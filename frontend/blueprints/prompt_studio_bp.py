from flask import Blueprint, jsonify, request
from backend.core.containers import main_container
from backend.utils.core.llm.prompt_repository import PromptRepository

prompt_studio_bp = Blueprint("prompt_studio", __name__)
_repo: PromptRepository = None


def get_repo():
    global _repo
    if _repo is None:
        root = main_container.core.ollash_root_dir()
        db_path = root / ".ollash" / "prompts.db"
        _repo = PromptRepository(db_path)
    return _repo


@prompt_studio_bp.route("/api/prompts/roles", methods=["GET"])
def get_roles():
    roles = ["orchestrator", "code", "network", "system", "cybersecurity", "planner", "prototyper"]
    return jsonify({"roles": roles})


@prompt_studio_bp.route("/api/prompts/<role>/history", methods=["GET"])
def get_prompt_history(role):
    history = get_repo().get_history(role)
    return jsonify({"history": history})


@prompt_studio_bp.route("/api/prompts/<role>", methods=["POST"])
def save_prompt(role):
    data = request.json
    text = data.get("prompt_text")
    if not text:
        return jsonify({"error": "No text provided"}), 400
    prompt_id = get_repo().save_prompt(role, text, is_active=True)
    return jsonify({"status": "success", "id": prompt_id})


@prompt_studio_bp.route("/api/prompts/rollback/<int:prompt_id>", methods=["POST"])
def rollback_prompt(prompt_id):
    get_repo().rollback(prompt_id)
    return jsonify({"status": "success"})


@prompt_studio_bp.route("/api/prompts/migrate", methods=["POST"])
def migrate():
    root = main_container.core.ollash_root_dir()
    get_repo().migrate_from_json(root / "prompts")
    return jsonify({"status": "migration_started"})
