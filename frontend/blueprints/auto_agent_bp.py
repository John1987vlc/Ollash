"""Blueprint for AutoAgent project generation routes."""
import io
import os
import re
import subprocess
import threading
import zipfile
from pathlib import Path
from typing import Dict, List

from flask import (Blueprint, Response, jsonify, request, send_file,
                   stream_with_context)

from backend.agents.auto_agent import AutoAgent
# DI Container and Agent
from backend.core.containers import main_container
from backend.utils.core.event_publisher import EventPublisher
from frontend.middleware import rate_limit_api, require_api_key
from frontend.services.chat_event_bridge import ChatEventBridge

auto_agent_bp = Blueprint("auto_agent", __name__)

# Globals for shared services
_ollash_root_dir: Path = None
_event_publisher: EventPublisher = None
_chat_event_bridge: ChatEventBridge = None


def init_app(
    ollash_root_dir: Path,
    event_publisher: EventPublisher,
    chat_event_bridge: ChatEventBridge,
):
    """Initialize shared services for the blueprint and wire the DI container."""
    global _ollash_root_dir, _event_publisher, _chat_event_bridge
    _ollash_root_dir = ollash_root_dir
    _event_publisher = event_publisher
    _chat_event_bridge = chat_event_bridge

    # Wire the container to the modules that will use injected dependencies
    main_container.wire(modules=[__name__, "backend.agents.auto_agent"])


@auto_agent_bp.route("/api/projects/generate_structure", methods=["POST"])
@require_api_key
@rate_limit_api
def generate_project_structure():
    # ... (form data parsing remains the same)
    project_description = request.form.get("project_description")
    project_name = request.form.get("project_name")

    if not project_description or not project_name:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Project description and name are required.",
                }
            ),
            400,
        )

    try:
        # Instantiate the agent via the DI container
        local_auto_agent: AutoAgent = main_container.auto_agent_module.auto_agent()

        # Collect kwargs for the agent method
        kwargs = {
            "template_name": request.form.get("template_name", "default"),
            "python_version": request.form.get("python_version"),
            "license_type": request.form.get("license_type"),
            "include_docker": request.form.get("include_docker") == "true",
        }

        readme, structure_json = local_auto_agent.generate_structure_only(
            project_description, project_name, **kwargs
        )
        return jsonify(
            {
                "status": "structure_generated",
                "project_name": project_name,
                "readme": readme,
                "structure": structure_json,
            }
        )
    except Exception as e:
        # Log the exception using the agent's logger if possible, otherwise a default logger
        logger = main_container.core.logger()
        logger.error(
            f"[PROJECT_STATUS] Error generating structure for '{project_name}': {e}",
            exc_info=True,
        )
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/create", methods=["POST"])
@require_api_key
@rate_limit_api
def create_project():
    # ... (form data parsing remains the same)
    project_description = request.form.get("project_description")
    project_name = request.form.get("project_name")

    if not project_description or not project_name:
        return (
            jsonify(
                {"status": "error", "message": "Missing required project details."}
            ),
            400,
        )

    def run_agent_in_thread():
        """Target function for the background thread."""
        try:
            # Instantiate the agent inside the thread via the DI container
            agent: AutoAgent = main_container.auto_agent_module.auto_agent()

            # Hook up the global event publisher for this long-running task
            agent.event_publisher = _event_publisher

            agent.logger.info(
                f"[PROJECT_STATUS] Project '{project_name}' generation starting in background."
            )

            run_kwargs = {
                "project_description": project_description,
                "project_name": project_name,
                "template_name": request.form.get("template_name", "default"),
                "python_version": request.form.get("python_version"),
                "license_type": request.form.get("license_type"),
                "include_docker": request.form.get("include_docker") == "true",
                "num_refine_loops": int(request.form.get("num_refine_loops", 0)),
            }

            project_root = agent.run(**run_kwargs)

            agent.logger.info(
                f"[PROJECT_STATUS] Project '{project_name}' created at {project_root}"
            )
            _chat_event_bridge.push_event(
                "stream_end", {"message": f"Project '{project_name}' completed."}
            )
        except Exception as e:
            logger = main_container.core.logger()
            logger.error(
                f"[PROJECT_STATUS] Error creating project '{project_name}': {e}",
                exc_info=True,
            )
            _chat_event_bridge.push_event(
                "error", {"message": f"Error creating project: {e}"}
            )

    # Run the agent in a background thread
    thread = threading.Thread(target=run_agent_in_thread, daemon=True)
    thread.start()

    return jsonify(
        {
            "status": "started",
            "message": "Project creation started in background.",
            "project_name": project_name,
        }
    )


# ... (the rest of the file remains the same)
@auto_agent_bp.route("/api/projects/stream/<project_name>")
def stream_project_logs(project_name):
    # This route will now stream events directly from ChatEventBridge
    # We still need project_name for potential filtering in the future, but for now,
    # all events from the shared bridge are streamed.
    return Response(
        stream_with_context(_chat_event_bridge.iter_events()),
        mimetype="text/event-stream",
    )


@auto_agent_bp.route("/api/projects/list")
def list_all_projects():
    projects_dir = str(_ollash_root_dir / "generated_projects" / "auto_agent_projects")

    if not os.path.isdir(projects_dir):
        return jsonify({"status": "success", "projects": []})

    try:
        projects = [
            d
            for d in os.listdir(projects_dir)
            if os.path.isdir(os.path.join(projects_dir, d))
        ]
        projects.sort(
            key=lambda x: os.path.getmtime(os.path.join(projects_dir, x)), reverse=True
        )
        return jsonify({"status": "success", "projects": projects})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/<project_name>/files")
def list_project_files(project_name):
    project_path = str(
        _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    )

    if not os.path.isdir(project_path):
        return jsonify({"status": "error", "message": "Project not found."}), 404

    file_tree = []
    try:
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [
                d
                for d in dirs
                if d not in [".git", "__pycache__", "node_modules", ".venv", "venv"]
            ]

            rel_root = os.path.relpath(root, project_path)
            if rel_root == ".":
                rel_root = ""

            for d in sorted(dirs):
                file_tree.append(
                    {
                        "path": os.path.join(rel_root, d) if rel_root else d,
                        "type": "directory",
                        "name": d,
                    }
                )
            for f in sorted(files):
                if not f.startswith(".") and not f.endswith(".pyc"):
                    file_tree.append(
                        {
                            "path": os.path.join(rel_root, f) if rel_root else f,
                            "type": "file",
                            "name": f,
                        }
                    )

        return jsonify({"status": "success", "files": file_tree})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/<project_name>/file", methods=["POST"])
def read_file_content(project_name):
    file_path_relative = request.json.get("file_path_relative")
    if not file_path_relative:
        return jsonify({"status": "error", "message": "File path is required."}), 400

    project_base_path = str(
        _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    )
    full_file_path = os.path.normpath(
        os.path.join(project_base_path, file_path_relative)
    )

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
            return jsonify(
                {
                    "status": "success",
                    "content": "[Binary file - cannot display as text]",
                    "type": "binary",
                }
            )
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error reading file: {e}"}), 500


@auto_agent_bp.route("/api/projects/<project_name>/save_file", methods=["POST"])
@require_api_key
@rate_limit_api
def save_file_content(project_name):
    file_path_relative = request.json.get("file_path_relative")
    content = request.json.get("content")

    if not file_path_relative:
        return jsonify({"status": "error", "message": "File path is required."}), 400
    if content is None:  # Allow saving empty content
        return jsonify({"status": "error", "message": "Content is required."}), 400

    project_base_path = (
        _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    )
    full_file_path = project_base_path / file_path_relative

    # Security: prevent directory traversal
    if not str(full_file_path).startswith(str(project_base_path)):
        return jsonify({"status": "error", "message": "Invalid file path."}), 400

    try:
        # Ensure directory exists
        full_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return jsonify({"status": "success", "message": "File saved successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error saving file: {e}"}), 500


@auto_agent_bp.route("/api/projects/<project_name>/execute_command", methods=["POST"])
@require_api_key
@rate_limit_api
def execute_command(project_name):
    command = request.json.get("command")
    if not command:
        return jsonify({"status": "error", "message": "Command is required."}), 400

    project_base_path = (
        _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    )

    # Security: Ensure command is executed within the project directory
    if not project_base_path.is_dir():
        return jsonify({"status": "error", "message": "Project not found."}), 404

    try:
        # Execute the command in the project's directory
        # Using shell=True for convenience, but consider security implications
        # For production, might want to parse command and arguments explicitly
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=project_base_path,
            check=False,  # Do not raise CalledProcessError for non-zero exit codes
        )
        return jsonify(
            {
                "status": "success",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        )
    except Exception as e:
        return (
            jsonify({"status": "error", "message": f"Error executing command: {e}"}),
            500,
        )


@auto_agent_bp.route("/api/projects/<project_name>/export")
def export_project_zip(project_name):
    """Download a project as a ZIP archive."""
    project_path = (
        _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    )

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


@auto_agent_bp.route("/api/projects/<project_name>/issues")
def get_project_issues(project_name):
    """Retrieve structured issues from senior review markdown files for a given project."""
    project_path = (
        _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    )

    if not project_path.is_dir():
        return jsonify({"status": "error", "message": "Project not found."}), 404

    all_issues = []
    # Iterate through possible SENIOR_REVIEW_ISSUES_ATTEMPT_X.md files
    for i in range(1, 4):  # Assuming max 3 review attempts as in AutoAgent
        issue_file_path = project_path / f"SENIOR_REVIEW_ISSUES_ATTEMPT_{i}.md"
        if issue_file_path.is_file():
            try:
                with open(issue_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                parsed_issues = _parse_issue_markdown(content)
                all_issues.extend(parsed_issues)
            except Exception as e:
                # Use a reliable logger
                logger = main_container.core.logger()
                logger.error(f"Error parsing issue file {issue_file_path}: {e}")
                # Continue to next file even if one fails to parse

    return jsonify({"status": "success", "issues": all_issues})


def _parse_issue_markdown(markdown_content: str) -> List[Dict]:
    """Parses the Markdown content of a SENIOR_REVIEW_ISSUES_ATTEMPT_X.md file into a list of dictionaries."""
    issues = []
    # Regex to find each issue section
    issue_sections = re.findall(
        r"## Issue \d+: \[(.+?)\]\n\*\*File:\*\*\s*(.*?)\n\*\*Description:\*\*\s*(.*?)\n\*\*Recommendation:\*\*\s*(.*?)(?=\n## Issue|\Z)",
        markdown_content,
        re.DOTALL,
    )

    for section in issue_sections:
        severity, file_path, description, recommendation = section
        issues.append(
            {
                "severity": severity.strip(),
                "file": file_path.strip() if file_path.strip() != "N/A" else None,
                "description": description.strip(),
                "recommendation": recommendation.strip(),
            }
        )
    return issues
