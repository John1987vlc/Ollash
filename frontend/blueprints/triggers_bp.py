"""Blueprint for managing conditional triggers (advanced automation rules)."""

import logging

from flask import Blueprint, jsonify, request

from backend.utils.core.trigger_manager import get_trigger_manager
from frontend.middleware import require_api_key

logger = logging.getLogger(__name__)

triggers_bp = Blueprint("triggers", __name__)

_trigger_manager = None


def init_app():
    """Initialize triggers blueprint."""
    global _trigger_manager
    _trigger_manager = get_trigger_manager()


@triggers_bp.route("/api/triggers", methods=["GET"])
@require_api_key
def get_all_triggers():
    """Get all conditional triggers."""
    if not _trigger_manager:
        return jsonify({"error": "Trigger manager not initialized"}), 503

    try:
        triggers = _trigger_manager.to_dict()

        return jsonify({"count": len(triggers), "triggers": triggers})

    except Exception as e:
        logger.error(f"Error retrieving triggers: {e}")
        return jsonify({"error": str(e)}), 500


@triggers_bp.route("/api/triggers", methods=["POST"])
@require_api_key
def create_trigger():
    """Create a new conditional trigger."""
    if not _trigger_manager:
        return jsonify({"error": "Trigger manager not initialized"}), 503

    try:
        data = request.get_json()

        # Validate required fields
        required = ["trigger_id", "rule", "actions"]
        if not all(field in data for field in required):
            return jsonify({"error": "Missing required fields"}), 400

        trigger_id = data["trigger_id"]

        # Check if trigger already exists
        if trigger_id in _trigger_manager.triggers:
            return jsonify({"error": "Trigger already exists"}), 409

        # Add trigger
        success = _trigger_manager.add_trigger(trigger_id=trigger_id, rule=data["rule"], actions=data["actions"])

        if not success:
            return jsonify({"error": "Failed to create trigger"}), 500

        return (
            jsonify(
                {
                    "status": "created",
                    "trigger_id": trigger_id,
                    "trigger": _trigger_manager.triggers[trigger_id].to_dict(),
                }
            ),
            201,
        )

    except Exception as e:
        logger.error(f"Error creating trigger: {e}")
        return jsonify({"error": str(e)}), 500


@triggers_bp.route("/api/triggers/<trigger_id>", methods=["GET"])
@require_api_key
def get_trigger(trigger_id: str):
    """Get a specific trigger."""
    if not _trigger_manager:
        return jsonify({"error": "Trigger manager not initialized"}), 503

    try:
        if trigger_id not in _trigger_manager.triggers:
            return jsonify({"error": "Trigger not found"}), 404

        trigger = _trigger_manager.triggers[trigger_id]

        return jsonify({"trigger_id": trigger_id, "trigger": trigger.to_dict()})

    except Exception as e:
        logger.error(f"Error retrieving trigger: {e}")
        return jsonify({"error": str(e)}), 500


@triggers_bp.route("/api/triggers/<trigger_id>", methods=["PUT"])
@require_api_key
def update_trigger(trigger_id: str):
    """Update a trigger."""
    if not _trigger_manager:
        return jsonify({"error": "Trigger manager not initialized"}), 503

    try:
        if trigger_id not in _trigger_manager.triggers:
            return jsonify({"error": "Trigger not found"}), 404

        data = request.get_json()
        trigger = _trigger_manager.triggers[trigger_id]

        # Update rule
        if "rule" in data:
            trigger.rule = data["rule"]

        # Update actions
        if "actions" in data:
            trigger.actions = data["actions"]

        return jsonify(
            {
                "status": "updated",
                "trigger_id": trigger_id,
                "trigger": trigger.to_dict(),
            }
        )

    except Exception as e:
        logger.error(f"Error updating trigger: {e}")
        return jsonify({"error": str(e)}), 500


@triggers_bp.route("/api/triggers/<trigger_id>", methods=["DELETE"])
@require_api_key
def delete_trigger(trigger_id: str):
    """Delete a trigger."""
    if not _trigger_manager:
        return jsonify({"error": "Trigger manager not initialized"}), 503

    try:
        success = _trigger_manager.remove_trigger(trigger_id)

        if not success:
            return jsonify({"error": "Trigger not found"}), 404

        return jsonify({"status": "deleted", "trigger_id": trigger_id})

    except Exception as e:
        logger.error(f"Error deleting trigger: {e}")
        return jsonify({"error": str(e)}), 500


@triggers_bp.route("/api/triggers/<trigger_id>/enable", methods=["PUT"])
@require_api_key
def enable_trigger(trigger_id: str):
    """Enable a trigger."""
    if not _trigger_manager:
        return jsonify({"error": "Trigger manager not initialized"}), 503

    try:
        success = _trigger_manager.enable_trigger(trigger_id)

        if not success:
            return jsonify({"error": "Trigger not found"}), 404

        return jsonify({"status": "enabled", "trigger_id": trigger_id})

    except Exception as e:
        logger.error(f"Error enabling trigger: {e}")
        return jsonify({"error": str(e)}), 500


@triggers_bp.route("/api/triggers/<trigger_id>/disable", methods=["PUT"])
@require_api_key
def disable_trigger(trigger_id: str):
    """Disable a trigger."""
    if not _trigger_manager:
        return jsonify({"error": "Trigger manager not initialized"}), 503

    try:
        success = _trigger_manager.disable_trigger(trigger_id)

        if not success:
            return jsonify({"error": "Trigger not found"}), 404

        return jsonify({"status": "disabled", "trigger_id": trigger_id})

    except Exception as e:
        logger.error(f"Error disabling trigger: {e}")
        return jsonify({"error": str(e)}), 500


@triggers_bp.route("/api/triggers/history", methods=["GET"])
@require_api_key
def get_trigger_history():
    """Get trigger execution history."""
    if not _trigger_manager:
        return jsonify({"error": "Trigger manager not initialized"}), 503

    try:
        limit = request.args.get("limit", 100, type=int)
        history = _trigger_manager.get_trigger_history(limit=limit)

        return jsonify({"count": len(history), "history": history})

    except Exception as e:
        logger.error(f"Error retrieving trigger history: {e}")
        return jsonify({"error": str(e)}), 500


@triggers_bp.route("/api/triggers/<trigger_id>/test", methods=["POST"])
@require_api_key
def test_trigger(trigger_id: str):
    """Test a trigger with provided context."""
    if not _trigger_manager:
        return jsonify({"error": "Trigger manager not initialized"}), 503

    try:
        if trigger_id not in _trigger_manager.triggers:
            return jsonify({"error": "Trigger not found"}), 404

        data = request.get_json() or {}
        context = data.get("context", {})

        trigger = _trigger_manager.triggers[trigger_id]
        should_trigger = trigger.should_trigger(context, cooldown_minutes=0)

        return jsonify(
            {
                "trigger_id": trigger_id,
                "test_context": context,
                "would_trigger": should_trigger,
                "rule": trigger.rule,
            }
        )

    except Exception as e:
        logger.error(f"Error testing trigger: {e}")
        return jsonify({"error": str(e)}), 500


@triggers_bp.route("/api/triggers/templates", methods=["GET"])
@require_api_key
def get_trigger_templates():
    """Get predefined trigger templates for common scenarios."""
    templates = {
        "high_cpu_alert": {
            "name": "High CPU Usage Alert",
            "description": "Alert when CPU usage exceeds 80%",
            "rule": {
                "conditions": [{"metric": "system.cpu_usage", "operator": ">", "value": 80}],
                "logic": "AND",
            },
            "actions": [
                {
                    "type": "send_notification",
                    "title": "High CPU Alert",
                    "message": "CPU usage has exceeded 80%",
                    "severity": "warning",
                },
                {
                    "type": "execute_prompt",
                    "name": "Analyze High CPU",
                    "agent": "system",
                    "prompt": "Identify top processes consuming CPU",
                },
            ],
        },
        "low_disk_space": {
            "name": "Low Disk Space Alert",
            "description": "Alert when free disk space falls below 10%",
            "rule": {
                "conditions": [{"metric": "system.disk_free_percent", "operator": "<", "value": 10}],
                "logic": "AND",
            },
            "actions": [
                {
                    "type": "send_notification",
                    "title": "Low Disk Space",
                    "message": "Available disk space is below 10%",
                    "severity": "critical",
                }
            ],
        },
        "service_down": {
            "name": "Critical Service Down",
            "description": "Alert when critical service becomes unavailable",
            "rule": {
                "conditions": [
                    {
                        "metric": "network.service_status",
                        "operator": "==",
                        "value": "DOWN",
                    }
                ],
                "logic": "AND",
            },
            "actions": [
                {
                    "type": "send_notification",
                    "title": "Service Alert",
                    "message": "Critical service is down",
                    "severity": "critical",
                }
            ],
        },
    }

    return jsonify({"count": len(templates), "templates": templates})
