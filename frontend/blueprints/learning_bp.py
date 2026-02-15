"""
Flask Blueprint for Phase 3: Learning & Memory APIs

Exposes preference management, pattern analysis, and behavior tuning
through REST endpoints.

Endpoints:
- /api/learning/preferences/* - User preference management
- /api/learning/patterns/* - Pattern analysis and insights
- /api/learning/tuning/* - Behavior tuning and auto-adjustment
- /api/learning/feedback/* - Feedback recording and analysis
"""

import json
import logging
from pathlib import Path
from typing import Tuple

from flask import Blueprint, jsonify, request

from backend.utils.core.behavior_tuner import BehaviorTuner, TuningParameter
from backend.utils.core.pattern_analyzer import PatternAnalyzer, SentimentType
from backend.utils.core.preference_manager_extended import (
    CommunicationStyle, ComplexityLevel, PreferenceManagerExtended)

logger = logging.getLogger(__name__)
learning_bp = Blueprint("learning", __name__, url_prefix="/api/learning")


def init_app(app):
    """Initialize learning blueprint."""
    logger.info("Learning blueprint initialized")
    pass


def get_learning_managers() -> (
    Tuple[PreferenceManagerExtended, PatternAnalyzer, BehaviorTuner]
):
    """
    Get or create learning managers (cached in app context).

    Returns:
        Tuple of (preference_manager, pattern_analyzer, behavior_tuner)
    """
    from flask import current_app

    workspace_root = Path.cwd()

    if not hasattr(current_app, "_learning_managers"):
        current_app._learning_managers = {
            "preferences": PreferenceManagerExtended(workspace_root),
            "patterns": PatternAnalyzer(workspace_root),
            "tuning": BehaviorTuner(workspace_root),
        }

    return (
        current_app._learning_managers["preferences"],
        current_app._learning_managers["patterns"],
        current_app._learning_managers["tuning"],
    )


# ============================================================================
# PREFERENCE MANAGEMENT ENDPOINTS
# ============================================================================


@learning_bp.route("/preferences/profile/<user_id>", methods=["GET"])
def get_preference_profile(user_id: str):
    """
    Get user preference profile.

    Args:
        user_id: User identifier

    Returns:
        User preference profile with all settings
    """
    try:
        pref_mgr, _, _ = get_learning_managers()
        profile = pref_mgr.get_profile(user_id)

        return jsonify(
            {
                "status": "success",
                "profile": {
                    "user_id": profile.user_id,
                    "communication": {
                        "style": profile.communication.style.value,
                        "complexity": profile.communication.complexity.value,
                        "preferences": [
                            p.value for p in profile.communication.interaction_prefs
                        ],
                        "use_examples": profile.communication.use_examples,
                        "use_visuals": profile.communication.use_visuals,
                    },
                    "statistics": {
                        "total_interactions": profile.total_interactions,
                        "positive_feedback": profile.positive_feedback_count,
                        "negative_feedback": profile.negative_feedback_count,
                    },
                    "learned_keywords": profile.learned_keywords[-10:],
                    "frequently_used_commands": profile.frequently_used_commands[-10:],
                },
            }
        )
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/preferences/profile/<user_id>", methods=["PUT"])
def update_preference_profile(user_id: str):
    """
    Update user preference profile.

    Request body:
    {
        "style": "concise|detailed|formal|casual|technical|conversational",
        "complexity": "beginner|intermediate|expert",
        "use_examples": true,
        "use_visuals": true,
        "max_response_length": 2000
    }
    """
    try:
        data = request.get_json()
        pref_mgr, _, _ = get_learning_managers()

        style = None
        if "style" in data:
            style = CommunicationStyle(data["style"])

        complexity = None
        if "complexity" in data:
            complexity = ComplexityLevel(data["complexity"])

        # Extract other kwargs
        kwargs = {k: v for k, v in data.items() if k not in ["style", "complexity"]}

        profile = pref_mgr.update_communication_style(
            user_id, style=style, complexity=complexity, **kwargs
        )

        return jsonify(
            {
                "status": "success",
                "message": f"Updated preferences for {user_id}",
                "style": profile.communication.style.value,
                "complexity": profile.communication.complexity.value,
            }
        )
    except ValueError as e:
        return jsonify({"status": "error", "message": f"Invalid value: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/preferences/recommendations/<user_id>", methods=["GET"])
def get_preference_recommendations(user_id: str):
    """
    Get recommendations for preference adjustments.

    Args:
        user_id: User identifier

    Returns:
        Recommendations for style/complexity adjustments
    """
    try:
        pref_mgr, _, _ = get_learning_managers()
        recommendations = pref_mgr.get_recommendations(user_id)

        return jsonify(
            {
                "status": "success",
                "recommendations": recommendations,
                "user_id": user_id,
            }
        )
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/preferences/export/<user_id>", methods=["GET"])
def export_preference_profile(user_id: str):
    """
    Export user preference profile.

    Query args:
        format: json or markdown
    """
    try:
        format_type = request.args.get("format", "json")
        pref_mgr, _, _ = get_learning_managers()

        exported = pref_mgr.export_profile(user_id, format_type)

        return jsonify(
            {"status": "success", "format": format_type, "content": exported}
        )
    except Exception as e:
        logger.error(f"Error exporting profile: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# PATTERN ANALYSIS ENDPOINTS
# ============================================================================


@learning_bp.route("/feedback/record", methods=["POST"])
def record_feedback():
    """
    Record user feedback for pattern analysis.

    Request body:
    {
        "user_id": "user123",
        "task_type": "analysis|artifact_creation|decision_recording",
        "sentiment": "positive|neutral|negative",
        "score": 4,
        "comment": "Great results",
        "keywords": ["fast", "accurate"],
        "affected_component": "cross_reference",
        "resolution_time": 2.5
    }
    """
    try:
        data = request.get_json()
        _, pattern_analyzer, behavior_tuner = get_learning_managers()

        entry = pattern_analyzer.record_feedback(
            user_id=data.get("user_id", "unknown"),
            task_type=data.get("task_type", "general"),
            sentiment=data.get("sentiment", SentimentType.NEUTRAL),
            score=data.get("score", 3.0),
            comment=data.get("comment", ""),
            keywords=data.get("keywords", []),
            affected_component=data.get("affected_component", ""),
            resolution_time=data.get("resolution_time", 0.0),
        )

        # Auto-adapt behavior based on feedback
        behavior_tuner.adapt_to_feedback(
            entry.score, data.get("task_type"), keywords=data.get("keywords", [])
        )

        return jsonify(
            {
                "status": "success",
                "message": "Feedback recorded",
                "entry_timestamp": entry.timestamp,
            }
        )
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/patterns/insights", methods=["GET"])
def get_pattern_insights():
    """
    Get overall pattern insights from feedback.

    Returns:
        Aggregated insights and metrics
    """
    try:
        _, pattern_analyzer, _ = get_learning_managers()
        insights = pattern_analyzer.get_insights()

        return jsonify({"status": "success", "insights": insights})
    except Exception as e:
        logger.error(f"Error getting insights: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/patterns/detected", methods=["GET"])
def get_detected_patterns():
    """
    Get detected patterns.

    Query args:
        type: success|failure|inefficiency
        confidence: 0.0-1.0 (default 0.5)
        limit: max results (default 10)
    """
    try:
        pattern_type = request.args.get("type", None)
        min_confidence = float(request.args.get("confidence", 0.5))
        limit = int(request.args.get("limit", 10))

        _, pattern_analyzer, _ = get_learning_managers()
        patterns = pattern_analyzer.get_patterns(
            pattern_type=pattern_type, min_confidence=min_confidence, limit=limit
        )

        return jsonify(
            {
                "status": "success",
                "patterns": [
                    {
                        "pattern_id": p.pattern_id,
                        "type": p.pattern_type,
                        "description": p.description,
                        "confidence": p.confidence,
                        "frequency": p.frequency,
                        "recommendations": p.recommendations,
                    }
                    for p in patterns
                ],
            }
        )
    except Exception as e:
        logger.error(f"Error getting patterns: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/patterns/component-health/<component>", methods=["GET"])
def get_component_health(component: str):
    """
    Get health status of specific component.

    Args:
        component: Component name

    Returns:
        Health metrics and feedback summary
    """
    try:
        _, pattern_analyzer, _ = get_learning_managers()
        health = pattern_analyzer.get_component_health(component)

        return jsonify({"status": "success", "component": component, "health": health})
    except Exception as e:
        logger.error(f"Error getting health: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/patterns/report", methods=["GET"])
def export_pattern_report():
    """
    Export pattern analysis report.

    Query args:
        format: json or markdown
    """
    try:
        format_type = request.args.get("format", "json")
        _, pattern_analyzer, _ = get_learning_managers()

        report = pattern_analyzer.export_report(format_type)

        return jsonify({"status": "success", "format": format_type, "content": report})
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# BEHAVIOR TUNING ENDPOINTS
# ============================================================================


@learning_bp.route("/tuning/config", methods=["GET"])
def get_tuning_config():
    """
    Get current behavior tuning configuration.

    Returns:
        Current tuning parameters
    """
    try:
        _, _, behavior_tuner = get_learning_managers()
        config = behavior_tuner.get_current_config()

        return jsonify({"status": "success", "config": config})
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/tuning/update", methods=["POST"])
def update_tuning_parameter():
    """
    Update a tuning parameter.

    Request body:
    {
        "parameter": "response_length|detail_level|code_example_frequency|...",
        "new_value": 1500,
        "reason": "User feedback: responses too long",
        "confidence": 0.8
    }
    """
    try:
        data = request.get_json()
        _, _, behavior_tuner = get_learning_managers()

        param = TuningParameter(data["parameter"])
        success = behavior_tuner.update_parameter(
            parameter=param,
            new_value=data["new_value"],
            reason=data.get("reason", ""),
            confidence=data.get("confidence", 0.5),
        )

        return jsonify(
            {
                "status": "success" if success else "error",
                "parameter": data["parameter"],
                "updated": success,
            }
        )
    except ValueError as e:
        return (
            jsonify({"status": "error", "message": f"Invalid parameter: {str(e)}"}),
            400,
        )
    except Exception as e:
        logger.error(f"Error updating parameter: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/tuning/feature-toggle", methods=["POST"])
def toggle_feature():
    """
    Toggle a feature on/off.

    Request body:
    {
        "feature": "cross_reference|knowledge_graph|decision_memory|artifacts",
        "enabled": true,
        "reason": "Reducing latency"
    }
    """
    try:
        data = request.get_json()
        _, _, behavior_tuner = get_learning_managers()

        success = behavior_tuner.toggle_feature(
            feature_name=data["feature"],
            enabled=data["enabled"],
            reason=data.get("reason", ""),
        )

        return jsonify(
            {
                "status": "success" if success else "error",
                "feature": data["feature"],
                "enabled": data["enabled"],
                "toggled": success,
            }
        )
    except Exception as e:
        logger.error(f"Error toggling feature: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/tuning/recommendations", methods=["GET"])
def get_tuning_recommendations():
    """
    Get recommendations for behavior adjustments.

    Returns:
        List of tuning recommendations
    """
    try:
        _, _, behavior_tuner = get_learning_managers()
        recommendations = behavior_tuner.get_recommendations()

        return jsonify({"status": "success", "recommendations": recommendations})
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/tuning/reset", methods=["POST"])
def reset_tuning_config():
    """
    Reset tuning configuration to defaults.

    Returns:
        Confirmation of reset
    """
    try:
        _, _, behavior_tuner = get_learning_managers()
        behavior_tuner.reset_to_defaults()

        return jsonify(
            {"status": "success", "message": "Tuning configuration reset to defaults"}
        )
    except Exception as e:
        logger.error(f"Error resetting config: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route("/tuning/report", methods=["GET"])
def export_tuning_report():
    """
    Export tuning report.

    Query args:
        format: json or markdown
    """
    try:
        format_type = request.args.get("format", "json")
        _, _, behavior_tuner = get_learning_managers()

        report = behavior_tuner.export_tuning_report(format_type)

        return jsonify({"status": "success", "format": format_type, "content": report})
    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================================
# INTEGRATED ENDPOINTS
# ============================================================================


@learning_bp.route("/health-check", methods=["GET"])
def learning_health_check():
    """
    Health check for learning system.

    Returns:
        Status of all learning components
    """
    try:
        pref_mgr, pattern_analyzer, behavior_tuner = get_learning_managers()

        prefs_ok = pref_mgr.prefs_dir.exists()
        patterns_ok = pattern_analyzer.data_dir.exists()
        tuning_ok = behavior_tuner.tuning_dir.exists()

        return jsonify(
            {
                "status": "healthy"
                if all([prefs_ok, patterns_ok, tuning_ok])
                else "degraded",
                "components": {
                    "preferences": "ok" if prefs_ok else "error",
                    "patterns": "ok" if patterns_ok else "error",
                    "tuning": "ok" if tuning_ok else "error",
                },
                "timestamp": json.dumps({"timestamp": "2026-02-11T10:30:00"}),
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@learning_bp.route("/summary/<user_id>", methods=["GET"])
def get_learning_summary(user_id: str):
    """
    Get complete learning summary for a user.

    Combines preferences, patterns, and tuning info.

    Args:
        user_id: User identifier
    """
    try:
        pref_mgr, pattern_analyzer, behavior_tuner = get_learning_managers()

        profile = pref_mgr.get_profile(user_id)
        insights = pattern_analyzer.get_insights()
        config = behavior_tuner.get_current_config()

        return jsonify(
            {
                "status": "success",
                "user_id": user_id,
                "preferences": {
                    "style": profile.communication.style.value,
                    "complexity": profile.communication.complexity.value,
                    "interactions": profile.total_interactions,
                },
                "patterns": {
                    "detected": insights.get("detected_patterns", 0),
                    "critical": insights.get("critical_patterns", 0),
                    "average_score": insights.get("average_score", 0),
                },
                "tuning": {
                    "auto_tune_enabled": config.get("auto_tune_enabled", True),
                    "learning_rate": config.get("learning_rate", 0.1),
                    "response_length": config.get("max_response_length", 2000),
                },
            }
        )
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
