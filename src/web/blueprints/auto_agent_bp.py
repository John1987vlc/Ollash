"""Blueprint for AutoAgent project generation routes."""
import io
import os
import re
import threading
import time
import zipfile

from flask import Blueprint, jsonify, request, Response, stream_with_context, send_file
from pathlib import Path

from src.agents.auto_agent import AutoAgent
from src.web.middleware import rate_limit_api, require_api_key
from src.utils.core.event_publisher import EventPublisher
from src.web.services.chat_event_bridge import ChatEventBridge


auto_agent_bp = Blueprint("auto_agent", __name__)

# Initialized lazily via init_app()
_auto_agent: AutoAgent = None
_ollash_root_dir: Path = None
_event_publisher: EventPublisher = None
_chat_event_bridge: ChatEventBridge = None


def init_app(ollash_root_dir: Path, event_publisher: EventPublisher, chat_event_bridge: ChatEventBridge):
    """Initialize the AutoAgent instance for this blueprint."""
    global _auto_agent, _ollash_root_dir, _event_publisher, _chat_event_bridge
    _ollash_root_dir = ollash_root_dir
    _event_publisher = event_publisher
    _chat_event_bridge = chat_event_bridge
    config_path = ollash_root_dir / "config" / "settings.json"
    _auto_agent = AutoAgent(config_path=str(config_path), ollash_root_dir=ollash_root_dir)


@auto_agent_bp.route("/api/projects/create", methods=["POST"])
@require_api_key
@rate_limit_api
def create_project():
    project_description = request.form.get("project_description")
    project_name = request.form.get("project_name")

    if not project_description or not project_name:
        return jsonify({"status": "error", "message": "Project description and name are required."}), 400

    def run_agent():
        # Pass the event_publisher to the AutoAgent instance
        # Re-instantiate AutoAgent to inject event_publisher if necessary,
        # or ensure the existing instance is updated.
        # For simplicity, we'll assume AutoAgent's init can handle event_publisher
        # as a constructor parameter, and _auto_agent is re-initialized if needed.
        # Since AutoAgent's __init__ already accepts event_publisher (after previous changes)
        # we can just pass it directly.
        local_auto_agent = AutoAgent(
            config_path=str(_ollash_root_dir / "config" / "settings.json"),
            ollash_root_dir=_ollash_root_dir
        )
        local_auto_agent.event_publisher = _event_publisher # Inject the shared publisher

        try:
            local_auto_agent.logger.info(f"[PROJECT_STATUS] Project '{project_name}' creation initiated.")
            project_root = local_auto_agent.run(project_description, project_name) # Changed from create_project to run
            local_auto_agent.logger.info(f"[PROJECT_STATUS] Project '{project_name}' created at {project_root}")
            _chat_event_bridge.push_event("stream_end", {"message": f"Project '{project_name}' completed."}) # Use chat_event_bridge
        except Exception as e:
            local_auto_agent.logger.error(f"[PROJECT_STATUS] Error creating project '{project_name}': {e}")
            _chat_event_bridge.push_event("error", {"message": f"Error creating project: {e}"}) # Use chat_event_bridge

    thread = threading.Thread(target=run_agent, daemon=True)
    thread.start()

    return jsonify({"status": "started", "message": "Project creation started in background.", "project_name": project_name})


@auto_agent_bp.route("/api/projects/stream/<project_name>")
def stream_project_logs(project_name):
    # This route will now stream events directly from ChatEventBridge
    # We still need project_name for potential filtering in the future, but for now,
    # all events from the shared bridge are streamed.
    return Response(stream_with_context(_chat_event_bridge.iter_events()), mimetype="text/event-stream")


@auto_agent_bp.route("/api/projects/list")
def list_all_projects():
    projects_dir = str(_ollash_root_dir / "generated_projects" / "auto_agent_projects")

    if not os.path.isdir(projects_dir):
        return jsonify({"status": "success", "projects": []})

    try:
        projects = [d for d in os.listdir(projects_dir) if os.path.isdir(os.path.join(projects_dir, d))]
        projects.sort(key=lambda x: os.path.getmtime(os.path.join(projects_dir, x)), reverse=True)
        return jsonify({"status": "success", "projects": projects})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/<project_name>/files")
def list_project_files(project_name):
    project_path = str(_ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name)

    if not os.path.isdir(project_path):
        return jsonify({"status": "error", "message": "Project not found."}), 404

    file_tree = []
    try:
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in [".git", "__pycache__", "node_modules", ".venv", "venv"]]

            rel_root = os.path.relpath(root, project_path)
            if rel_root == ".":
                rel_root = ""

            for d in sorted(dirs):
                file_tree.append({
                    "path": os.path.join(rel_root, d) if rel_root else d,
                    "type": "directory",
                    "name": d,
                })
            for f in sorted(files):
                if not f.startswith(".") and not f.endswith(".pyc"):
                    file_tree.append({
                        "path": os.path.join(rel_root, f) if rel_root else f,
                        "type": "file",
                        "name": f,
                    })

        return jsonify({"status": "success", "files": file_tree})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/<project_name>/file", methods=["POST"])
def read_file_content(project_name):
    file_path_relative = request.json.get("file_path_relative")
    if not file_path_relative:
        return jsonify({"status": "error", "message": "File path is required."}), 400

    project_base_path = str(_ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name)
    full_file_path = os.path.normpath(os.path.join(project_base_path, file_path_relative))

    # Security: prevent directory traversal
    if not full_file_path.startswith(project_base_path):
        return jsonify({"status": "error", "message": "Invalid file path."}), 400

    if not os.path.isfile(full_file_path):
        return jsonify({"status": "error", "message": "File not found."}), 404

    try:
        try:
            with open(full_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return jsonify({"status": "success", "content": content, "type": "text"})
        except UnicodeDecodeError:
            return jsonify({
                "status": "success",
                "content": "[Binary file - cannot display as text]",
                "type": "binary",
            })
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error reading file: {e}"}), 500


@auto_agent_bp.route("/api/projects/<project_name>/export")
def export_project_zip(project_name):
    """Download a project as a ZIP archive."""
    project_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name

    if not project_path.is_dir():
        return jsonify({"status": "error", "message": "Project not found."}), 404

    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for f in files:
                if f.startswith(".") or f.endswith(".pyc"):
                    continue
                full_path = os.path.join(root, f)
                arcname = os.path.relpath(full_path, project_path)
                zf.write(full_path, arcname)

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{project_name}.zip",
    )