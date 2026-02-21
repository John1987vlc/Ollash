from flask import Blueprint, jsonify, request
from backend.core.containers import main_container
import json

policies_bp = Blueprint("policies", __name__)

@policies_bp.route("/api/policies", methods=["GET"])
def get_policies():
    root = main_container.core.ollash_root_dir()
    from backend.utils.core.policy_manager import PolicyManager
    from backend.utils.core.agent_logger import AgentLogger
    from backend.utils.core.structured_logger import StructuredLogger
    
    sl = StructuredLogger(root / "logs" / "policies.log")
    mgr = PolicyManager(root, AgentLogger(sl, "policies_api"), {})
    return jsonify(mgr.policies)

@policies_bp.route("/api/policies/update", methods=["POST"])
def update_policies():
    data = request.json
    root = main_container.core.ollash_root_dir()
    from backend.utils.core.policy_manager import PolicyManager
    from backend.utils.core.agent_logger import AgentLogger
    from backend.utils.core.structured_logger import StructuredLogger
    
    sl = StructuredLogger(root / "logs" / "policies.log")
    mgr = PolicyManager(root, AgentLogger(sl, "policies_api"), {})
    mgr.policies.update(data)
    mgr._save_policies()
    return jsonify({"status": "success"})
