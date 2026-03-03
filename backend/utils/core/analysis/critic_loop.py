"""Critic-Correction Closed Loop.

After each file is generated, a nano-auditor LLM call validates the code
for syntax, indentation, and missing imports.  On failure the reason is
returned to the caller so it can be injected as ``last_error`` in the
next generation attempt.

The critic uses the smallest available role (``"nano_reviewer"``).
A fallback to ``"coder"`` is used if that role is not configured.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from backend.utils.core.system.agent_logger import AgentLogger


class CriticLoop:
    """Calls the nano_critic_review prompt and parses the JSON verdict.

    Args:
        llm_manager: The ``IModelProvider`` instance (provides ``get_client``).
        logger: Agent logger for debug/info output.
    """

    def __init__(self, llm_manager, logger: AgentLogger) -> None:
        self._llm_manager = llm_manager
        self._logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def review(self, file_path: str, content: str, language: str) -> Optional[str]:
        """Review *content* using the nano critic and return error feedback.

        Args:
            file_path: Path of the file (used for log context only).
            content: Generated source code to validate.
            language: Programming language string (e.g. ``"python"``).

        Returns:
            A semicolon-joined error string when issues are found, or
            ``None`` when the code passes review or on any LLM/parse error.
            Returning ``None`` on error is intentional — the critic must
            **never** abort generation.
        """
        if not content or not language or language == "unknown":
            return None

        try:
            system_prompt, user_prompt = await self._build_prompts(language, content)
            client = self._get_client()
            response_data, _ = client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=[],
                options_override={"temperature": 0.0},
            )
            raw = response_data.get("content", "").strip()
            return self._parse_verdict(raw, file_path)
        except Exception as exc:
            self._logger.debug(f"[CriticLoop] Review failed for '{file_path}' (non-fatal): {exc}")
            return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_client(self):
        """Return the nano_reviewer client, falling back to coder."""
        try:
            return self._llm_manager.get_client("nano_reviewer")
        except Exception:
            return self._llm_manager.get_client("coder")

    async def _build_prompts(self, language: str, code: str):
        """Load the nano_critic_review prompt from YAML."""
        try:
            from backend.utils.domains.auto_generation.prompt_templates import AutoGenPrompts

            return await AutoGenPrompts.nano_critic_review(language, code)
        except Exception:
            # Inline fallback so the critic works even without YAML
            system = (
                "You are a syntax checker. Check for indentation errors, syntax errors, "
                "and missing imports that would cause a NameError. "
                'Output ONLY JSON: {"has_errors": true/false, "errors": ["..."]}'
            )
            user = f"Language: {language}\nCode:\n```\n{code}\n```\nOutput JSON only."
            return system, user

    def _parse_verdict(self, raw: str, file_path: str) -> Optional[str]:
        """Extract the JSON verdict from *raw* and return errors or None."""
        # Strip markdown fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
        # Find the first JSON object
        json_match = re.search(r"\{[\s\S]*\}", cleaned)
        if not json_match:
            self._logger.debug(f"[CriticLoop] No JSON in critic response for '{file_path}'")
            return None
        try:
            verdict = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            self._logger.debug(f"[CriticLoop] JSON parse error in critic response for '{file_path}'")
            return None

        if not verdict.get("has_errors", False):
            return None

        errors = verdict.get("errors", [])
        if not errors:
            return None
        return "; ".join(str(e) for e in errors if e)
