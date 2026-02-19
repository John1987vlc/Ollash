"""
Alerts API Blueprint - Exposes alert endpoints and SSE streams
"""

import json
import logging
import queue  # Import queue module
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")
logger = logging.getLogger(__name__)


# Global event subscribers for SSE
_alert_subscribers = []


@alerts_bp.route("/stream")
def stream_alerts():
    """
    Server-Sent Events endpoint for real-time alerts.
    Clients connect here to receive proactive notifications.
    """
    event_publisher = current_app.config.get("event_publisher")

    def generate(publisher):
        if not publisher:
            logger.warning("EventPublisher not available for alerts stream")
            yield f"data: {json.dumps({'error': 'EventPublisher not initialized'})}\n\n"
            return

        # Create a subscription queue for this client
        event_queue = queue.Queue()  # Renamed to event_queue to avoid conflict with imported queue module

        # Define a callback function to put events into the queue
        def _event_callback(event_type, event_data):
            event_queue.put((event_type, event_data))

        # Subscribe the callback to relevant events
        publisher.subscribe("ui_alert", _event_callback)
        publisher.subscribe("alert_triggered", _event_callback)
        publisher.subscribe("task_execution_complete", _event_callback)
        publisher.subscribe("task_execution_error", _event_callback)
        publisher.subscribe("automation_started", _event_callback)

        logger.info("🔌 Client connected to alert stream")

        try:
            while True:
                try:
                    # Get next event from queue (timeout: 30 seconds)
                    event_type, event_data = event_queue.get(timeout=30)

                    # Format as SSE
                    data = json.dumps(event_data) if isinstance(event_data, dict) else str(event_data)
                    yield f"event: {event_type}\n"
                    yield f"data: {data}\n\n"

                except queue.Empty:  # Use the imported queue.Empty
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"

        except GeneratorExit:
            logger.info("🔌 Client disconnected from alert stream")
        except Exception as e:
            logger.error(f"Error in alert stream: {e}")
        finally:
            # Unsubscribe the specific callback for this client
            publisher.unsubscribe("ui_alert", _event_callback)
            publisher.unsubscribe("alert_triggered", _event_callback)
            publisher.unsubscribe("task_execution_complete", _event_callback)
            publisher.unsubscribe("task_execution_error", _event_callback)
            publisher.unsubscribe("automation_started", _event_callback)

    return Response(
        generate(event_publisher),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@alerts_bp.route("", methods=["GET"])
def get_alerts():
    """Get configured alerts."""
    try:
        alert_manager = current_app.config.get("alert_manager")
        if not alert_manager:
            return jsonify({"ok": False, "error": "Alert manager not initialized"}), 500

        alerts = alert_manager.get_active_alerts()
        return jsonify({"ok": True, "alerts": alerts, "total": len(alerts)})
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@alerts_bp.route("/history", methods=["GET"])
def get_alert_history():
    """Get recent alert history."""
    try:
        alert_manager = current_app.config.get("alert_manager")
        if not alert_manager:
            return jsonify({"ok": False, "error": "Alert manager not initialized"}), 500

        limit = request.args.get("limit", 50, type=int)
        history = alert_manager.get_alert_history(limit=limit)

        return jsonify({"ok": True, "history": history, "total": len(history)})
    except Exception as e:
        logger.error(f"Error getting alert history: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@alerts_bp.route("/<alert_id>/disable", methods=["POST"])
def disable_alert(alert_id):
    """Disable a specific alert."""
    try:
        alert_manager = current_app.config.get("alert_manager")
        if not alert_manager:
            return jsonify({"ok": False, "error": "Alert manager not initialized"}), 500

        success = alert_manager.disable_alert(alert_id)
        if success:
            return jsonify({"ok": True, "message": f"Alert {alert_id} disabled"})
        else:
            return jsonify({"ok": False, "error": f"Alert {alert_id} not found"}), 404
    except Exception as e:
        logger.error(f"Error disabling alert: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@alerts_bp.route("/<alert_id>/enable", methods=["POST"])
def enable_alert(alert_id):
    """Enable a specific alert."""
    try:
        alert_manager = current_app.config.get("alert_manager")
        if not alert_manager:
            return jsonify({"ok": False, "error": "Alert manager not initialized"}), 500

        success = alert_manager.enable_alert(alert_id)
        if success:
            return jsonify({"ok": True, "message": f"Alert {alert_id} enabled"})
        else:
            return jsonify({"ok": False, "error": f"Alert {alert_id} not found"}), 404
    except Exception as e:
        logger.error(f"Error enabling alert: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@alerts_bp.route("/history/clear", methods=["POST"])
def clear_history():
    """Clear alert history."""
    try:
        alert_manager = current_app.config.get("alert_manager")
        if not alert_manager:
            return jsonify({"ok": False, "error": "Alert manager not initialized"}), 500

        alert_manager.clear_history()
        return jsonify({"ok": True, "message": "Alert history cleared"})
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


def init_app(app, event_publisher=None, alert_manager=None):
    """Initialize alerts blueprint with required dependencies."""
    logger.info("Initializing alerts blueprint")
    ollash_root_dir = app.config.get("ollash_root_dir")


__all__ = ["alerts_bp", "init_app"]
