from flask import Blueprint, jsonify, request
from backend.core.containers import main_container
from backend.utils.core.io.checkpoint_manager import CheckpointManager
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.structured_logger import StructuredLogger

checkpoints_bp = Blueprint("checkpoints", __name__)


@checkpoints_bp.route("/api/checkpoints/<project_name>", methods=["GET"])
def list_checkpoints(project_name):
    root = main_container.core.ollash_root_dir()
    sl = StructuredLogger(root / "logs" / "checkpoints.log")
    mgr = CheckpointManager(root / ".ollash" / "checkpoints", AgentLogger(sl, "checkpoints_api"))
    checkpoints = mgr.list_checkpoints(project_name)
    return jsonify({"checkpoints": checkpoints})


@checkpoints_bp.route("/api/checkpoints/restore", methods=["POST"])
def restore_checkpoint():
    data = request.json
    project_name = data.get("project_name")
    phase_name = data.get("phase_name")

    root = main_container.core.ollash_root_dir()
    sl = StructuredLogger(root / "logs" / "checkpoints.log")
    mgr = CheckpointManager(root / ".ollash" / "checkpoints", AgentLogger(sl, "checkpoints_api"))

    checkpoint = mgr.load_at_phase(project_name, phase_name)
    if not checkpoint:
        return jsonify({"error": "Checkpoint not found"}), 404

    # Restore files logic
    project_dir = root / "generated_projects" / "auto_agent_projects" / project_name
    for path, content in checkpoint.generated_files.items():
        full_path = project_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    return jsonify({"status": "restored"})
