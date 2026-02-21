"""
Adaptive Notification UI - Injects interactive artifacts into the web dashboard.

Instead of simple toast notifications, this system generates:
- Mermaid diagrams for network/system errors
- Interactive architecture visualizations
- Decision trees for error diagnosis
- Animated status indicators
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NotificationSeverity(Enum):
    """Severity levels for notifications."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    CRITICAL = "critical"
    DIAGNOSTIC = "diagnostic"  # For interactive diagnostics


class ArtifactType(Enum):
    """Types of interactive artifacts."""

    MERMAID_DIAGRAM = "mermaid_diagram"
    STATUS_TIMELINE = "status_timeline"
    DECISION_TREE = "decision_tree"
    METRIC_CARD = "metric_card"
    ACTION_LIST = "action_list"


@dataclass
class InteractiveArtifact:
    """Represents an interactive artifact to inject into the UI."""

    id: str
    type: ArtifactType
    title: str
    content: Dict[str, Any]
    severity: NotificationSeverity
    timestamp: str
    dismissible: bool = True
    auto_dismiss_after: Optional[int] = None  # Seconds, None = no auto-dismiss
    data: Optional[Dict[str, Any]] = None  # Additional metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "content": self.content,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "dismissible": self.dismissible,
            "auto_dismiss_after": self.auto_dismiss_after,
            "data": self.data or {},
        }


class AdaptiveNotificationUI:
    """
    Generates and manages interactive notifications with artifacts.

    Key features:
    - Create Mermaid diagrams for network/system errors
    - Generate status timelines
    - Build decision trees for troubleshooting
    - Inject directly into web UI via EventPublisher
    """

    def __init__(self):
        """Initialize the adaptive UI manager."""
        self.active_artifacts: Dict[str, InteractiveArtifact] = {}
        logger.info("AdaptiveNotificationUI initialized")

    def notify_network_error(
        self,
        service_name: str,
        error_message: str,
        failed_nodes: Optional[List[Dict[str, str]]] = None,
        recovery_actions: Optional[List[str]] = None,
    ) -> Optional[InteractiveArtifact]:
        """
        Create an interactive network error visualization.

        Args:
            service_name: Name of the affected service
            error_message: Error description
            failed_nodes: List of dicts with 'name' and 'status' for network nodes
            recovery_actions: Suggested recovery steps

        Returns:
            InteractiveArtifact: The created artifact
        """
        try:
            artifact_id = f"network_error_{datetime.now().timestamp()}"

            # Generate Mermaid diagram showing the failed network topology
            diagram = self._generate_network_diagram(service_name, failed_nodes or [])

            artifact = InteractiveArtifact(
                id=artifact_id,
                type=ArtifactType.MERMAID_DIAGRAM,
                title=f"🔗 Network Error: {service_name}",
                content={
                    "diagram": diagram,
                    "error": error_message,
                    "failed_nodes": failed_nodes or [],
                    "recovery": recovery_actions or [],
                },
                severity=NotificationSeverity.CRITICAL,
                timestamp=datetime.now().isoformat(),
                dismissible=True,
                auto_dismiss_after=None,  # Keep until user dismisses
            )

            self.active_artifacts[artifact_id] = artifact
            self._publish_artifact(artifact)
            logger.info(f"Network error artifact created: {artifact_id}")
            return artifact

        except Exception as e:
            logger.error(f"Failed to create network error artifact: {e}")
            return None

    def notify_system_status(
        self,
        status_type: str,
        metrics: Dict[str, float],
        threshold_breaches: Optional[List[str]] = None,
    ) -> Optional[InteractiveArtifact]:
        """
        Create a status card/metric visualization.

        Args:
            status_type: Type of status (cpu, memory, disk, etc.)
            metrics: Dictionary of metric names and values
            threshold_breaches: Metrics that have exceeded thresholds

        Returns:
            InteractiveArtifact: The created artifact
        """
        try:
            artifact_id = f"status_{status_type}_{datetime.now().timestamp()}"

            # Determine severity based on threshold breaches
            severity = NotificationSeverity.CRITICAL if threshold_breaches else NotificationSeverity.INFO

            artifact = InteractiveArtifact(
                id=artifact_id,
                type=ArtifactType.METRIC_CARD,
                title=f"📊 System Status: {status_type.title()}",
                content={
                    "metrics": metrics,
                    "breaches": threshold_breaches or [],
                    "recommendations": self._generate_recommendations(status_type, metrics, threshold_breaches or []),
                },
                severity=severity,
                timestamp=datetime.now().isoformat(),
                dismissible=True,
                auto_dismiss_after=60 if severity == NotificationSeverity.INFO else None,
            )

            self.active_artifacts[artifact_id] = artifact
            self._publish_artifact(artifact)
            logger.info(f"Status artifact created: {artifact_id}")
            return artifact

        except Exception as e:
            logger.error(f"Failed to create status artifact: {e}")
            return None

    def notify_decision_point(
        self,
        scenario: str,
        decision_context: Dict[str, Any],
        options: List[Dict[str, str]],
        recommended_action: str,
    ) -> Optional[InteractiveArtifact]:
        """
        Create an interactive decision tree for troubleshooting.

        Args:
            scenario: Description of the scenario
            decision_context: Context information for the decision
            options: List of dicts with 'label' and 'description'
            recommended_action: The recommended option

        Returns:
            InteractiveArtifact: The created artifact
        """
        try:
            artifact_id = f"decision_{datetime.now().timestamp()}"

            # Generate decision tree visualization
            tree = self._generate_decision_tree(options, recommended_action)

            artifact = InteractiveArtifact(
                id=artifact_id,
                type=ArtifactType.DECISION_TREE,
                title=f"🎯 Decision Required: {scenario}",
                content={
                    "scenario": scenario,
                    "context": decision_context,
                    "tree": tree,
                    "options": options,
                    "recommended": recommended_action,
                },
                severity=NotificationSeverity.WARNING,
                timestamp=datetime.now().isoformat(),
                dismissible=True,
                auto_dismiss_after=None,  # Requires user decision
            )

            self.active_artifacts[artifact_id] = artifact
            self._publish_artifact(artifact)
            logger.info(f"Decision tree artifact created: {artifact_id}")
            return artifact

        except Exception as e:
            logger.error(f"Failed to create decision tree artifact: {e}")
            return None

    def notify_diagnostic(
        self,
        problem: str,
        findings: List[str],
        diagnostic_diagram: Optional[str] = None,
    ) -> Optional[InteractiveArtifact]:
        """
        Create a diagnostic report with visual findings.

        Args:
            problem: Problem statement
            findings: List of diagnostic findings
            diagnostic_diagram: Optional Mermaid diagram of the problem

        Returns:
            InteractiveArtifact: The created artifact
        """
        try:
            artifact_id = f"diagnostic_{datetime.now().timestamp()}"

            artifact = InteractiveArtifact(
                id=artifact_id,
                type=ArtifactType.MERMAID_DIAGRAM,
                title=f"🔍 Diagnostic Report: {problem}",
                content={
                    "problem": problem,
                    "findings": findings,
                    "diagram": diagnostic_diagram or self._generate_default_diagnostic(),
                    "severity_indicators": self._classify_findings(findings),
                },
                severity=NotificationSeverity.DIAGNOSTIC,
                timestamp=datetime.now().isoformat(),
                dismissible=True,
                auto_dismiss_after=None,
            )

            self.active_artifacts[artifact_id] = artifact
            self._publish_artifact(artifact)
            logger.info(f"Diagnostic artifact created: {artifact_id}")
            return artifact

        except Exception as e:
            logger.error(f"Failed to create diagnostic artifact: {e}")
            return None

    def notify_recovery_plan(
        self,
        issue: str,
        recovery_steps: List[Dict[str, str]],
        estimated_time: Optional[int] = None,
    ) -> Optional[InteractiveArtifact]:
        """
        Create an interactive recovery plan.

        Args:
            issue: The issue being recovered from
            recovery_steps: List of dicts with 'step', 'description', 'command'
            estimated_time: Estimated recovery time in seconds

        Returns:
            InteractiveArtifact: The created artifact
        """
        try:
            artifact_id = f"recovery_{datetime.now().timestamp()}"

            artifact = InteractiveArtifact(
                id=artifact_id,
                type=ArtifactType.ACTION_LIST,
                title=f"🔧 Recovery Plan: {issue}",
                content={
                    "issue": issue,
                    "steps": recovery_steps,
                    "estimated_time_seconds": estimated_time,
                    "timeline": self._generate_timeline(recovery_steps, estimated_time),
                },
                severity=NotificationSeverity.WARNING,
                timestamp=datetime.now().isoformat(),
                dismissible=True,
                auto_dismiss_after=None,
            )

            self.active_artifacts[artifact_id] = artifact
            self._publish_artifact(artifact)
            logger.info(f"Recovery plan artifact created: {artifact_id}")
            return artifact

        except Exception as e:
            logger.error(f"Failed to create recovery plan artifact: {e}")
            return None

    # ==================== Artifact Generation Methods ====================

    def _generate_network_diagram(self, service_name: str, failed_nodes: List[Dict[str, str]]) -> str:
        """Generate a Mermaid diagram of network topology with failed nodes highlighted."""
        nodes = [
            f"{service_name} Service",
            "Load Balancer",
            "Primary Node",
            "Secondary Node",
            "Cache Layer",
            "Database",
        ]

        diagram_lines = ["graph TD"]

        # Add nodes with status colors
        for i, node in enumerate(nodes):
            is_failed = any(fn["name"] in node for fn in failed_nodes)
            if is_failed:
                diagram_lines.append(f"    N{i}[{node}]:::failed")
            else:
                diagram_lines.append(f"    N{i}[{node}]:::healthy")

        # Add connections
        diagram_lines.extend(
            [
                "    N0 --> N1",
                "    N1 --> N2",
                "    N1 --> N3",
                "    N2 --> N4",
                "    N2 --> N5",
                "    N3 --> N5",
                "    classDef healthy fill:#10b981,stroke:#059669,stroke-width:2px,color:#fff",
                "    classDef failed fill:#ef4444,stroke:#dc2626,stroke-width:3px,color:#fff",
            ]
        )

        return "\n".join(diagram_lines)

    def _generate_decision_tree(self, options: List[Dict[str, str]], recommended: str) -> str:
        """Generate a Mermaid diagram of decision tree."""
        diagram_lines = ["graph TD", "    Decision{Troubleshooting}:::decision"]

        for i, option in enumerate(options):
            label = option.get("label", f"Option {i + 1}")
            is_recommended = label == recommended
            style = ":::recommended" if is_recommended else ":::option"
            diagram_lines.append(f"    Option{i}[{label}]{style}")
            diagram_lines.append(f"    Decision -->|Option {i + 1}| Option{i}")

        diagram_lines.extend(
            [
                "    classDef decision fill:#6366f1,stroke:#4f46e5,stroke-width:2px,color:#fff",
                "    classDef option fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:#fff",
                "    classDef recommended fill:#10b981,stroke:#059669,stroke-width:3px,color:#fff",
            ]
        )

        return "\n".join(diagram_lines)

    def _generate_default_diagnostic(self) -> str:
        """Generate a basic diagnostic diagram."""
        return """graph TD
    A[Problem Detected]:::warning
    B{Root Cause Analysis}:::decision
    C[Symptom Analysis]:::info
    D[Impact Assessment]:::info
    B -->|Low Impact| C
    B -->|High Impact| D
    classDef warning fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff
    classDef decision fill:#6366f1,stroke:#4f46e5,stroke-width:2px,color:#fff
    classDef info fill:#3b82f6,stroke:#1d4ed8,stroke-width:2px,color:#fff
"""

    def _generate_timeline(
        self, steps: List[Dict[str, str]], estimated_total_time: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Generate a timeline from recovery steps."""
        timeline = []
        for i, step in enumerate(steps):
            timeline.append(
                {
                    "order": i + 1,
                    "step": step.get("step", f"Step {i + 1}"),
                    "description": step.get("description", ""),
                    "command": step.get("command", ""),
                    "estimated_duration_seconds": estimated_total_time // len(steps) if estimated_total_time else None,
                }
            )
        return timeline

    def _generate_recommendations(self, status_type: str, metrics: Dict[str, float], breaches: List[str]) -> List[str]:
        """Generate recommendations based on system status."""
        recommendations = []

        if "cpu" in status_type.lower():
            if any("cpu" in b.lower() for b in breaches):
                recommendations.append("Consider stopping non-essential processes")
                recommendations.append("Check for runaway processes consuming CPU")

        if "memory" in status_type.lower():
            if any("memory" in b.lower() for b in breaches):
                recommendations.append("Clear cache and temporary files")
                recommendations.append("Increase allocated memory if possible")

        if "disk" in status_type.lower():
            if any("disk" in b.lower() for b in breaches):
                recommendations.append("Delete old logs and temporary files")
                recommendations.append("Archive or remove unused data")

        return recommendations or ["System operating normally"]

    def _classify_findings(self, findings: List[str]) -> Dict[str, int]:
        """Classify findings by severity."""
        severity_keywords = {
            "critical": ["error", "failed", "critical"],
            "warning": ["warning", "slow", "unusual"],
            "info": ["info", "note", "observation"],
        }

        counts = {"critical": 0, "warning": 0, "info": 0}
        for finding in findings:
            lower_finding = finding.lower()
            for severity, keywords in severity_keywords.items():
                if any(kw in lower_finding for kw in keywords):
                    counts[severity] += 1
                    break

        return counts

    def _publish_artifact(self, artifact: InteractiveArtifact) -> bool:
        """Publish artifact to the web UI via EventPublisher."""
        try:
            from backend.utils.core.system.event_publisher import EventPublisher

            publisher = EventPublisher()

            # Publish to UI artifacts channel
            publisher.publish("ui_artifact", artifact.to_dict())
            logger.debug(f"Artifact published: {artifact.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish artifact: {e}")
            return False

    def dismiss_artifact(self, artifact_id: str) -> bool:
        """Dismiss/remove an artifact from the UI."""
        if artifact_id in self.active_artifacts:
            del self.active_artifacts[artifact_id]
            logger.info(f"Artifact dismissed: {artifact_id}")
            return True
        return False

    def get_active_artifacts(self) -> List[Dict[str, Any]]:
        """Get all currently active artifacts."""
        return [artifact.to_dict() for artifact in self.active_artifacts.values()]

    def clear_artifacts_by_severity(self, severity: NotificationSeverity) -> int:
        """Clear artifacts matching a specific severity level."""
        to_remove = [aid for aid, artifact in self.active_artifacts.items() if artifact.severity == severity]
        for aid in to_remove:
            del self.active_artifacts[aid]
        logger.info(f"Cleared {len(to_remove)} artifacts with severity {severity.value}")
        return len(to_remove)


# Global instance
_adaptive_ui = None


def get_adaptive_notification_ui() -> AdaptiveNotificationUI:
    """Get or create the global adaptive UI instance."""
    global _adaptive_ui
    if _adaptive_ui is None:
        _adaptive_ui = AdaptiveNotificationUI()
    return _adaptive_ui
