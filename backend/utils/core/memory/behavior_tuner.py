"""
Behavior Tuner for Phase 3: Automatic Learning

Automatically adjusts agent behavior based on user feedback and patterns.
Learns from interactions and adapts responses accordingly.

Key Features:
- Response parameter tuning
- Communication style adaptation
- Response quality optimization
- Feature toggling based on usage
- Auto-adjustment suggestions
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class TuningParameter(Enum):
    """Parameters that can be tuned."""

    RESPONSE_LENGTH = "response_length"
    DETAIL_LEVEL = "detail_level"
    CODE_EXAMPLE_FREQUENCY = "code_example_frequency"
    DIAGRAM_FREQUENCY = "diagram_frequency"
    ERROR_VERBOSITY = "error_verbosity"
    SUGGESTION_COUNT = "suggestion_count"
    TIMEOUT_SECONDS = "timeout_seconds"


@dataclass
class TuningConfig:
    """Configuration for behavior tuning."""

    # Response generation parameters
    max_response_length: int = 2000  # characters
    detail_level: float = 0.7  # 0-1 scale
    code_example_frequency: float = 0.5  # 0-1 (probability)
    diagram_frequency: float = 0.4  # 0-1
    error_verbosity: float = 0.6  # 0-1
    suggestion_count: int = 3  # number of suggestions
    timeout_seconds: float = 30.0

    # Feature toggles
    use_cross_reference: bool = True
    use_knowledge_graph: bool = True
    use_decision_memory: bool = True
    use_artifacts: bool = True

    # Quality parameters
    confidence_threshold: float = 0.6  # 0-1
    include_sources: bool = True
    include_disclaimers: bool = True

    # Learning parameters
    auto_tune_enabled: bool = True
    learning_rate: float = 0.1  # How fast to adapt
    adaptation_window: int = 20  # Feedback samples to consider

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TuningChange:
    """Record of a tuning adjustment."""

    parameter: str
    old_value: Any
    new_value: Any
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    confidence: float = 0.5


class BehaviorTuner:
    """
    Automatically tunes agent behavior based on feedback.

    Responsibilities:
    - Monitor user feedback and satisfaction
    - Adjust response parameters
    - Toggle features based on usage
    - Learn from outcomes
    - Generate tuning recommendations
    """

    def __init__(self, workspace_root: Path = None):
        """
        Initialize behavior tuner.

        Args:
            workspace_root: Root path for storage
        """
        self.workspace_root = workspace_root or Path.cwd()
        self.tuning_dir = self.workspace_root / "knowledge_workspace" / "tuning"
        self.tuning_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.tuning_dir / "tuning_config.json"
        self.changes_file = self.tuning_dir / "tuning_changes.json"

        self.config = TuningConfig()
        self.change_history: List[TuningChange] = []

        self._load_config()

    def _load_config(self):
        """Load tuning configuration from disk."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.config = TuningConfig(**data)
                logger.info("Loaded tuning configuration")
            except Exception as e:
                logger.error(f"Error loading config: {e}")

        if self.changes_file.exists():
            try:
                with open(self.changes_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.change_history = [TuningChange(**change) for change in data.get("changes", [])]
            except Exception as e:
                logger.error(f"Error loading change history: {e}")

    def _save_config(self):
        """Save tuning configuration to disk."""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(asdict(self.config), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def _save_history(self):
        """Save change history to disk."""
        try:
            with open(self.changes_file, "w", encoding="utf-8") as f:
                json.dump(
                    {"changes": [asdict(c) for c in self.change_history[-100:]]},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.error(f"Error saving change history: {e}")

    def update_parameter(
        self,
        parameter: TuningParameter,
        new_value: Any,
        reason: str = "",
        confidence: float = 0.7,
    ) -> bool:
        """
        Update a tuning parameter.

        Args:
            parameter: Parameter to update
            new_value: New value
            reason: Reason for change
            confidence: Confidence in the change (0-1)

        Returns:
            Success status
        """
        param_name = parameter.value

        # Get current value
        if hasattr(self.config, param_name):
            old_value = getattr(self.config, param_name)

            # Apply change using learning rate
            if isinstance(old_value, (int, float)):
                adjusted_value = old_value + (new_value - old_value) * self.config.learning_rate
                setattr(self.config, param_name, adjusted_value)
            else:
                setattr(self.config, param_name, new_value)

            # Record change
            change = TuningChange(
                parameter=param_name,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                confidence=confidence,
            )
            self.change_history.append(change)

            # Save
            self.config.last_modified = datetime.now().isoformat()
            self._save_config()
            self._save_history()

            logger.info(f"Updated {param_name}: {old_value} → {new_value}")
            return True

        return False

    def adapt_to_feedback(self, feedback_score: float, feedback_type: str, keywords: List[str] = None):
        """
        Adapt behavior based on user feedback.

        Args:
            feedback_score: Score 1-5
            feedback_type: "response_length", "clarity", "relevance", etc.
            keywords: Keywords from feedback
        """
        if not self.config.auto_tune_enabled:
            return

        keywords = keywords or []

        # Positive feedback (4-5 score)
        if feedback_score >= 4.0:
            # Reinforce successful parameters - maintain them
            pass

        # Negative feedback (1-2 score)
        elif feedback_score <= 2.0:
            self._handle_negative_feedback(feedback_type, keywords)

        # Neutral/mixed (3 score)
        else:
            self._handle_neutral_feedback(feedback_type, keywords)

    def _handle_negative_feedback(self, feedback_type: str, keywords: List[str]):
        """Handle negative feedback by adjusting parameters."""

        if "too_long" in keywords or feedback_type == "response_length":
            self.update_parameter(
                TuningParameter.RESPONSE_LENGTH,
                self.config.max_response_length * 0.8,
                reason="User feedback: response too long",
                confidence=0.8,
            )

        if "too_detailed" in keywords or feedback_type == "detail_level":
            self.update_parameter(
                TuningParameter.DETAIL_LEVEL,
                self.config.detail_level * 0.9,
                reason="User feedback: too detailed",
                confidence=0.8,
            )

        if "not_clear" in keywords or "unclear" in keywords:
            # Increase example frequency and reduce complexity
            self.update_parameter(
                TuningParameter.CODE_EXAMPLE_FREQUENCY,
                min(1.0, self.config.code_example_frequency + 0.2),
                reason="User feedback: unclear, adding examples",
                confidence=0.7,
            )

        if "slow" in keywords or feedback_type == "performance":
            # Reduce unnecessary features
            self.update_parameter(
                TuningParameter.DIAGRAM_FREQUENCY,
                self.config.diagram_frequency * 0.8,
                reason="User feedback: slow response",
                confidence=0.7,
            )

    def _handle_neutral_feedback(self, feedback_type: str, keywords: List[str]):
        """Handle neutral/mixed feedback with small adjustments."""

        adjustments = {
            "too_brief": lambda: self.update_parameter(
                TuningParameter.DETAIL_LEVEL,
                min(1.0, self.config.detail_level + 0.1),
                reason="User feedback: too brief",
                confidence=0.5,
            ),
            "examples_helpful": lambda: self.update_parameter(
                TuningParameter.CODE_EXAMPLE_FREQUENCY,
                min(1.0, self.config.code_example_frequency + 0.15),
                reason="User feedback: examples helpful",
                confidence=0.6,
            ),
            "diagrams_useful": lambda: self.update_parameter(
                TuningParameter.DIAGRAM_FREQUENCY,
                min(1.0, self.config.diagram_frequency + 0.15),
                reason="User feedback: diagrams useful",
                confidence=0.6,
            ),
        }

        for keyword, adjustment in adjustments.items():
            if keyword in keywords:
                adjustment()

    def toggle_feature(self, feature_name: str, enabled: bool, reason: str = "") -> bool:
        """
        Toggle a feature on/off.

        Args:
            feature_name: Name of feature to toggle
            enabled: Whether to enable
            reason: Reason for toggle

        Returns:
            Success status
        """
        feature_mapping = {
            "cross_reference": "use_cross_reference",
            "knowledge_graph": "use_knowledge_graph",
            "decision_memory": "use_decision_memory",
            "artifacts": "use_artifacts",
        }

        attr_name = feature_mapping.get(feature_name)
        if attr_name and hasattr(self.config, attr_name):
            old_value = getattr(self.config, attr_name)
            setattr(self.config, attr_name, enabled)

            change = TuningChange(
                parameter=feature_name,
                old_value=old_value,
                new_value=enabled,
                reason=f"Feature toggle: {reason}",
                confidence=0.9,
            )
            self.change_history.append(change)

            self.config.last_modified = datetime.now().isoformat()
            self._save_config()
            self._save_history()

            logger.info(f"Toggled {feature_name}: {enabled}")
            return True

        return False

    def get_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate tuning recommendations based on history.

        Returns:
            List of recommendations
        """
        recommendations = []

        if not self.change_history:
            return recommendations

        # Analyze recent changes
        recent_changes = self.change_history[-10:]

        # Check for conflicting changes
        param_changes = {}
        for change in recent_changes:
            if change.parameter not in param_changes:
                param_changes[change.parameter] = []
            param_changes[change.parameter].append(change)

        for param, changes in param_changes.items():
            if len(changes) >= 3:
                # Multiple recent changes to same parameter - may be instability
                directions = [
                    1 if c.new_value > c.old_value else -1 for c in changes if isinstance(c.old_value, (int, float))
                ]
                if directions and directions != [directions[0]] * len(directions):
                    recommendations.append(
                        {
                            "type": "stability_warning",
                            "parameter": param,
                            "message": f"Parameter {param} is oscillating - may need manual adjustment",
                            "confidence": 0.7,
                        }
                    )

        # Check for underutilized features
        feature_usage = {}
        for change in recent_changes:
            if change.parameter.startswith("use_"):
                if change.parameter not in feature_usage:
                    feature_usage[change.parameter] = {"enabled": False, "changes": 0}
                feature_usage[change.parameter]["changes"] += 1
                feature_usage[change.parameter]["enabled"] = change.new_value

        for feature, usage in feature_usage.items():
            if usage["enabled"] and usage["changes"] > 2:
                recommendations.append(
                    {
                        "type": "feature_toggle",
                        "feature": feature,
                        "message": f"Feature {feature} was toggled frequently - may be problematic",
                        "confidence": 0.6,
                    }
                )

        return recommendations

    def get_current_config(self) -> Dict[str, Any]:
        """Get current tuning configuration."""
        return asdict(self.config)

    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        self.config = TuningConfig()
        self._save_config()
        logger.info("Reset tuning configuration to defaults")

    def export_tuning_report(self, format: str = "json") -> str:
        """
        Export tuning report.

        Args:
            format: json or markdown

        Returns:
            Formatted report
        """
        if format == "json":
            return json.dumps(
                {
                    "current_config": asdict(self.config),
                    "change_history": [asdict(c) for c in self.change_history[-20:]],
                    "recommendations": self.get_recommendations(),
                },
                indent=2,
                ensure_ascii=False,
            )

        elif format == "markdown":
            md = "# Behavior Tuning Report\n\n"
            md += f"**Generated**: {datetime.now().isoformat()}\n\n"

            md += "## Current Configuration\n"
            config = asdict(self.config)

            md += "### Response Parameters\n"
            md += f"- Max Length: {config['max_response_length']} chars\n"
            md += f"- Detail Level: {config['detail_level']}\n"
            md += f"- Code Examples: {config['code_example_frequency'] * 100:.0f}%\n"
            md += f"- Diagrams: {config['diagram_frequency'] * 100:.0f}%\n\n"

            md += "### Feature Toggles\n"
            for feature in [
                "use_cross_reference",
                "use_knowledge_graph",
                "use_decision_memory",
                "use_artifacts",
            ]:
                status = "✅" if config[feature] else "❌"
                md += f"- {feature}: {status}\n"

            md += "\n## Recent Changes\n"
            for change in self.change_history[-10:]:
                md += f"- {change.parameter}: {change.old_value} → {change.new_value}\n"
                md += f"  (Reason: {change.reason})\n"

            md += "\n## Recommendations\n"
            for rec in self.get_recommendations():
                md += f"- **{rec['type']}**: {rec['message']}\n"

            return md

        return ""
