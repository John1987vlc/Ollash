"""Blueprint for Model Cost Analyzer (F8)."""

import logging

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

cost_bp = Blueprint("cost_bp", __name__, url_prefix="/api/costs")

_cost_analyzer = None


def init_app(app):
    """Initialize cost analyzer blueprint."""
    global _cost_analyzer
    try:
        from backend.utils.core.cost_analyzer import CostAnalyzer
        from backend.core.containers import main_container

        _cost_analyzer = CostAnalyzer(
            token_tracker=None,
            llm_config=main_container.auto_agent_module.llm_models_config(),
            logger=main_container.core.logger(),
        )
        logger.info("Cost analyzer initialized")
    except Exception as e:
        logger.warning(f"Cost analyzer init skipped: {e}")


@cost_bp.route("/report", methods=["GET"])
def get_cost_report():
    """Get cost report."""
    if not _cost_analyzer:
        return jsonify({"error": "Cost analyzer not available"}), 503

    try:
        report = _cost_analyzer.get_report()
        return jsonify({"report": report.to_dict() if hasattr(report, "to_dict") else report})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cost_bp.route("/suggestions", methods=["GET"])
def get_suggestions():
    """Get model downgrade suggestions."""
    if not _cost_analyzer:
        return jsonify({"suggestions": []})

    try:
        suggestions = _cost_analyzer.suggest_downgrades()
        return jsonify({"suggestions": [s.to_dict() if hasattr(s, "to_dict") else s for s in suggestions]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
