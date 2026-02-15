"""
Feedback Cycle Manager - Learn writing style from user corrections.

Builds on FeedbackRefinementManager to:
- Capture user feedback on generated content
- Extract style preferences (verbosity, technical level, tone)
- Build a style profile over time
- Apply learned preferences to future outputs
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of feedback."""

    CLARITY = "clarity"
    CONCISENESS = "conciseness"
    TECHNICAL_LEVEL = "technical_level"
    TONE = "tone"
    ORGANIZATION = "organization"
    COMPLETENESS = "completeness"
    ACCURACY = "accuracy"
    STYLE = "style"


class StyleDimension(Enum):
    """Dimensions of writing style."""

    VERBOSITY = "verbosity"  # Concise vs Detailed
    TECHNICAL_LEVEL = "technical_level"  # Simple vs Technical
    TONE = "tone"  # Formal vs Casual
    ORGANIZATION = "organization"  # Structure preference
    DEPTH = "depth"  # Surface vs Deep


@dataclass
class FeedbackRecord:
    """Single feedback instance."""

    id: str
    timestamp: str
    content_id: str  # ID of content being reviewed
    content_excerpt: str  # Sample of the content
    feedback_type: FeedbackType
    feedback_text: str
    severity: str  # "minor", "moderate", "major"
    suggested_correction: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StylePreference:
    """Learned style preference."""

    dimension: StyleDimension
    value: float  # 0-100, where 0 = left extreme, 100 = right extreme
    confidence: float  # 0-100 how confident we are in this preference
    examples: List[str]  # Content examples showing this preference
    last_updated: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeedbackCycleManager:
    """
    Manages iterative feedback cycles for content refinement.

    The cycle works as follows:
    1. Generate content → Agent produces text/report
    2. Collect Feedback → User provides corrections
    3. Extract Preferences → Analyze patterns in feedback
    4. Update Profile → Adjust style preferences
    5. Apply to Next → Use learned preferences in future content

    This creates a continuous learning loop.
    """

    def __init__(self, project_root: Path, config: Optional[Dict] = None):
        """
        Initialize the feedback cycle manager.

        Args:
            project_root: Root path for storing feedback data
            config: Optional configuration
        """
        self.project_root = project_root
        self.config = config or {}

        # Storage
        self.feedback_file = project_root / ".feedback_history.json"
        self.style_profile_file = project_root / ".style_profile.json"

        # In-memory caches
        self.feedback_history: List[FeedbackRecord] = []
        self.style_profile: Dict[str, StylePreference] = {}

        # Statistics
        self.feedback_stats = {"total_feedback": 0, "by_type": {}, "by_severity": {}}

        self._load_profile()
        logger.info("FeedbackCycleManager initialized")

    def submit_feedback(
        self,
        content_id: str,
        content_excerpt: str,
        feedback_type: FeedbackType,
        feedback_text: str,
        severity: str = "moderate",
        suggested_correction: Optional[str] = None,
    ) -> FeedbackRecord:
        """
        Submit feedback on generated content.

        Args:
            content_id: ID of the content being reviewed
            content_excerpt: Sample of the content (for context)
            feedback_type: Type of feedback
            feedback_text: The actual feedback
            severity: How important is this feedback
            suggested_correction: Optional suggested fix

        Returns:
            FeedbackRecord: The recorded feedback
        """
        try:
            record = FeedbackRecord(
                id=f"feedback_{datetime.now().timestamp()}",
                timestamp=datetime.now().isoformat(),
                content_id=content_id,
                content_excerpt=content_excerpt,
                feedback_type=feedback_type,
                feedback_text=feedback_text,
                severity=severity,
                suggested_correction=suggested_correction,
            )

            self.feedback_history.append(record)

            # Update statistics
            self._update_feedback_stats(feedback_type, severity)

            # Extract preference patterns
            self._extract_preferences_from_feedback(record)

            logger.info(
                f"Feedback recorded: {feedback_type.value} - {severity} severity"
            )

            return record

        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}")
            raise

    def get_style_profile(self) -> Dict[str, StylePreference]:
        """
        Get the current learned style profile.

        Returns:
            Dict: Style preferences by dimension
        """
        return self.style_profile.copy()

    def get_style_recommendation(self) -> Dict[str, Any]:
        """
        Get a style recommendation to apply to next content.

        Returns:
            Dict: Recommended style parameters
        """
        try:
            recommendation = {}

            for dimension, preference in self.style_profile.items():
                # Only include high-confidence preferences
                if preference.confidence >= 60:
                    recommendation[dimension] = {
                        "value": preference.value,
                        "confidence": preference.confidence,
                        "recommendation": self._value_to_recommendation(
                            dimension, preference.value
                        ),
                    }

            return recommendation

        except Exception as e:
            logger.error(f"Failed to get style recommendation: {e}")
            return {}

    def apply_style_preferences(
        self, content: str, style_recommendations: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Apply learned style preferences to content.

        Args:
            content: The content to adjust
            style_recommendations: Optional specific recommendations

        Returns:
            str: Content adjusted to match learned preferences
        """
        try:
            if not style_recommendations:
                style_recommendations = self.get_style_recommendation()

            if not style_recommendations:
                return content  # No preferences learned yet

            adjusted = content

            # Apply each style preference
            for dimension, recommendation in style_recommendations.items():
                if recommendation["confidence"] < 60:
                    continue

                if dimension == StyleDimension.VERBOSITY.value:
                    adjusted = self._adjust_verbosity(
                        adjusted, int(recommendation["value"])
                    )
                elif dimension == StyleDimension.TECHNICAL_LEVEL.value:
                    adjusted = self._adjust_technical_level(
                        adjusted, int(recommendation["value"])
                    )
                elif dimension == StyleDimension.TONE.value:
                    adjusted = self._adjust_tone(adjusted, int(recommendation["value"]))

            logger.info("Style preferences applied to content")
            return adjusted

        except Exception as e:
            logger.error(f"Failed to apply style preferences: {e}")
            return content

    def get_feedback_trends(self, days: int = 30) -> Dict[str, Any]:
        """
        Get trends in feedback over time.

        Args:
            days: Number of days to analyze

        Returns:
            Dict: Feedback trends
        """
        try:
            cutoff = datetime.now() - timedelta(days=days)
            recent_feedback = [
                f
                for f in self.feedback_history
                if datetime.fromisoformat(f.timestamp) >= cutoff
            ]

            if not recent_feedback:
                return {
                    "period_days": days,
                    "feedback_count": 0,
                    "top_issues": [],
                    "improvement_areas": [],
                }

            # Calculate top feedback types
            by_type = {}
            for f in recent_feedback:
                ft = f.feedback_type.value
                by_type[ft] = by_type.get(ft, 0) + 1

            # Calculate severity distribution
            by_severity = {}
            for f in recent_feedback:
                by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

            return {
                "period_days": days,
                "feedback_count": len(recent_feedback),
                "top_issues": sorted(by_type.items(), key=lambda x: x[1], reverse=True),
                "severity_distribution": by_severity,
                "improvement_areas": self._identify_improvement_areas(recent_feedback),
            }

        except Exception as e:
            logger.error(f"Failed to get feedback trends: {e}")
            return {}

    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get a summary of all feedback."""
        try:
            if not self.feedback_history:
                return {
                    "total_feedback": 0,
                    "top_issues": [],
                    "style_profile_confidence": 0.0,
                }

            by_type = {}
            for f in self.feedback_history:
                ft = f.feedback_type.value
                by_type[ft] = by_type.get(ft, 0) + 1

            avg_confidence = (
                sum(p.confidence for p in self.style_profile.values())
                / len(self.style_profile)
                if self.style_profile
                else 0.0
            )

            return {
                "total_feedback": len(self.feedback_history),
                "by_type": by_type,
                "top_issues": sorted(by_type.items(), key=lambda x: x[1], reverse=True)[
                    :5
                ],
                "style_profile": {
                    k: v.to_dict() for k, v in self.style_profile.items()
                },
                "profile_confidence": avg_confidence,
            }

        except Exception as e:
            logger.error(f"Failed to get feedback summary: {e}")
            return {}

    def refine_content_based_on_feedback(
        self, content: str, recent_feedback_limit: int = 5
    ) -> str:
        """
        Refine content based on recent feedback patterns.

        Args:
            content: Content to refine
            recent_feedback_limit: How many recent feedback items to consider

        Returns:
            str: Refined content
        """
        try:
            # Get most recent relevant feedback
            relevant_feedback = self.feedback_history[-recent_feedback_limit:]

            if not relevant_feedback:
                return content

            refined = content

            # Apply common corrections
            for feedback in relevant_feedback:
                if feedback.suggested_correction:
                    # Simple keyword replacement - in production, more sophisticated
                    refined = self._apply_feedback_correction(refined, feedback)

            return refined

        except Exception as e:
            logger.error(f"Failed to refine content: {e}")
            return content

    # ==================== Private Methods ====================

    def _extract_preferences_from_feedback(self, feedback: FeedbackRecord) -> None:
        """Extract style preferences from feedback."""

        # Map feedback types to style dimensions
        type_to_dimension = {
            FeedbackType.CONCISENESS: StyleDimension.VERBOSITY,
            FeedbackType.TECHNICAL_LEVEL: StyleDimension.TECHNICAL_LEVEL,
            FeedbackType.TONE: StyleDimension.TONE,
            FeedbackType.ORGANIZATION: StyleDimension.ORGANIZATION,
            FeedbackType.CLARITY: StyleDimension.VERBOSITY,  # Clarity often means less verbose
        }

        if feedback.feedback_type not in type_to_dimension:
            return

        dimension = type_to_dimension[feedback.feedback_type]
        dimension_key = dimension.value

        # Analyze feedback text to infer preference direction
        preference_value = self._infer_style_value(feedback)
        confidence = self._calculate_feedback_confidence(feedback.severity)

        # Update or create preference
        if dimension_key in self.style_profile:
            # Update existing preference with weighted average
            existing = self.style_profile[dimension_key]
            new_value = (
                existing.value * existing.confidence + preference_value * confidence
            ) / (existing.confidence + confidence)

            new_confidence = min(existing.confidence + confidence * 10, 100)

            existing.value = new_value
            existing.confidence = new_confidence
            existing.examples.append(feedback.content_id)
            existing.last_updated = datetime.now().isoformat()
        else:
            # Create new preference
            self.style_profile[dimension_key] = StylePreference(
                dimension=dimension,
                value=preference_value,
                confidence=confidence,
                examples=[feedback.content_id],
                last_updated=datetime.now().isoformat(),
            )

    def _infer_style_value(self, feedback: FeedbackRecord) -> float:
        """Infer style value (0-100) from feedback content."""
        text_lower = feedback.feedback_text.lower()

        # Keywords indicating preference for more concise
        concise_keywords = ["verbose", "too long", "brevity", "too detailed", "wordy"]
        # Keywords indicating preference for more detailed
        detailed_keywords = [
            "too brief",
            "explain more",
            "more detail",
            "expand on",
            "missing",
        ]
        # Keywords for more technical
        technical_keywords = [
            "too simple",
            "technical",
            "jargon",
            "acronym",
            "include code",
        ]
        # Keywords for less technical
        simple_keywords = [
            "too technical",
            "simplify",
            "non-technical",
            "layman",
            "explain",
        ]

        if any(kw in text_lower for kw in concise_keywords):
            return 20.0  # Prefer conciseness
        elif any(kw in text_lower for kw in detailed_keywords):
            return 80.0  # Prefer detail
        elif any(kw in text_lower for kw in technical_keywords):
            return 80.0  # Prefer technical
        elif any(kw in text_lower for kw in simple_keywords):
            return 20.0  # Prefer simplicity

        return 50.0  # Neutral

    def _calculate_feedback_confidence(self, severity: str) -> float:
        """Calculate confidence weight from feedback severity."""
        weights = {"minor": 10.0, "moderate": 30.0, "major": 50.0}
        return weights.get(severity, 20.0)

    def _update_feedback_stats(
        self, feedback_type: FeedbackType, severity: str
    ) -> None:
        """Update feedback statistics."""
        self.feedback_stats["total_feedback"] += 1

        ft = feedback_type.value
        self.feedback_stats["by_type"][ft] = (
            self.feedback_stats["by_type"].get(ft, 0) + 1
        )

        self.feedback_stats["by_severity"][severity] = (
            self.feedback_stats["by_severity"].get(severity, 0) + 1
        )

    def _adjust_verbosity(self, content: str, value: int) -> str:
        """Adjust content verbosity."""
        if value < 40:  # Concise preference
            # Remove redundant words and shorten sentences
            redundant_patterns = [
                (r"very\s+", ""),
                (r"in order to\s+", "to "),
                (r"due to the fact that\s+", "because "),
            ]
            adjusted = content
            import re

            for pattern, replacement in redundant_patterns:
                adjusted = re.sub(pattern, replacement, adjusted, flags=re.IGNORECASE)
            return adjusted

        return content

    def _adjust_technical_level(self, content: str, value: int) -> str:
        """Adjust technical level of content."""
        if value > 70:  # Technical preference
            # This would add more technical details (simplified approach)
            pass
        elif value < 30:  # Simple preference
            # Remove or explain technical terms
            pass

        return content

    def _adjust_tone(self, content: str, value: int) -> str:
        """Adjust tone of content."""
        # Implementation would depend on tone scale definition
        return content

    def _value_to_recommendation(self, dimension: str, value: float) -> str:
        """Convert numeric value to human-readable recommendation."""
        if dimension == StyleDimension.VERBOSITY.value:
            if value < 40:
                return "Keep it concise and brief"
            elif value > 70:
                return "Provide detailed explanations"
            else:
                return "Balanced detail level"
        elif dimension == StyleDimension.TECHNICAL_LEVEL.value:
            if value < 40:
                return "Use simple, non-technical language"
            elif value > 70:
                return "Use technical depth with examples"
            else:
                return "Intermediate technical level"

        return f"Preference value: {value}"

    def _identify_improvement_areas(
        self, feedback_list: List[FeedbackRecord]
    ) -> List[str]:
        """Identify areas needing improvement."""
        areas = {}

        for f in feedback_list:
            area = f.feedback_type.value
            areas[area] = areas.get(area, 0) + 1

        # Return top 3 areas by frequency
        return [
            area
            for area, count in sorted(areas.items(), key=lambda x: x[1], reverse=True)[
                :3
            ]
        ]

    def _apply_feedback_correction(self, content: str, feedback: FeedbackRecord) -> str:
        """Apply a specific feedback correction."""
        if feedback.suggested_correction:
            # Simple approach: look for similar text and replace

            excerpt = feedback.content_excerpt
            if excerpt in content:
                return content.replace(excerpt, feedback.suggested_correction)

        return content

    def _load_profile(self) -> None:
        """Load style profile from persistent storage."""
        try:
            if self.feedback_file.exists():
                with open(self.feedback_file) as f:
                    feedback_data = json.load(f)
                    # Reconstruct feedback records
                    for item in feedback_data:
                        item["feedback_type"] = FeedbackType(item["feedback_type"])
                        # Convert back to FeedbackRecord

            if self.style_profile_file.exists():
                with open(self.style_profile_file) as f:
                    profile_data = json.load(f)
                    for key, data in profile_data.items():
                        data["dimension"] = StyleDimension(data["dimension"])
                        self.style_profile[key] = StylePreference(**data)

            logger.info("Style profile loaded from disk")

        except Exception as e:
            logger.warning(f"Failed to load style profile: {e}")

    def save(self) -> bool:
        """Save feedback history and profile to persistent storage."""
        try:
            # Save feedback history
            feedback_data = [
                {**f.to_dict(), "feedback_type": f.feedback_type.value}
                for f in self.feedback_history
            ]
            with open(self.feedback_file, "w") as f:
                json.dump(feedback_data, f, indent=2)

            # Save style profile
            profile_data = {
                k: {**v.to_dict(), "dimension": v.dimension.value}
                for k, v in self.style_profile.items()
            }
            with open(self.style_profile_file, "w") as f:
                json.dump(profile_data, f, indent=2)

            logger.info("Feedback cycle data saved to disk")
            return True

        except Exception as e:
            logger.error(f"Failed to save feedback cycle data: {e}")
            return False


# Global instance
_feedback_cycle_manager = None


def get_feedback_cycle_manager(
    project_root: Optional[Path] = None,
) -> FeedbackCycleManager:
    """Get or create the global feedback cycle manager instance."""
    global _feedback_cycle_manager
    if _feedback_cycle_manager is None:
        if project_root is None:
            from pathlib import Path

            project_root = Path.cwd()
        _feedback_cycle_manager = FeedbackCycleManager(project_root)
    return _feedback_cycle_manager
