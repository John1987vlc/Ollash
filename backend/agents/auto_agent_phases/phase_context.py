"""Shared state for the 8-phase AutoAgent pipeline.

PhaseContext is a simple dataclass passed between all phases. Phases mutate it
in place — no return values, no 3-tuple passing. This replaces the old 779-line
singleton with 30+ constructor arguments.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from backend.interfaces.imodel_provider import IModelProvider
    from backend.utils.core.system.agent_logger import AgentLogger
    from backend.utils.core.system.event_publisher import EventPublisher
    from backend.utils.core.io.file_manager import FileManager


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class FilePlan:
    """Blueprint entry for a single file to be generated."""

    path: str
    purpose: str
    exports: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)  # other project files this depends on
    key_logic: str = ""
    priority: int = 10  # lower number = generate first


# ---------------------------------------------------------------------------
# PhaseContext
# ---------------------------------------------------------------------------


@dataclass
class PhaseContext:
    """Shared mutable state for the 8-phase AutoAgent pipeline.

    Immutable inputs (set at construction, never mutated by phases):
        project_name, project_description, project_root,
        llm_manager, file_manager, event_publisher, logger

    Mutable phase state (grows through the pipeline):
        project_type, tech_stack, blueprint,
        generated_files, errors, metrics
    """

    # --- Immutable inputs ---
    project_name: str
    project_description: str
    project_root: Path

    # --- Infrastructure (injected, typed under TYPE_CHECKING to keep imports light) ---
    llm_manager: "IModelProvider"
    file_manager: "FileManager"
    event_publisher: "EventPublisher"
    logger: "AgentLogger"

    # --- Detected (set by ProjectScanPhase, stable afterward) ---
    project_type: str = "unknown"
    tech_stack: List[str] = field(default_factory=list)

    # --- Phase state (grows through pipeline) ---
    blueprint: List[FilePlan] = field(default_factory=list)
    # Populated by BlueprintPhase. Sorted by priority.

    generated_files: Dict[str, str] = field(default_factory=dict)
    # path -> content. Grows through CodeFillPhase.

    errors: List[str] = field(default_factory=list)
    # Non-fatal errors collected for FinishPhase summary.

    metrics: Dict[str, Any] = field(default_factory=dict)
    # token_usage per phase, phase_timings, schema_validity_rate, etc.

    # --- Internal ---
    _phase_start_times: Dict[str, float] = field(default_factory=dict, repr=False)

    # ----------------------------------------------------------------
    # Model-size helpers
    # ----------------------------------------------------------------

    def _model_size_b(self, role: str = "coder") -> float:
        """Return model size in billions. Returns 999.0 on parse failure (= treat as large)."""
        try:
            client = self.llm_manager.get_client(role)
            model_name: str = getattr(client, "model", "") or ""
            m = re.search(r"(\d+(?:\.\d+)?)b", model_name.lower())
            if m:
                return float(m.group(1))
        except Exception:
            pass
        return 999.0

    def is_small(self, role: str = "coder") -> bool:
        """True if model <=8B (4B / 7B / 8B tier)."""
        return self._model_size_b(role) <= 8.0

    def is_micro(self, role: str = "coder") -> bool:
        """True if model <=2B (true nano)."""
        return self._model_size_b(role) <= 2.0

    # ----------------------------------------------------------------
    # Metrics helpers
    # ----------------------------------------------------------------

    def start_phase_timer(self, phase_id: str) -> None:
        self._phase_start_times[phase_id] = time.monotonic()

    def end_phase_timer(self, phase_id: str) -> float:
        """Record elapsed seconds and return it."""
        elapsed = time.monotonic() - self._phase_start_times.get(phase_id, time.monotonic())
        timings: Dict[str, float] = self.metrics.setdefault("phase_timings", {})
        timings[phase_id] = round(elapsed, 2)
        return elapsed

    def record_tokens(self, phase_id: str, prompt_tokens: int, completion_tokens: int) -> None:
        usage: Dict[str, Any] = self.metrics.setdefault("token_usage", {})
        phase_usage = usage.setdefault(phase_id, {"prompt": 0, "completion": 0})
        phase_usage["prompt"] += prompt_tokens
        phase_usage["completion"] += completion_tokens

    def total_tokens(self) -> int:
        usage = self.metrics.get("token_usage", {})
        return sum(v["prompt"] + v["completion"] for v in usage.values())
