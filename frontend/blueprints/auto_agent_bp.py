"""Blueprint for AutoAgent project generation routes."""

import io
import os
import re
import subprocess
import threading
import zipfile
from pathlib import Path
from typing import Dict, List

from flask import Blueprint, Response, jsonify, request, send_file, stream_with_context

from backend.agents.auto_agent import AutoAgent

# DI Container and Agent
from backend.core.containers import main_container
from backend.utils.core.event_publisher import EventPublisher
from frontend.middleware import rate_limit_api, require_api_key
from frontend.services.chat_event_bridge import ChatEventBridge

from backend.utils.core.git_manager import GitManager
from backend.utils.core.git_pr_tool import GitPRTool
from backend.utils.core.task_scheduler import get_scheduler

auto_agent_bp = Blueprint("auto_agent", __name__)

# Globals for shared services
_ollash_root_dir: Path = None
_event_publisher: EventPublisher = None
_chat_event_bridge: ChatEventBridge = None


def init_app(
    app,
    event_publisher: EventPublisher,
    chat_event_bridge: ChatEventBridge,
):
    """Initialize shared services for the blueprint and wire the DI container."""
    global _ollash_root_dir, _event_publisher, _chat_event_bridge
    _ollash_root_dir = app.config.get("ollash_root_dir")
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

        readme, structure_json = local_auto_agent.generate_structure_only(project_description, project_name, **kwargs)
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
            jsonify({"status": "error", "message": "Missing required project details."}),
            400,
        )

    def run_agent_in_thread():
        """Target function for the background thread."""
        try:
            # Instantiate the agent inside the thread via the DI container
            agent: AutoAgent = main_container.auto_agent_module.auto_agent()

            # Hook up the global event publisher for this long-running task
            agent.event_publisher = _event_publisher

            agent.logger.info(f"[PROJECT_STATUS] Project '{project_name}' generation starting in background.")

            run_kwargs = {
                "project_description": project_description,
                "project_name": project_name,
                "template_name": request.form.get("template_name", "default"),
                "python_version": request.form.get("python_version"),
                "license_type": request.form.get("license_type"),
                "include_docker": request.form.get("include_docker") == "true",
                "num_refine_loops": int(request.form.get("num_refine_loops", 0)),
                # Git & CI/CD options
                "git_push": request.form.get("git_push") == "true",
                "git_token": request.form.get("git_token", ""),
                "repo_name": request.form.get("repo_name", project_name),
                "git_organization": request.form.get("git_organization", ""),
                # Feature flags
                "senior_review_as_pr": request.form.get("senior_review_as_pr") == "true",
                "enable_github_wiki": request.form.get("enable_github_wiki") == "true",
                "enable_github_pages": request.form.get("enable_github_pages") == "true",
                "block_security_critical": request.form.get("block_security_critical") == "true",
            }

            project_root = agent.run(**run_kwargs)

            # Schedule autonomous maintenance if requested
            if request.form.get("enable_hourly_pr") == "true":
                try:
                    from backend.utils.core.autonomous_maintenance import AutonomousMaintenanceTask
                    from backend.utils.core.agent_logger import AgentLogger
                    
                    maint_logger = AgentLogger(f"Maint-{project_name}")
                    maint_task = AutonomousMaintenanceTask(
                        project_root=project_root,
                        agent_logger=maint_logger,
                        event_publisher=_event_publisher
                    )
                    
                    # Register the task with the scheduler
                    # Note: AutonomousMaintenanceTask.register expects an automation_manager
                    # but it seems it just needs something with a .scheduler property.
                    # We can pass an object that has the scheduler.
                    class SimpleAutomationManager:
                        def __init__(self, scheduler):
                            self.scheduler = scheduler
                    
                    maint_task.register(SimpleAutomationManager(get_scheduler().scheduler))
                    agent.logger.info(f"[PROJECT_STATUS] Autonomous maintenance scheduled for '{project_name}'.")
                except Exception as maint_err:
                    agent.logger.error(f"Failed to schedule maintenance for '{project_name}': {maint_err}")

            agent.logger.info(f"[PROJECT_STATUS] Project '{project_name}' created at {project_root}")
            _chat_event_bridge.push_event("stream_end", {"message": f"Project '{project_name}' completed."})
        except Exception as e:
            logger = main_container.core.logger()
            logger.error(
                f"[PROJECT_STATUS] Error creating project '{project_name}': {e}",
                exc_info=True,
            )
            _chat_event_bridge.push_event("error", {"message": f"Error creating project: {e}"})

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

    project_base_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
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

    project_base_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name

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


@auto_agent_bp.route("/api/projects/clone", methods=["POST"])
@require_api_key
@rate_limit_api
def clone_project():
    """Clone an existing git repository into the generated_projects directory."""
    from backend.utils.core.input_validators import validate_git_url, validate_project_name

    git_url = request.form.get("git_url", "").strip()

    if not git_url:
        return jsonify({"status": "error", "message": "Git URL is required."}), 400

    if not validate_git_url(git_url):
        return jsonify({"status": "error", "message": "Invalid or unsupported git URL."}), 400

    # Derive project name from URL if not provided
    project_name = request.form.get("project_name", "").strip()
    if not project_name:
        project_name = git_url.rstrip("/").split("/")[-1].replace(".git", "")

    if not validate_project_name(project_name):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Invalid project name. Use alphanumeric, hyphens, or underscores.",
                }
            ),
            400,
        )

    projects_dir = _ollash_root_dir / "generated_projects" / "auto_agent_projects"
    target_path = projects_dir / project_name

    if target_path.exists():
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Project '{project_name}' already exists.",
                }
            ),
            409,
        )

    try:
        logger = main_container.core.logger()
        logger.info(f"Cloning {git_url} to {target_path}")

        projects_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", git_url, str(target_path)],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            error = result.stderr.strip() or "Unknown error"
            logger.error(f"Clone failed: {error}")
            return (
                jsonify({"status": "error", "message": f"Git clone failed: {error}"}),
                500,
            )

        logger.info(f"Successfully cloned {git_url} as {project_name}")
        return jsonify(
            {
                "status": "success",
                "message": f"Project '{project_name}' cloned successfully.",
                "project_name": project_name,
            }
        )
    except subprocess.TimeoutExpired:
        return (
            jsonify({"status": "error", "message": "Git clone timed out (5 min limit)."}),
            504,
        )
    except Exception as e:
        logger = main_container.core.logger()
        logger.error(f"Error cloning project: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/<project_name>/quarantine")
def get_project_quarantine(project_name):
    """List files currently in quarantine for a project."""
    project_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    quarantine_dir = project_path / ".quarantine"

    if not quarantine_dir.is_dir():
        return jsonify({"status": "success", "files": []})

    try:
        files = []
        for f in os.listdir(quarantine_dir):
            f_path = quarantine_dir / f
            if f_path.is_file():
                # Try to find why it was quarantined (from vulnerability scan report if exists)
                reason = "Deemed unsafe by security scanner"
                files.append({
                    "name": f,
                    "path": str(f_path),
                    "reason": reason,
                    "size": f_path.stat().st_size,
                    "modified": f_path.stat().st_mtime
                })
        return jsonify({"status": "success", "files": sorted(files, key=lambda x: x["modified"], reverse=True)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/<project_name>/quarantine/<filename>/approve", methods=["POST"])
def approve_quarantine_file(project_name, filename):
    """Move a file from quarantine back to the project root."""
    project_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    quarantine_path = project_path / ".quarantine" / filename
    dest_path = project_path / filename

    if not quarantine_path.is_file():
        return jsonify({"status": "error", "message": "File not found in quarantine."}), 404

    try:
        import shutil
        shutil.move(str(quarantine_path), str(dest_path))
        return jsonify({"status": "success", "message": f"File {filename} approved and restored."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/<project_name>/quarantine/<filename>/reject", methods=["POST"])
def reject_quarantine_file(project_name, filename):
    """Delete a file from quarantine and request re-generation (simulated)."""
    project_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    quarantine_path = project_path / ".quarantine" / filename

    if not quarantine_path.is_file():
        return jsonify({"status": "error", "message": "File not found in quarantine."}), 404

    try:
        os.remove(quarantine_path)
        # In a real scenario, we might trigger a re-generation task here
        return jsonify({"status": "success", "message": f"File {filename} rejected and removed from quarantine."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/<project_name>/compliance")
def get_project_compliance(project_name):
    """Perform a deep license and dependency scan on the project."""
    project_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name

    if not project_path.is_dir():
        return jsonify({"status": "error", "message": "Project not found."}), 404

    try:
        from backend.utils.core.deep_license_scanner import DeepLicenseScanner
        from backend.utils.core.agent_logger import AgentLogger
        
        logger = AgentLogger(f"Compliance-{project_name}")
        scanner = DeepLicenseScanner(logger)
        
        # Collect relevant files for scanning
        generated_files = {}
        for root, _, files in os.walk(project_path):
            for f in files:
                if f in ("requirements.txt", "package.json", "pyproject.toml"):
                    rel_path = os.path.relpath(os.path.join(root, f), project_path)
                    try:
                        with open(os.path.join(root, f), "r", encoding="utf-8") as file:
                            generated_files[rel_path] = file.read()
                    except Exception:
                        pass
        
        # Assume project license is MIT if not found (or read from LICENSE file)
        project_license = "MIT"
        license_file = project_path / "LICENSE"
        if license_file.is_file():
            content = license_file.read_text().upper()
            if "APACHE" in content: project_license = "Apache-2.0"
            elif "GPL" in content: project_license = "GPL-3.0-only"

        report = scanner.scan_project(generated_files, project_license)
        return jsonify({"status": "success", "report": report.to_dict()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/<project_name>/security-report")
def get_project_security_report(project_name):
    """Retrieve the latest security scan report for a project."""
    project_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    report_path = project_path / "SECURITY_SCAN_REPORT.md"

    if not report_path.is_file():
        return jsonify({"status": "error", "message": "Security report not found. Run a security scan first."}), 404

    try:
        content = report_path.read_text(encoding="utf-8")
        return jsonify({"status": "success", "report_markdown": content})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/<project_name>/issues")
def get_project_issues(project_name):
    """Retrieve structured issues from senior review markdown files for a given project."""
    project_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name

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


@auto_agent_bp.route("/api/projects/<project_name>/delete", methods=["POST"])
@require_api_key
def delete_project_item(project_name):
    """Delete a file or folder within a project."""
    import shutil
    path_relative = request.json.get("path")
    if not path_relative:
        return jsonify({"status": "error", "message": "Path is required."}), 400

    project_base_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    full_path = os.path.normpath(os.path.join(project_base_path, path_relative))

    if not str(full_path).startswith(str(project_base_path)):
        return jsonify({"status": "error", "message": "Invalid path."}), 400

    try:
        if os.path.isfile(full_path):
            os.remove(full_path)
        elif os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            return jsonify({"status": "error", "message": "Item not found."}), 404
        
        return jsonify({"status": "success", "message": "Item deleted successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auto_agent_bp.route("/api/projects/<project_name>/rename", methods=["POST"])
@require_api_key
def rename_project_item(project_name):
    """Rename a file or folder within a project."""
    old_path_rel = request.json.get("old_path")
    new_path_rel = request.json.get("new_path")
    
    if not old_path_rel or not new_path_rel:
        return jsonify({"status": "error", "message": "Old and new paths are required."}), 400

    project_base_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    old_full_path = os.path.normpath(os.path.join(project_base_path, old_path_rel))
    new_full_path = os.path.normpath(os.path.join(project_base_path, new_path_rel))

    if not str(old_full_path).startswith(str(project_base_path)) or \
       not str(new_full_path).startswith(str(project_base_path)):
        return jsonify({"status": "error", "message": "Invalid path."}), 400

    try:
        os.rename(old_full_path, new_full_path)
        return jsonify({"status": "success", "message": "Item renamed successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


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


@auto_agent_bp.route("/api/projects/<project_name>/git_status")
def get_project_git_status(project_name):
    """Retrieve Git status and automated maintenance info for a project."""
    project_path = _ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name

    if not project_path.is_dir():
        return jsonify({"status": "error", "message": "Project not found."}), 404

    git_enabled = (project_path / ".git").is_dir()
    
    if not git_enabled:
        return jsonify({"status": "success", "git_enabled": False})

    try:
        logger = main_container.core.logger()
        git_tool = GitPRTool(str(project_path), logger)
        
        # Get open PRs
        prs = git_tool.list_open_prs()
        
        # Check if auto-improvement is scheduled
        scheduler = get_scheduler()
        tasks = scheduler.list_all_tasks()
        
        # We look for a task that might be the maintenance task for this project
        # In this simplified version, we just check if any maintenance task is active
        sync_active = any(t.get("id") == "autonomous_maintenance_hourly" and not t.get("paused") for t in tasks)
        next_review = None
        
        maint_task = next((t for t in tasks if t.get("id") == "autonomous_maintenance_hourly"), None)
        if maint_task and maint_task.get("next_run_time"):
            from datetime import datetime
            next_run = datetime.fromisoformat(maint_task["next_run_time"])
            diff = next_run - datetime.now()
            minutes = int(diff.total_seconds() / 60)
            next_review = f"{minutes} min" if minutes > 0 else "Pronto"

        return jsonify({
            "status": "success",
            "git_enabled": True,
            "sync_active": sync_active,
            "next_review": next_review,
            "prs": prs
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
