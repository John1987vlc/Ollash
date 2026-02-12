"""
Automations API Blueprint - Exposes automation task management endpoints
"""

from flask import Blueprint, jsonify, request, current_app
from pathlib import Path
import json
import logging
import asyncio

automations_api_bp = Blueprint('automations_api', __name__, url_prefix='/api/automations')
logger = logging.getLogger(__name__)


@automations_api_bp.route('', methods=['GET'])
def get_automations():
    """Get all automation tasks."""
    try:
        automation_manager = current_app.config.get('automation_manager')
        if not automation_manager:
            return jsonify({"ok": False, "error": "Automation manager not initialized"}), 500
        
        tasks = automation_manager.get_tasks()
        return jsonify({
            "ok": True,
            "tasks": tasks,
            "total": len(tasks)
        })
    except Exception as e:
        logger.error(f"Error getting automations: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@automations_api_bp.route('/<task_id>', methods=['GET'])
def get_automation(task_id):
    """Get a specific automation task."""
    try:
        automation_manager = current_app.config.get('automation_manager')
        if not automation_manager:
            return jsonify({"ok": False, "error": "Automation manager not initialized"}), 500
        
        task = automation_manager.get_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": f"Task {task_id} not found"}), 404
        
        return jsonify({
            "ok": True,
            "task": task
        })
    except Exception as e:
        logger.error(f"Error getting automation: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@automations_api_bp.route('/<task_id>', methods=['PUT'])
def update_automation(task_id):
    """Update an automation task."""
    try:
        automation_manager = current_app.config.get('automation_manager')
        if not automation_manager:
            return jsonify({"ok": False, "error": "Automation manager not initialized"}), 500
        
        data = request.get_json()
        success = automation_manager.update_task(task_id, data)
        
        if success:
            return jsonify({
                "ok": True,
                "message": f"Task {task_id} updated",
                "task": automation_manager.get_task(task_id)
            })
        else:
            return jsonify({"ok": False, "error": f"Task {task_id} not found"}), 404
    except Exception as e:
        logger.error(f"Error updating automation: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@automations_api_bp.route('/<task_id>/toggle', methods=['POST'])
def toggle_automation(task_id):
    """Enable/disable an automation task."""
    try:
        automation_manager = current_app.config.get('automation_manager')
        if not automation_manager:
            return jsonify({"ok": False, "error": "Automation manager not initialized"}), 500
        
        task = automation_manager.get_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": f"Task {task_id} not found"}), 404
        
        # Toggle enabled state
        new_enabled = not task.get("enabled", True)
        success = automation_manager.update_task(task_id, {"enabled": new_enabled})
        
        if success:
            return jsonify({
                "ok": True,
                "message": f"Task {task_id} {'enabled' if new_enabled else 'disabled'}",
                "enabled": new_enabled
            })
        else:
            return jsonify({"ok": False, "error": "Failed to toggle task"}), 500
    except Exception as e:
        logger.error(f"Error toggling automation: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@automations_api_bp.route('/<task_id>/run', methods=['POST'])
def run_automation_now(task_id):
    """Execute an automation task immediately."""
    try:
        automation_manager = current_app.config.get('automation_manager')
        if not automation_manager:
            return jsonify({"ok": False, "error": "Automation manager not initialized"}), 500
        
        task = automation_manager.get_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": f"Task {task_id} not found"}), 404
        
        # Execute task immediately through the wrapper
        automation_manager._execute_task_wrapper(task_id, task)
        
        return jsonify({
            "ok": True,
            "message": f"Task {task_id} execution started"
        })
    except Exception as e:
        logger.error(f"Error running automation: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@automations_api_bp.route('/<task_id>', methods=['DELETE'])
def delete_automation(task_id):
    """Delete an automation task."""
    try:
        automation_manager = current_app.config.get('automation_manager')
        if not automation_manager:
            return jsonify({"ok": False, "error": "Automation manager not initialized"}), 500
        
        task = automation_manager.get_task(task_id)
        if not task:
            return jsonify({"ok": False, "error": f"Task {task_id} not found"}), 404
        
        # Remove from tasks dict
        automation_manager.tasks.pop(task_id, None)
        
        # Remove from scheduler if running
        if automation_manager.scheduler and automation_manager.scheduler.running:
            job = automation_manager.scheduler.get_job(task_id)
            if job:
                job.remove()
        
        # Save updated tasks
        automation_manager._save_tasks()
        
        return jsonify({
            "ok": True,
            "message": f"Task {task_id} deleted"
        })
    except Exception as e:
        logger.error(f"Error deleting automation: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@automations_api_bp.route('/reload', methods=['POST'])
def reload_automations():
    """Reload all automation tasks from config."""
    try:
        automation_manager = current_app.config.get('automation_manager')
        if not automation_manager:
            return jsonify({"ok": False, "error": "Automation manager not initialized"}), 500
        
        automation_manager.reload_tasks()
        
        return jsonify({
            "ok": True,
            "message": "Automations reloaded",
            "count": len(automation_manager.get_tasks())
        })
    except Exception as e:
        logger.error(f"Error reloading automations: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


def init_app(ollash_root_dir: Path, event_publisher=None):
    """Initialize automations blueprint with required dependencies."""
    logger.info("Initializing automations blueprint")
    
    # This will be completed when registering the blueprint


__all__ = ['automations_api_bp', 'init_app']
