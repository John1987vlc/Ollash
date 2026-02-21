"""
Blueprint for managing Ollash plugins.
"""

import logging
from flask import Blueprint, jsonify, request, current_app
from backend.utils.core.plugin_manager import PluginManager

plugins_bp = Blueprint("plugins", __name__, url_prefix="/api/plugins")
logger = logging.getLogger(__name__)

_plugin_manager = None

def get_plugin_manager():
    global _plugin_manager
    if _plugin_manager is None:
        ollash_root_dir = current_app.config.get("ollash_root_dir")
        plugins_dir = ollash_root_dir / "plugins"
        _plugin_manager = PluginManager(plugins_dir, logger)
        _plugin_manager.discover()
    return _plugin_manager

@plugins_bp.route("/", methods=["GET"])
def list_plugins():
    """List all discovered plugins and their status."""
    try:
        pm = get_plugin_manager()
        plugins = pm.get_plugin_metadata()
        # In a real app, we'd check against a config of enabled plugins
        # For now, we'll return what's loaded
        return jsonify({"status": "success", "plugins": plugins})
    except Exception as e:
        logger.error(f"Error listing plugins: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@plugins_bp.route("/toggle", methods=["POST"])
def toggle_plugin():
    """Enable or disable a plugin."""
    data = request.json
    plugin_id = data.get("plugin_id")
    enabled = data.get("enabled", True)

    if not plugin_id:
        return jsonify({"status": "error", "message": "Missing plugin_id"}), 400

    try:
        pm = get_plugin_manager()
        if enabled:
            pm.load_plugin(plugin_id)
        else:
            pm.unload_plugin(plugin_id)

        return jsonify({"status": "success", "plugin_id": plugin_id, "enabled": enabled})
    except Exception as e:
        logger.error(f"Error toggling plugin {plugin_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def init_app(app):
    """Initialize the plugin manager for the app."""
    # This could also pre-load plugins from a config
    pass
