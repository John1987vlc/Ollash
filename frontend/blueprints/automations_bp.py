"""Blueprint for task automation scheduling."""

import json
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, render_template

from backend.utils.core.system.automation_executor import get_task_executor
from backend.utils.core.system.task_scheduler import get_scheduler
from frontend.middleware import require_api_key

logger = logging.getLogger(__name__)

automations_bp = Blueprint("automations", __name__)


@automations_bp.route("/automations")
def automations_page():
    return render_template("pages/automations.html")


# Storage path for tasks
_tasks_storage_file = None
_scheduled_tasks = {}
_scheduler = None
_executor = None


def init_app(app, event_publisher=None):
    """Initialize the automations blueprint."""
    global _tasks_storage_file, _scheduler, _executor
    ollash_root_dir = app.config.get("ollash_root_dir")
    _tasks_storage_file = ollash_root_dir / "config" / "scheduled_tasks.json"
    _tasks_storage_file.parent.mkdir(parents=True, exist_ok=True)

    # Initialize scheduler
    _scheduler = get_scheduler()

    # Initialize executor (only if event_publisher provided)
    if event_publisher:
        _executor = get_task_executor(ollash_root_dir, event_publisher)
        # Set the task execution callback in scheduler
        _scheduler.set_callback(_execute_scheduled_task)

    # Load existing tasks from storage
    load_tasks_from_storage()

    # Re-schedule all active tasks
    _reschedule_all_tasks()


def load_tasks_from_storage():
    """Load scheduled tasks from JSON file."""
    global _scheduled_tasks
    if _tasks_storage_file and _tasks_storage_file.exists():
        try:
            with open(_tasks_storage_file, "r") as f:
                _scheduled_tasks = json.load(f)
        except Exception as e:
            print(f"Error loading tasks: {e}")
            _scheduled_tasks = {}
    else:
        _scheduled_tasks = {}


def save_tasks_to_storage():
    """Save scheduled tasks to JSON file."""
    if _tasks_storage_file:
        try:
            with open(_tasks_storage_file, "w") as f:
                json.dump(_scheduled_tasks, f, indent=2)
        except Exception as e:
            print(f"Error saving tasks: {e}")


@automations_bp.route("/api/automations", methods=["GET"])
@require_api_key
def get_automations():
    """Fetch all scheduled tasks."""
    tasks_list = []
    for task_id, task in _scheduled_tasks.items():
        tasks_list.append(
            {
                "id": task_id,
                "name": task.get("name"),
                "agent": task.get("agent"),
                "prompt": task.get("prompt"),
                "schedule": task.get("schedule"),
                "cron": task.get("cron"),
                "nextRun": task.get("nextRun"),
                "lastRun": task.get("lastRun"),
                "status": task.get("status", "active"),
                "notifyEmail": task.get("notifyEmail", False),
                "createdAt": task.get("createdAt"),
            }
        )
    return jsonify(tasks_list)


@automations_bp.route("/api/automations", methods=["POST"])
@require_api_key
def create_automation():
    """Create a new scheduled task."""
    data = request.get_json()

    # Validate required fields
    required_fields = ["name", "agent", "prompt", "schedule"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    task_id = f"task_{int(datetime.now().timestamp() * 1000)}"

    _scheduled_tasks[task_id] = {
        "name": data["name"],
        "agent": data["agent"],
        "prompt": data["prompt"],
        "schedule": data["schedule"],
        "cron": data.get("cron"),
        "notifyEmail": data.get("notifyEmail", False),
        "meta": data.get("meta", {}),
        "status": "active",
        "createdAt": datetime.now().isoformat(),
        "lastRun": None,
        "nextRun": None,
    }

    save_tasks_to_storage()

    # Schedule with APScheduler if active
    if _scheduler and _scheduled_tasks[task_id]["status"] == "active":
        success = _scheduler.schedule_task(task_id, _scheduled_tasks[task_id])
        if not success:
            logger.warning(f"Failed to schedule task {task_id} with APScheduler")

    return (
        jsonify({"status": "created", "id": task_id, "task": _scheduled_tasks[task_id]}),
        201,
    )


@automations_bp.route("/api/automations/<task_id>", methods=["DELETE"])
@require_api_key
def delete_automation(task_id):
    """Delete/disable a scheduled task."""
    if task_id in _scheduled_tasks:
        del _scheduled_tasks[task_id]
        save_tasks_to_storage()

        # Unschedule from APScheduler
        if _scheduler:
            _scheduler.unschedule_task(task_id)

        return jsonify({"status": "deleted"})
    return jsonify({"error": "Task not found"}), 404


@automations_bp.route("/api/automations/<task_id>/toggle", methods=["PUT"])
@require_api_key
def toggle_automation(task_id):
    """Enable/disable a scheduled task."""
    if task_id in _scheduled_tasks:
        task = _scheduled_tasks[task_id]
        task["status"] = "inactive" if task["status"] == "active" else "active"
        save_tasks_to_storage()

        # Update scheduler
        if _scheduler:
            if task["status"] == "active":
                _scheduler.schedule_task(task_id, task)
            else:
                _scheduler.pause_task(task_id)

        return jsonify(
            {
                "id": task_id,
                "status": task["status"],
                "message": f"Task {task['name']} is now {task['status']}",
            }
        )
    return jsonify({"error": "Task not found"}), 404


@automations_bp.route("/api/automations/<task_id>/run", methods=["POST"])
@require_api_key
def run_automation_now(task_id):
    """Run a scheduled task immediately."""
    if task_id not in _scheduled_tasks:
        return jsonify({"error": "Task not found"}), 404

    task = _scheduled_tasks[task_id]
    task["lastRun"] = datetime.now().isoformat()
    save_tasks_to_storage()

    # Execute task immediately in background
    if _executor:
        try:
            # Execute in thread to avoid blocking
            import threading

            def _run():
                _executor.execute_task_sync(task_id, task)

            thread = threading.Thread(target=_run, daemon=True)
            thread.start()
        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}")
            return jsonify({"error": f"Failed to execute task: {str(e)}"}), 500

    return jsonify(
        {
            "id": task_id,
            "status": "executing",
            "message": f"Task '{task['name']}' started",
        }
    )


# ==================== Helper Functions ====================


def _reschedule_all_tasks():
    """Re-schedule all active tasks from storage on startup."""
    if not _scheduler:
        return

    for task_id, task in _scheduled_tasks.items():
        if task.get("status") == "active":
            try:
                _scheduler.schedule_task(task_id, task)
                logger.info(f"Rescheduled task {task_id}: {task.get('name')}")
            except Exception as e:
                logger.error(f"Failed to reschedule task {task_id}: {e}")


async def _execute_scheduled_task(task_id: str, task_data: dict):
    """
    Callback for APScheduler to execute tasks.
    This is called by the scheduler when a task is due.
    """
    if not _executor:
        logger.warning(f"Task executor not initialized for task {task_id}")
        return

    logger.info(f"APScheduler executing task {task_id}")

    # Get recipient emails from task config
    recipient_emails = None
    if task_data.get("notifyEmail"):
        # TODO: Get user's configured email addresses
        # For now, we'll just use the manager's subscribed emails
        from backend.utils.core.system.notification_manager import get_notification_manager

        nm = get_notification_manager()
        recipient_emails = list(nm.subscribed_emails) if nm.subscribed_emails else None

    # Execute the task
    await _executor.execute_task(task_id, task_data, recipient_emails)

    # Update last run time in storage
    if task_id in _scheduled_tasks:
        _scheduled_tasks[task_id]["lastRun"] = datetime.now().isoformat()
        save_tasks_to_storage()
