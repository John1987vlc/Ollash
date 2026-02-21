"""Phase failure database for tracking model failures by (model, phase) pair.

Stores failure records as JSON files. Used by AutoModelSelector to avoid
assigning models to phases where they consistently fail.
"""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger


@dataclass
class PhaseFailureRecord:
    """A single failure record for a (model, phase) pair."""

    model_name: str
    phase_name: str
    failure_type: str  # "loop_detected", "exception", "timeout", "quality_below_threshold"
    timestamp: float
    details: str = ""
    recovery_attempted: bool = False
    recovery_succeeded: bool = False


class PhaseFailureDatabase:
    """JSON-based database tracking model failures per phase.

    Maintains a failure count per (model, phase) pair. When failure count
    exceeds a configurable threshold, the model is marked as "not suitable"
    for that phase.

    Storage: {db_dir}/phase_failures.json
    """

    def __init__(
        self,
        db_dir: Path,
        logger: AgentLogger,
        unsuitability_threshold: int = 3,
    ):
        self.db_dir = Path(db_dir)
        self.logger = logger
        self.unsuitability_threshold = unsuitability_threshold
        self._records: List[PhaseFailureRecord] = []
        self._unsuitable: Dict[str, List[str]] = {}  # phase -> [models]
        self._load()

    def _load(self) -> None:
        """Load failure records from disk."""
        db_file = self.db_dir / "phase_failures.json"
        if not db_file.exists():
            return

        try:
            with open(db_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._records = [
                PhaseFailureRecord(
                    model_name=r["model_name"],
                    phase_name=r["phase_name"],
                    failure_type=r["failure_type"],
                    timestamp=r["timestamp"],
                    details=r.get("details", ""),
                    recovery_attempted=r.get("recovery_attempted", False),
                    recovery_succeeded=r.get("recovery_succeeded", False),
                )
                for r in data.get("records", [])
            ]

            self._unsuitable = data.get("unsuitable", {})
            self.logger.info(f"Loaded {len(self._records)} failure records from {db_file}")
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.warning(f"Failed to load phase failure database: {e}")

    def _save(self) -> None:
        """Persist failure records to disk."""
        self.db_dir.mkdir(parents=True, exist_ok=True)
        db_file = self.db_dir / "phase_failures.json"

        data = {
            "records": [asdict(r) for r in self._records],
            "unsuitable": self._unsuitable,
            "last_updated": time.time(),
        }

        try:
            with open(db_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to save phase failure database: {e}")

    def record_failure(self, record: PhaseFailureRecord) -> None:
        """Record a new failure and check if model becomes unsuitable."""
        self._records.append(record)

        # Check threshold
        failure_count = self.get_failure_count(record.model_name, record.phase_name)
        if failure_count >= self.unsuitability_threshold:
            if record.phase_name not in self._unsuitable:
                self._unsuitable[record.phase_name] = []
            if record.model_name not in self._unsuitable[record.phase_name]:
                self._unsuitable[record.phase_name].append(record.model_name)
                self.logger.warning(
                    f"Model '{record.model_name}' marked unsuitable for "
                    f"'{record.phase_name}' after {failure_count} failures"
                )

        self._save()

    def is_model_suitable(self, model_name: str, phase_name: str) -> bool:
        """Check if a model is still suitable for a phase."""
        unsuitable_models = self._unsuitable.get(phase_name, [])
        return model_name not in unsuitable_models

    def get_failure_count(self, model_name: str, phase_name: str) -> int:
        """Get number of failures for a (model, phase) pair."""
        return sum(1 for r in self._records if r.model_name == model_name and r.phase_name == phase_name)

    def get_unsuitable_models(self, phase_name: str) -> List[str]:
        """Get list of models marked unsuitable for a phase."""
        return list(self._unsuitable.get(phase_name, []))

    def get_failure_summary(self) -> Dict[str, Any]:
        """Get a summary of all failures grouped by phase and model."""
        summary: Dict[str, Dict[str, Any]] = {}

        for record in self._records:
            phase = record.phase_name
            model = record.model_name

            if phase not in summary:
                summary[phase] = {}
            if model not in summary[phase]:
                summary[phase][model] = {
                    "failure_count": 0,
                    "failure_types": [],
                    "is_suitable": self.is_model_suitable(model, phase),
                    "last_failure": 0.0,
                }

            summary[phase][model]["failure_count"] += 1
            if record.failure_type not in summary[phase][model]["failure_types"]:
                summary[phase][model]["failure_types"].append(record.failure_type)
            summary[phase][model]["last_failure"] = max(summary[phase][model]["last_failure"], record.timestamp)

        return {
            "total_failures": len(self._records),
            "total_unsuitable_pairs": sum(len(models) for models in self._unsuitable.values()),
            "phases": summary,
        }

    def clear_records(self, model_name: Optional[str] = None, phase_name: Optional[str] = None) -> int:
        """Clear failure records, optionally filtered by model and/or phase.

        Returns the number of records removed.
        """
        original_count = len(self._records)

        if model_name and phase_name:
            self._records = [
                r for r in self._records if not (r.model_name == model_name and r.phase_name == phase_name)
            ]
            # Also clear unsuitable status
            if phase_name in self._unsuitable:
                self._unsuitable[phase_name] = [m for m in self._unsuitable[phase_name] if m != model_name]
        elif model_name:
            self._records = [r for r in self._records if r.model_name != model_name]
            for phase in self._unsuitable:
                self._unsuitable[phase] = [m for m in self._unsuitable[phase] if m != model_name]
        elif phase_name:
            self._records = [r for r in self._records if r.phase_name != phase_name]
            self._unsuitable.pop(phase_name, None)
        else:
            self._records = []
            self._unsuitable = {}

        removed = original_count - len(self._records)
        if removed > 0:
            self._save()
        return removed
