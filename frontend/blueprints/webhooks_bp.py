"""
Blueprint for managing external webhooks and notifications.
"""

import logging
from flask import Blueprint, jsonify, request
from backend.utils.core.webhook_manager import get_webhook_manager, WebhookType

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/api/webhooks")
logger = logging.getLogger(__name__)

@webhooks_bp.route("/", methods=["GET"])
def list_webhooks():
    """List all registered webhooks and their status."""
    try:
        wm = get_webhook_manager()
        status = wm.get_webhook_status()
        return jsonify({"status": "success", "webhooks": status})
    except Exception as e:
        logger.error(f"Error listing webhooks: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@webhooks_bp.route("/register", methods=["POST"])
def register_webhook():
    """Register a new webhook."""
    data = request.json
    name = data.get("name")
    webhook_type_str = data.get("type", "custom").lower()
    url = data.get("url")

    if not name or not url:
        return jsonify({"status": "error", "message": "Missing name or url"}), 400

    try:
        wm = get_webhook_manager()
        webhook_type = WebhookType(webhook_type_str)
        success = wm.register_webhook(name=name, webhook_type=webhook_type, webhook_url=url)

        if success:
            return jsonify({"status": "success", "message": f"Webhook '{name}' registered"})
        else:
            return jsonify({"status": "error", "message": "Failed to register webhook"}), 400
    except Exception as e:
        logger.error(f"Error registering webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@webhooks_bp.route("/test", methods=["POST"])
async def test_webhook():
    """Send a test notification to a webhook."""
    data = request.json
    name = data.get("name")

    if not name:
        return jsonify({"status": "error", "message": "Missing name"}), 400

    try:
        wm = get_webhook_manager()
        success = await wm.send_to_webhook(
            webhook_name=name,
            message="This is a test notification from Ollash Agent.",
            title="Ollash Connection Test"
        )

        if success:
            return jsonify({"status": "success", "message": "Test message sent successfully"})
        else:
            return jsonify({"status": "error", "message": "Failed to send test message"}), 500
    except Exception as e:
        logger.error(f"Error testing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def init_app(app):
    """Initialize webhooks."""
    pass
