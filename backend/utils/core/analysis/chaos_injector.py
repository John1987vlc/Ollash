"""Chaos Engineering — Fault Injector.

Injects deterministic faults into generated source code for verifying
that the agent supervision pipeline (ShadowEvaluator, supervisor phases)
detects and repairs them automatically.

Activation is controlled by agent_features.json:
    "chaos_engineering": {"enabled": false, "injection_rate": 0.2}

Disabled by default — set ``enabled: true`` only in controlled test environments.
"""

from __future__ import annotations

import random
import re
from typing import Optional, Tuple

from backend.utils.core.system.agent_logger import AgentLogger


class ChaosInjector:
    """Injects random structural faults into source code.

    Supported fault types:
    - ``remove_import``: Delete one import/include line at random.
    - ``rename_variable``: Rename the first local variable found to a nonsense name.

    Args:
        injection_rate: Probability (0–1) that any given file is corrupted.
        logger: Optional logger for debug output.
    """

    FAULT_TYPES = ["remove_import", "rename_variable"]

    def __init__(
        self,
        injection_rate: float = 0.2,
        logger: Optional[AgentLogger] = None,
    ) -> None:
        self.injection_rate = max(0.0, min(1.0, injection_rate))
        self.logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_inject(self) -> bool:
        """Return ``True`` with probability ``self.injection_rate``."""
        return random.random() < self.injection_rate

    def inject_fault(self, content: str, language: str) -> Tuple[str, str]:
        """Inject a random fault into *content*.

        Returns:
            ``(corrupted_content, description)`` when a fault is injected, or
            ``(content, "")`` when the rate check fails or no suitable
            injection point is found.
        """
        if not self.should_inject() or not content:
            return content, ""

        fault_type = random.choice(self.FAULT_TYPES)
        if fault_type == "remove_import":
            result, desc = self._remove_random_import(content, language)
        else:
            result, desc = self._rename_local_variable(content, language)

        if desc and self.logger:
            self.logger.debug(f"[Chaos] {fault_type} injected: {desc}")

        return result, desc

    # ------------------------------------------------------------------
    # Fault implementations
    # ------------------------------------------------------------------

    def _remove_random_import(self, content: str, language: str) -> Tuple[str, str]:
        """Remove one import/include line chosen at random."""
        lines = content.splitlines(keepends=True)
        if language in ("python", "py"):
            import_lines = [
                i for i, ln in enumerate(lines) if re.match(r"^\s*(?:import|from)\s+\S+", ln)
            ]
        else:
            import_lines = [
                i
                for i, ln in enumerate(lines)
                if re.match(r"^\s*(?:import|require|#include)\s+", ln)
            ]

        if not import_lines:
            return content, ""

        idx = random.choice(import_lines)
        removed_line = lines[idx].rstrip()
        del lines[idx]
        return "".join(lines), f"Removed import line: {removed_line!r}"

    def _rename_local_variable(self, content: str, language: str) -> Tuple[str, str]:
        """Rename the first local variable assignment to a nonsense name."""
        _PROTECTED = frozenset(
            {"self", "cls", "this", "return", "True", "False", "None", "true", "false", "null"}
        )

        if language in ("python", "py"):
            match = re.search(r"\n[ \t]{4,}([a-zA-Z_]\w*)\s*=\s*", content)
            if match:
                original = match.group(1)
            else:
                return content, ""
        else:
            match = re.search(r"\b(?:let|const|var)\s+([a-zA-Z_]\w*)\s*=", content)
            if match:
                original = match.group(1)
            else:
                return content, ""

        if original in _PROTECTED:
            return content, ""

        corrupted_name = f"__chaos_{original}_x"
        new_content = content.replace(original, corrupted_name, 1)
        return new_content, f"Renamed variable {original!r} → {corrupted_name!r}"
