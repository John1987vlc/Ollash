from flask import Blueprint, jsonify, request
from backend.core.containers import main_container

router_bp = Blueprint("router", __name__)


@router_bp.route("/api/router/config", methods=["GET"])
def get_router_config():
    # Model affinity/routing settings from config
    config = main_container.core.config()
    return jsonify(
        {
            "phase_mapping": config.get("phase_model_mapping", {}),
            "available_models": config.get("llm_models", []),
            "senior_reviewer": config.get("senior_reviewer_model", "qwen3-coder-next"),
        }
    )


@router_bp.route("/api/router/mapping", methods=["POST"])
def update_mapping():
    data = request.json
    phase = data.get("phase")
    model = data.get("model")

    # In a real app, update persistent config.json
    # For now, we simulate success
    return jsonify({"status": "success", "phase": phase, "model": model})
