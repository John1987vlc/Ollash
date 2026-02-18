"""Blueprint for selective refactoring endpoints.

Provides an endpoint to apply refactored code directly to project files,
used by the Monaco diff editor in the frontend.
"""

from pathlib import Path

from flask import Blueprint, jsonify, request

from frontend.middleware import require_api_key

refactor_bp = Blueprint("refactor", __name__)

_ollash_root_dir: Path = None


def init_app(app):
    global _ollash_root_dir
    _ollash_root_dir = app.config.get("ollash_root_dir", Path("."))


@refactor_bp.route("/api/refactor/apply", methods=["POST"])
@require_api_key
def apply_refactoring():
    """Apply refactored content to a project file.

    Body JSON: {
        "project_name": "my-project",
        "file_path": "src/main.py",
        "modified_content": "..."
    }
    """
    data = request.get_json(force=True)
    project_name = data.get("project_name", "").strip()
    file_path = data.get("file_path", "").strip()
    modified_content = data.get("modified_content", "")

    if not project_name or not file_path:
        return jsonify({"status": "error", "message": "project_name and file_path are required."}), 400

    # Security: prevent directory traversal
    if ".." in file_path or file_path.startswith("/") or file_path.startswith("\\"):
        return jsonify({"status": "error", "message": "Invalid file path."}), 400

    if ".." in project_name or "/" in project_name or "\\" in project_name:
        return jsonify({"status": "error", "message": "Invalid project name."}), 400

    project_dir = _ollash_root_dir / "generated_projects" / project_name
    if not project_dir.exists():
        return jsonify({"status": "error", "message": f"Project '{project_name}' not found."}), 404

    target_file = project_dir / file_path
    # Ensure the resolved path is still within the project
    try:
        target_file.resolve().relative_to(project_dir.resolve())
    except ValueError:
        return jsonify({"status": "error", "message": "File path escapes project directory."}), 400

    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(modified_content)
        return jsonify({"status": "success", "message": f"File '{file_path}' updated successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
