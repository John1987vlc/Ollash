"""Blueprint for CI/CD Auto-Healing (F7)."""

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

cicd_bp = Blueprint("cicd_bp", __name__, url_prefix="/api/cicd")

_healer = None


def init_app(app):
    """Initialize CI/CD blueprint."""
    global _healer
    try:
        from backend.utils.core.cicd_healer import CICDHealer
        from backend.core.containers import main_container

        _healer = CICDHealer(
            llm_client=main_container.auto_agent_module.llm_client_manager().get_client("coder"),
            command_executor=main_container.core.command_executor(),
            logger=main_container.core.logger(),
        )
        logger.info("CI/CD healer initialized")
    except Exception as e:
        logger.warning(f"CI/CD healer init skipped: {e}")


@cicd_bp.route("/analyze", methods=["POST"])
def analyze_failure():
    """Analyze a CI/CD failure log."""
    if not _healer:
        return jsonify({"error": "CI/CD healer not available"}), 503

    data = request.get_json(force=True)
    workflow_log = data.get("log", "")
    if not workflow_log:
        return jsonify({"error": "log field required"}), 400

    import asyncio

    try:
        loop = asyncio.new_event_loop()
        analysis = loop.run_until_complete(_healer.analyze_failure(workflow_log))
        loop.close()
        return jsonify({"analysis": analysis.to_dict() if hasattr(analysis, "to_dict") else str(analysis)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@cicd_bp.route("/fix", methods=["POST"])
def generate_fix():
    """Generate fix for a CI/CD failure."""
    if not _healer:
        return jsonify({"error": "CI/CD healer not available"}), 503

    data = request.get_json(force=True)
    workflow_log = data.get("log", "")

    import asyncio

    try:
        loop = asyncio.new_event_loop()
        analysis = loop.run_until_complete(_healer.analyze_failure(workflow_log))
        fix = loop.run_until_complete(_healer.generate_fix(analysis, data.get("project_files", {})))
        loop.close()
        return jsonify({"fix": fix})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
