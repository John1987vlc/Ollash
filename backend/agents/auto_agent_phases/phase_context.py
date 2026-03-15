"""Shared state for the 8-phase AutoAgent pipeline.

PhaseContext is a simple dataclass passed between all phases. Phases mutate it
in place — no return values, no 3-tuple passing. This replaces the old 779-line
singleton with 30+ constructor arguments.
"""

from __future__ import annotations

import dataclasses
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

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

    cross_file_errors: List[Dict[str, Any]] = field(default_factory=list)
    # Written by CrossFileValidationPhase (4b). Consumed by PatchPhase improvement rounds.
    # Each entry: {file_a, file_b, error_type, description, suggestion}

    metrics: Dict[str, Any] = field(default_factory=dict)
    # token_usage per phase, phase_timings, schema_validity_rate, etc.

    # --- User-configurable pipeline knobs ---
    num_refine_loops: int = 3
    # Max improvement rounds in PatchPhase. Overridden from wizard's "Refinement Loops" slider.

    # --- Internal ---
    _phase_start_times: Dict[str, float] = field(default_factory=dict, repr=False)

    # Optional callback invoked after BlueprintPhase: on_blueprint_ready(blueprint_dict) -> bool.
    # Return False to abort the pipeline.
    on_blueprint_ready: Optional[Callable[[Dict[str, Any]], bool]] = field(default=None, repr=False)

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

    # ----------------------------------------------------------------
    # Description complexity (#15)
    # ----------------------------------------------------------------

    def description_complexity(self) -> int:
        """Return a complexity score 0-10 based on description length and keywords (M11).

        Used by AutoAgent to warn when a complex project is run on a small model,
        and by BlueprintPhase to adjust max_files dynamically.

        Scoring:
          0-3 pts  — description length (1 pt per 200 chars, capped at 3)
          +2 each  — high-complexity words (admin, login, booking, availability, …)
          +1 each  — standard complexity words (authentication, database, real-time, …)
          +1 bonus — multi-page app (≥2 navigation keywords: panel, page, section, …)
        """
        desc = self.project_description.lower()
        score = min(3, len(desc) // 200)  # 0-3 pts from length

        # High-complexity domain keywords — each worth 2 points (M11)
        high_complexity_words = [
            "admin",
            "login",
            "dashboard",
            "permission",
            "availability",
            "calendar",
            "reservation",
            "booking",
            "payment",
            "notification",
            "search",
            "upload",
        ]
        score += sum(2 for w in high_complexity_words if w in desc)

        # Standard complexity keywords — 1 point each
        standard_words = [
            "complex",
            "full",
            "complete",
            "enterprise",
            "advanced",
            "production",
            "scalable",
            "microservice",
            "distributed",
            "authentication",
            "authorization",
            "database",
            "real-time",
            "websocket",
            "async",
            "multi-user",
            "role",
        ]
        score += sum(1 for w in standard_words if w in desc)

        # Multi-page bonus: ≥2 navigation/view keywords → +1 (M11)
        multi_page_words = ["panel", "page", "section", "view", "screen", "tab"]
        if sum(1 for w in multi_page_words if w in desc) >= 2:
            score += 1

        return min(10, score)

    # ----------------------------------------------------------------
    # Checkpoint / resume (#1)
    # ----------------------------------------------------------------

    def to_checkpoint_dict(self, completed_phases: List[str]) -> Dict[str, Any]:
        """Serialize pipeline state for checkpoint/resume.

        Does NOT serialize non-picklable objects (llm_manager, file_manager, etc.).
        generated_files content is NOT saved here — it lives on disk.
        """
        return {
            "project_name": self.project_name,
            "project_description": self.project_description,
            "project_type": self.project_type,
            "tech_stack": self.tech_stack,
            "blueprint": [dataclasses.asdict(fp) for fp in self.blueprint],
            "generated_file_paths": list(self.generated_files.keys()),
            "errors": self.errors,
            "metrics": self.metrics,
            "completed_phases": completed_phases,
        }

    def apply_checkpoint_dict(self, data: Dict[str, Any]) -> None:
        """Restore pipeline state from checkpoint dict.

        Re-reads generated file contents from disk (content not stored in checkpoint).
        """
        self.project_type = data.get("project_type", self.project_type)
        self.tech_stack = data.get("tech_stack", self.tech_stack)
        self.blueprint = [FilePlan(**fp) for fp in data.get("blueprint", [])]
        self.errors = data.get("errors", [])
        self.metrics = data.get("metrics", {})

        # Re-read generated files from disk
        for rel_path in data.get("generated_file_paths", []):
            abs_path = self.project_root / rel_path
            if abs_path.exists():
                try:
                    self.generated_files[rel_path] = abs_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass

    def save_checkpoint(self, completed_phases: List[str]) -> None:
        """Write checkpoint JSON to .ollash/checkpoint.json inside the project root."""
        checkpoint_dir = self.project_root / ".ollash"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_dir / "checkpoint.json"
        data = self.to_checkpoint_dict(completed_phases)
        try:
            checkpoint_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as e:
            self.logger.warning(f"[Checkpoint] Could not save: {e}")

    @staticmethod
    def load_checkpoint(project_root: Path) -> Optional[Dict[str, Any]]:
        """Load checkpoint JSON from .ollash/checkpoint.json. Returns None if absent."""
        checkpoint_path = project_root / ".ollash" / "checkpoint.json"
        if not checkpoint_path.exists():
            return None
        try:
            return json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
