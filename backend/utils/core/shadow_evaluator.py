"""Shadow evaluation system for continuous model performance monitoring.

Runs alongside the production pipeline, logging model outputs and
comparing against a critic model's corrections. When correction rate
exceeds a threshold, the model's affinity score is reduced.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.agent_logger import AgentLogger


@dataclass
class ShadowLog:
    """A single shadow evaluation log entry."""

    timestamp: float
    phase_name: str
    model_name: str
    input_hash: str  # Hash of the prompt/input for deduplication
    output_preview: str  # First 500 chars of model output
    critic_correction: Optional[str] = None  # None if critic agreed
    correction_severity: float = 0.0  # 0.0 = no correction, 1.0 = full rewrite
    metadata: Dict[str, Any] = field(default_factory=dict)


class ShadowEvaluator:
    """Evaluates model performance in production via shadow logging.

    Subscribes to EventPublisher events (phase_complete, shadow_evaluate)
    to passively monitor model outputs. Tracks correction rates and
    flags models that exceed the critic threshold.

    Usage:
        evaluator = ShadowEvaluator(logger, event_publisher, log_dir)
        evaluator.start()  # Subscribes to events
        # ... phases run normally ...
        evaluator.stop()
        report = evaluator.get_performance_report()
    """

    def __init__(
        self,
        logger: AgentLogger,
        event_publisher: Any,
        log_dir: Path,
        critic_threshold: float = 0.3,
    ):
        self.logger = logger
        self.event_publisher = event_publisher
        self.log_dir = Path(log_dir)
        self.critic_threshold = critic_threshold
        self._logs: List[ShadowLog] = []
        self._active = False

    def start(self) -> None:
        """Subscribe to phase events for shadow logging."""
        self._active = True
        if hasattr(self.event_publisher, "subscribe"):
            self.event_publisher.subscribe("phase_complete", self._on_phase_complete)
            self.event_publisher.subscribe("shadow_evaluate", self._on_shadow_evaluate)
        self.logger.info("Shadow evaluator started")

    def stop(self) -> None:
        """Unsubscribe and persist logs."""
        self._active = False
        if hasattr(self.event_publisher, "unsubscribe"):
            self.event_publisher.unsubscribe("phase_complete", self._on_phase_complete)
            self.event_publisher.unsubscribe("shadow_evaluate", self._on_shadow_evaluate)
        self._persist_logs()
        self.logger.info(f"Shadow evaluator stopped. {len(self._logs)} logs persisted.")

    def _on_phase_complete(self, event_data: Dict) -> None:
        """Handle phase_complete events for passive logging."""
        if not self._active:
            return

        phase_name = event_data.get("phase", event_data.get("phase_name", "unknown"))
        model_name = event_data.get("model_name", "unknown")
        output = str(event_data.get("output_preview", ""))[:500]
        input_text = str(event_data.get("input_preview", ""))

        log = ShadowLog(
            timestamp=time.time(),
            phase_name=phase_name,
            model_name=model_name,
            input_hash=hashlib.md5(input_text.encode()).hexdigest(),
            output_preview=output,
        )
        self._logs.append(log)

    def _on_shadow_evaluate(self, event_data: Dict) -> None:
        """Handle explicit shadow evaluation requests from phases."""
        if not self._active:
            return

        phase_name = event_data.get("phase", event_data.get("phase_name", "unknown"))
        model_name = event_data.get("model_name", "unknown")
        output = str(event_data.get("output_preview", ""))[:500]
        critic_correction = event_data.get("critic_correction")
        severity = float(event_data.get("correction_severity", 0.0))

        log = ShadowLog(
            timestamp=time.time(),
            phase_name=phase_name,
            model_name=model_name,
            input_hash=hashlib.md5(output.encode()).hexdigest(),
            output_preview=output,
            critic_correction=critic_correction,
            correction_severity=severity,
            metadata=event_data.get("metadata", {}),
        )
        self._logs.append(log)

    def record_shadow_log(self, log: ShadowLog) -> None:
        """Record a shadow log entry directly."""
        self._logs.append(log)

    def get_correction_rate(self, model_name: str, phase_name: Optional[str] = None) -> float:
        """Get the correction rate for a model (optionally filtered by phase).

        Returns ratio of corrected outputs to total outputs.
        """
        relevant = [log for log in self._logs if log.model_name == model_name]
        if phase_name:
            relevant = [log for log in relevant if log.phase_name == phase_name]

        if not relevant:
            return 0.0

        corrected = sum(1 for log in relevant if log.critic_correction is not None)
        return corrected / len(relevant)

    def get_average_correction_severity(self, model_name: str, phase_name: Optional[str] = None) -> float:
        """Get average correction severity for a model."""
        relevant = [log for log in self._logs if log.model_name == model_name]
        if phase_name:
            relevant = [log for log in relevant if log.phase_name == phase_name]

        if not relevant:
            return 0.0

        return sum(log.correction_severity for log in relevant) / len(relevant)

    def is_model_flagged(self, model_name: str, phase_name: Optional[str] = None) -> bool:
        """Check if a model's correction rate exceeds the threshold."""
        return self.get_correction_rate(model_name, phase_name) > self.critic_threshold

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate a summary report of shadow evaluation results."""
        models: Dict[str, Dict[str, Any]] = {}

        for log in self._logs:
            if log.model_name not in models:
                models[log.model_name] = {
                    "total_evaluations": 0,
                    "corrections": 0,
                    "phases": {},
                    "avg_severity": 0.0,
                }

            model_data = models[log.model_name]
            model_data["total_evaluations"] += 1
            if log.critic_correction is not None:
                model_data["corrections"] += 1

            # Per-phase breakdown
            phase = log.phase_name
            if phase not in model_data["phases"]:
                model_data["phases"][phase] = {"total": 0, "corrections": 0}
            model_data["phases"][phase]["total"] += 1
            if log.critic_correction is not None:
                model_data["phases"][phase]["corrections"] += 1

        # Compute derived metrics
        for model_name, data in models.items():
            total = data["total_evaluations"]
            data["correction_rate"] = data["corrections"] / total if total > 0 else 0.0
            data["avg_severity"] = self.get_average_correction_severity(model_name)
            data["flagged"] = data["correction_rate"] > self.critic_threshold

            for phase_data in data["phases"].values():
                p_total = phase_data["total"]
                phase_data["correction_rate"] = phase_data["corrections"] / p_total if p_total > 0 else 0.0

        return {
            "total_logs": len(self._logs),
            "critic_threshold": self.critic_threshold,
            "models": models,
        }

    def _persist_logs(self) -> None:
        """Save logs to JSON file in log_dir."""
        if not self._logs:
            return

        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self.log_dir / f"shadow_logs_{int(time.time())}.json"

        serializable = []
        for log in self._logs:
            entry = asdict(log)
            serializable.append(entry)

        try:
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2, default=str)
            self.logger.info(f"Shadow logs saved to {log_file}")
        except Exception as e:
            self.logger.error(f"Failed to persist shadow logs: {e}")
