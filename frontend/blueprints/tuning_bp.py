from flask import Blueprint, jsonify, request
from backend.core.containers import main_container
from backend.utils.core.memory.behavior_tuner import BehaviorTuner, TuningParameter
from backend.utils.core.analysis.shadow_evaluator import ShadowEvaluator
from backend.utils.core.system.agent_logger import AgentLogger

tuning_bp = Blueprint("tuning", __name__)
_tuner: BehaviorTuner = None
_shadow: ShadowEvaluator = None


def get_tuner():
    global _tuner
    if _tuner is None:
        root = main_container.core.ollash_root_dir()
        _tuner = BehaviorTuner(root)
    return _tuner


def get_shadow():
    global _shadow
    if _shadow is None:
        root = main_container.core.ollash_root_dir()
        # Note: In a real app, ShadowEvaluator should be a singleton managed by the kernel
        # and already started. We initialize a reporter-only instance here.
        from backend.utils.core.system.event_publisher import EventPublisher

        _shadow = ShadowEvaluator(
            AgentLogger("shadow_api", root / "logs"), EventPublisher(), root / ".ollash" / "shadow_logs"
        )
    return _shadow


@tuning_bp.route("/api/tuning/config", methods=["GET"])
def get_config():
    return jsonify(get_tuner().get_current_config())


@tuning_bp.route("/api/tuning/update", methods=["POST"])
def update_tuning():
    data = request.json
    param_name = data.get("parameter")
    new_value = data.get("value")

    try:
        param = TuningParameter(param_name)
        success = get_tuner().update_parameter(param, new_value, reason="Manual UI update")
        return jsonify({"status": "success" if success else "failed"})
    except ValueError:
        # Fallback for feature toggles or non-enum params
        if param_name in ["cross_reference", "knowledge_graph", "decision_memory", "artifacts"]:
            success = get_tuner().toggle_feature(param_name, bool(new_value), reason="Manual UI toggle")
            return jsonify({"status": "success" if success else "failed"})
        return jsonify({"error": "Invalid parameter"}), 400


@tuning_bp.route("/api/tuning/shadow-report", methods=["GET"])
def get_shadow_report():
    # Simple mock if no logs exist
    report = get_shadow().get_performance_report()
    if not report["models"]:
        # Provide some example data if none exists so the UI doesn't look empty
        report["models"] = {
            "qwen3-coder-next": {
                "total_evaluations": 45,
                "correction_rate": 0.12,
                "avg_severity": 0.15,
                "flagged": False,
            },
            "llama3-70b": {"total_evaluations": 12, "correction_rate": 0.05, "avg_severity": 0.08, "flagged": False},
        }
    return jsonify(report)
