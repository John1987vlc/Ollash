"""Simplified base class for all 8 AutoAgent pipeline phases.

Key design:
- execute(ctx) -> None   — mutates ctx in place, no 3-tuple return
- _llm_call()            — enforces token budgets before sending
- _llm_json()            — validates output against a Pydantic schema, retries on failure
- _write_file()          — writes disk + updates ctx.generated_files
"""

from __future__ import annotations

import time
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
        if ctx.run_logger:
            ctx.run_logger.log_phase_start(self.phase_id, self.phase_label)

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
            if ctx.run_logger:
                ctx.run_logger.log_phase_end(self.phase_id, self.phase_label, elapsed, "success")
        except PipelinePhaseError as e:
            elapsed = ctx.end_phase_timer(self.phase_id)
            ctx.event_publisher.publish_sync("phase_complete", phase=self.phase_id, status="error")
            if ctx.run_logger:
                ctx.run_logger.log_phase_end(self.phase_id, self.phase_label, elapsed, "error", str(e))
            raise
        except Exception as e:
            elapsed = ctx.end_phase_timer(self.phase_id)
            ctx.event_publisher.publish_sync("phase_complete", phase=self.phase_id, status="error", error=str(e))
            ctx.logger.error(f"[{ctx.project_name}] PHASE {self.phase_id} failed: {e}", exc_info=True)
            if ctx.run_logger:
                ctx.run_logger.log_phase_end(self.phase_id, self.phase_label, elapsed, "error", str(e))
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
        no_think: bool = False,
    ) -> str:
        """Centralized LLM call with token budget enforcement.

        Truncates system/user if they exceed budget before sending.
        Returns raw response string. Records token usage in ctx.metrics.

        no_think=True prepends /no_think to the user message, disabling Qwen3's
        extended thinking mode so that all token budget is used for the actual output.
        """
        from backend.utils.core.llm.llm_response_parser import LLMResponseParser

        system = self._truncate_to_tokens(system, _SYSTEM_TOKEN_BUDGET)
        user = self._truncate_to_tokens(user, _USER_TOKEN_BUDGET)

        client = ctx.llm_manager.get_client(role)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        # no_think=True → pass "think": False as a top-level Ollama API field (Qwen3 thinking mode).
        # Also keep the /no_think prefix as belt-and-suspenders for older Ollama versions.
        opts: dict = {"temperature": temperature, "num_predict": max_tokens}
        if no_think:
            opts["think"] = False
            if not user.startswith("/no_think"):
                messages[-1]["content"] = "/no_think\n" + user
        _llm_call_start = time.monotonic()
        response_data, _ = client.chat(
            messages,
            tools=[],
            options_override=opts,
        )
        _llm_elapsed_ms = (time.monotonic() - _llm_call_start) * 1000.0
        msg = response_data.get("message", {})
        content: str = msg.get("content", "")

        # Strip <think> blocks (Qwen3 emits these in content when not using no_think)
        content, _ = LLMResponseParser.remove_think_blocks(content)

        # Fallback: if content is empty, model used all tokens for thinking
        # (done_reason=="length"). Try to salvage a JSON object from the thinking field.
        if not content.strip():
            thinking: str = msg.get("thinking", "")
            # Only use thinking fallback when it contains an actual JSON object (starts with {)
            if thinking and "{" in thinking:
                ctx.logger.warning(
                    f"[{self.phase_id}] content empty (model exhausted tokens in think block); "
                    "attempting to extract JSON object from thinking field"
                )
                # Extract only the JSON object portion to avoid returning arbitrary list values
                start = thinking.find("{")
                content = thinking[start:]

        # Record token usage
        prompt_tokens = response_data.get("prompt_eval_count", len(system + user) // _CHARS_PER_TOKEN)
        completion_tokens = response_data.get("eval_count", len(content) // _CHARS_PER_TOKEN)
        ctx.record_tokens(self.phase_id, prompt_tokens, completion_tokens)

        # Run log: capture every LLM call with full prompts + response
        if ctx.run_logger:
            call_index = ctx.run_logger._next_call_index(self.phase_id)
            ctx.run_logger.log_llm_call(
                phase_id=self.phase_id,
                call_index=call_index,
                role=role,
                system=system,
                user=user,
                response=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                elapsed_ms=_llm_elapsed_ms,
                no_think=no_think,
            )

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

        Uses no_think=True (Qwen3 /no_think control token) so the model does not
        exhaust its token budget on chain-of-thought reasoning before writing JSON.
        Uses a higher num_predict budget so the full JSON object fits in one reply.
        """
        from backend.utils.core.llm.llm_response_parser import LLMResponseParser

        last_error: Optional[str] = None
        current_user = user

        for attempt in range(retries + 1):
            raw = self._llm_call(
                ctx,
                system,
                current_user,
                role=role,
                max_tokens=4096,
                no_think=True,
            )
            try:
                data = LLMResponseParser.extract_json(raw)
                # Attempt to recover truncated JSON when bracket matching fails
                if data is None and raw and "{" in raw:
                    data = self._recover_truncated_json(raw)
                if data is None:
                    raise ValueError("No JSON found in response")
                # For schema validation, we need a dict not a list
                if not isinstance(data, dict):
                    raise ValueError(f"Expected JSON object, got {type(data).__name__}")
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

    @staticmethod
    def _recover_truncated_json(text: str) -> Optional[Any]:
        """Try to recover a valid JSON object from truncated output.

        When a model runs out of tokens mid-JSON, the bracket counts reveal exactly
        how many closing brackets are missing. We append them and try to parse.
        Only returns a dict (not a list) to guard against false positives.
        """
        import json

        # Start from the first { in the text
        start = text.find("{")
        if start == -1:
            return None
        candidate = text[start:]

        # Count unmatched brackets
        open_curly = 0
        open_square = 0
        in_string = False
        escape_next = False
        for ch in candidate:
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                open_curly += 1
            elif ch == "}":
                open_curly -= 1
            elif ch == "[":
                open_square += 1
            elif ch == "]":
                open_square -= 1

        if open_curly <= 0 and open_square <= 0:
            return None  # Already balanced — bracket matcher should have caught it

        # Append missing closing brackets (innermost first)
        tail = "]" * max(0, open_square) + "}" * max(0, open_curly)
        try:
            result = json.loads(candidate + tail)
            return result if isinstance(result, dict) else None
        except json.JSONDecodeError:
            return None
