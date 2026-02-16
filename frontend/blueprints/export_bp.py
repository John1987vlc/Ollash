"""Blueprint for Multi-Purpose Export (F15)."""

import logging
from pathlib import Path

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

export_bp = Blueprint("export_bp", __name__, url_prefix="/api/export")

_export_manager = None
_ollash_root = None


def init_app(app):
    """Initialize export blueprint."""
    global _export_manager, _ollash_root
    try:
        from backend.utils.core.export_manager import ExportManager

        _ollash_root = app.config.get("ollash_root_dir", Path("."))
        from backend.core.containers import main_container

        _export_manager = ExportManager(
            command_executor=main_container.core.command_executor(),
            logger=main_container.core.logger(),
        )
        logger.info("Export manager initialized")
    except Exception as e:
        logger.warning(f"Export manager init skipped: {e}")


@export_bp.route("/zip", methods=["POST"])
def export_zip():
    """Export project as ZIP."""
    if not _export_manager:
        return jsonify({"error": "Export manager not available"}), 503

    data = request.get_json(force=True)
    project_name = data.get("project_name", "")
    if not project_name:
        return jsonify({"error": "project_name required"}), 400

    project_root = _ollash_root / "generated_projects" / "auto_agent_projects" / project_name
    if not project_root.exists():
        return jsonify({"error": f"Project '{project_name}' not found"}), 404

    try:
        output_path = _export_manager.export_zip(project_root)
        return jsonify({"success": True, "path": str(output_path)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@export_bp.route("/github", methods=["POST"])
def deploy_github():
    """Deploy project to GitHub."""
    if not _export_manager:
        return jsonify({"error": "Export manager not available"}), 503

    data = request.get_json(force=True)
    project_name = data.get("project_name", "")
    repo_name = data.get("repo_name", project_name)
    token = data.get("token", "")
    private = data.get("private", True)
    organization = data.get("organization")

    if not project_name or not token:
        return jsonify({"error": "project_name and token required"}), 400

    project_root = _ollash_root / "generated_projects" / "auto_agent_projects" / project_name

    import asyncio

    try:
        loop = asyncio.new_event_loop()
        url = loop.run_until_complete(
            _export_manager.deploy_to_github(project_root, repo_name, token, private, organization)
        )
        loop.close()
        return jsonify({"success": True, "url": url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@export_bp.route("/targets", methods=["GET"])
def get_targets():
    """Get supported export targets."""
    if not _export_manager:
        return jsonify({"targets": {}})
    return jsonify({"targets": _export_manager.get_supported_targets()})
