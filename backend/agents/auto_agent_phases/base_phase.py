"""Simplified base class for all 8 AutoAgent pipeline phases.

Key design:
- execute(ctx) -> None   — mutates ctx in place, no 3-tuple return
- _llm_call()            — enforces token budgets before sending
- _llm_json()            — validates output against a Pydantic schema, retries on failure
- _write_file()          — writes disk + updates ctx.generated_files
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.utils.core.exceptions import PipelinePhaseError

# Token budget constants for 4B / 8K context window
# 1 token ≈ 4 characters (English text / code)
_SYSTEM_TOKEN_BUDGET = 800  # ~3200 chars
_USER_TOKEN_BUDGET = 2200  # ~8800 chars
_CHARS_PER_TOKEN = 4


class BasePhase(ABC):
    """Simplified base class for all 8 pipeline phases."""

    phase_id: str = ""
    phase_label: str = ""

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def execute(self, ctx: PhaseContext) -> None:
        """Wrapper: publish events, time the phase, call run(), handle errors."""
        ctx.start_phase_timer(self.phase_id)
        ctx.event_publisher.publish_sync(
            "phase_start",
            phase=self.phase_id,
            label=self.phase_label,
        )
        ctx.logger.info(f"[{ctx.project_name}] PHASE {self.phase_id}: {self.phase_label}")

        try:
            self.run(ctx)
            elapsed = ctx.end_phase_timer(self.phase_id)
            ctx.event_publisher.publish_sync(
                "phase_complete",
                phase=self.phase_id,
                status="success",
                elapsed=elapsed,
            )
            ctx.logger.info(f"[{ctx.project_name}] PHASE {self.phase_id} done ({elapsed:.1f}s)")
        except PipelinePhaseError:
            ctx.end_phase_timer(self.phase_id)
            ctx.event_publisher.publish_sync("phase_complete", phase=self.phase_id, status="error")
            raise
        except Exception as e:
            ctx.end_phase_timer(self.phase_id)
            ctx.event_publisher.publish_sync("phase_complete", phase=self.phase_id, status="error", error=str(e))
            ctx.logger.error(f"[{ctx.project_name}] PHASE {self.phase_id} failed: {e}", exc_info=True)
            raise PipelinePhaseError(self.phase_id, str(e)) from e

    @abstractmethod
    def run(self, ctx: PhaseContext) -> None:
        """Override this. Mutates ctx in place. Must not return values."""
        raise NotImplementedError

    # ----------------------------------------------------------------
    # LLM helpers
    # ----------------------------------------------------------------

    def _llm_call(
        self,
        ctx: PhaseContext,
        system: str,
        user: str,
        role: str = "coder",
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Centralized LLM call with token budget enforcement.

        Truncates system/user if they exceed budget before sending.
        Returns raw response string. Records token usage in ctx.metrics.
        """
        system = self._truncate_to_tokens(system, _SYSTEM_TOKEN_BUDGET)
        user = self._truncate_to_tokens(user, _USER_TOKEN_BUDGET)

        client = ctx.llm_manager.get_client(role)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        response_data, _ = client.chat(
            messages,
            tools=[],
            options={"temperature": temperature, "num_predict": max_tokens},
        )
        content: str = response_data.get("message", {}).get("content", "")

        # Strip <think> blocks (Qwen3 emits these)
        from backend.utils.core.llm.llm_response_parser import LLMResponseParser

        content, _ = LLMResponseParser.remove_think_blocks(content)

        # Record token usage
        prompt_tokens = response_data.get("prompt_eval_count", len(system + user) // _CHARS_PER_TOKEN)
        completion_tokens = response_data.get("eval_count", len(content) // _CHARS_PER_TOKEN)
        ctx.record_tokens(self.phase_id, prompt_tokens, completion_tokens)

        return content

    def _llm_json(
        self,
        ctx: PhaseContext,
        system: str,
        user: str,
        schema_class: Type[Any],
        role: str = "coder",
        retries: int = 2,
    ) -> Any:
        """LLM call that validates output against a Pydantic schema.

        Retries up to `retries` times on JSON parse or validation failure.
        Raises PipelinePhaseError after all retries exhausted.
        """
        from backend.utils.core.llm.llm_response_parser import LLMResponseParser

        last_error: Optional[str] = None
        current_user = user

        for attempt in range(retries + 1):
            raw = self._llm_call(ctx, system, current_user, role=role)
            try:
                data = LLMResponseParser.extract_json(raw)
                if data is None:
                    raise ValueError("No JSON found in response")
                return schema_class.model_validate(data)
            except Exception as e:
                last_error = str(e)
                ctx.logger.warning(f"[{self.phase_id}] JSON parse attempt {attempt + 1}/{retries + 1} failed: {e}")
                if attempt < retries:
                    current_user = (
                        user
                        + f"\n\nPREVIOUS ATTEMPT FAILED: {last_error}"
                        + "\nFix the JSON and try again. Output ONLY valid JSON, no markdown."
                    )

        raise PipelinePhaseError(
            self.phase_id,
            f"JSON schema validation failed after {retries + 1} attempts: {last_error}",
        )

    # ----------------------------------------------------------------
    # File helpers
    # ----------------------------------------------------------------

    def _write_file(self, ctx: PhaseContext, rel_path: str, content: str) -> None:
        """Write a file to disk and record it in ctx.generated_files."""
        abs_path = ctx.project_root / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        ctx.file_manager.write_file(str(abs_path), content)
        ctx.generated_files[rel_path] = content

    def _read_file(self, ctx: PhaseContext, rel_path: str) -> Optional[str]:
        """Read a file from disk. Returns None if missing."""
        abs_path = ctx.project_root / rel_path
        try:
            return ctx.file_manager.read_file(str(abs_path))
        except (FileNotFoundError, OSError):
            return None

    # ----------------------------------------------------------------
    # Utility helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _truncate_to_tokens(text: str, max_tokens: int) -> str:
        """Hard-truncate text to approximately max_tokens."""
        limit = max_tokens * _CHARS_PER_TOKEN
        if len(text) <= limit:
            return text
        return text[:limit]
