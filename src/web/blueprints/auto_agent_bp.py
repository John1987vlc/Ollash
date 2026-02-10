"""Blueprint for AutoAgent project generation routes."""
import os
import re
import threading
import time

from flask import Blueprint, jsonify, request, Response, stream_with_context
from pathlib import Path

from src.agents.auto_agent import AutoAgent

auto_agent_bp = Blueprint("auto_agent", __name__)

# Initialized lazily via init_app()
_auto_agent: AutoAgent = None
_ollash_root_dir: Path = None


def init_app(ollash_root_dir: Path):
    """Initialize the AutoAgent instance for this blueprint."""
    global _auto_agent, _ollash_root_dir
    _ollash_root_dir = ollash_root_dir
    config_path = ollash_root_dir / "config" / "settings.json"
    _auto_agent = AutoAgent(config_path=str(config_path), ollash_root_dir=ollash_root_dir)


@auto_agent_bp.route("/api/projects/create", methods=["POST"])
def create_project():
    project_description = request.form.get("project_description")
    project_name = request.form.get("project_name")

    if not project_description or not project_name:
        return jsonify({"status": "error", "message": "Project description and name are required."}), 400

    def run_agent():
        try:
            _auto_agent.logger.info(f"[PROJECT_STATUS] Project '{project_name}' creation initiated.")
            project_root = _auto_agent.create_project(project_description, project_name)
            _auto_agent.logger.info(f"[PROJECT_STATUS] Project '{project_name}' created at {project_root}")
            _auto_agent.logger.info(f"[STREAM_END] Project '{project_name}' completed.")
        except Exception as e:
            _auto_agent.logger.error(f"[PROJECT_STATUS] Error creating project '{project_name}': {e}")

    thread = threading.Thread(target=run_agent, daemon=True)
    thread.start()

    return jsonify({"status": "started", "message": "Project creation started in background.", "project_name": project_name})


@auto_agent_bp.route("/api/projects/stream/<project_name>")
def stream_project_logs(project_name):
    log_file_path = str(_ollash_root_dir / "logs" / "auto_agent.log")

    def generate():
        last_position = 0
        project_log_pattern = re.compile(r".*\[PROJECT_STATUS\].*'{}'.*".format(re.escape(project_name)))
        general_log_pattern = re.compile(r".*{}.*".format(re.escape(project_name)))

        while True:
            try:
                if not os.path.exists(log_file_path):
                    yield "data: [INFO] Waiting for log file to be created...\n\n"
                    time.sleep(1)
                    continue

                with open(log_file_path, "r", encoding="utf-8") as f:
                    f.seek(last_position)
                    new_lines = f.readlines()
                    last_position = f.tell()

                    if not new_lines:
                        time.sleep(0.5)
                        continue

                    for line in new_lines:
                        if project_log_pattern.match(line) or general_log_pattern.search(line):
                            yield f"data: {line.strip()}\n\n"

                        if f"[STREAM_END] Project '{project_name}'" in line:
                            yield f"data: {line.strip()}\n\n"
                            return

            except Exception as e:
                yield f"data: [ERROR] Error during log streaming: {e}\n\n"
                time.sleep(1)
                continue

            time.sleep(0.1)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


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
