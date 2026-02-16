"""
Automation Manager - Orchestrates scheduled tasks and proactive automation
Manages task scheduling and execution with notification integration
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.core.kernel import AgentKernel  # Import AgentKernel
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


class AutomationManager:
    """Manages scheduled automation tasks and their execution."""

    def __init__(
        self,
        ollash_root_dir: Path,
        event_publisher: EventPublisher,
        agent_logger: AgentLogger,
    ):
        """
        Initialize the automation manager.

        Args:
            ollash_root_dir: Root directory of Ollash
            event_publisher: Event publisher for notifications
            agent_logger: An instance of AgentLogger for structured logging
        """
        self.ollash_root_dir = ollash_root_dir
        self.config_path = ollash_root_dir / "config" / "tasks.json"
        self.logger = agent_logger
        self.event_publisher = event_publisher

        self.scheduler = BackgroundScheduler(daemon=True)
        self.tasks = {}
        self.task_callbacks = {}  # Maps task_id to execution callback
        self.running = False
        self._lock = threading.Lock()

        self._load_tasks()

    def _load_tasks(self) -> Dict[str, Any]:
        """Load tasks from configuration file."""
        if not self.config_path.exists():
            self.logger.warning(f"Tasks config not found at {self.config_path}")
            return {}

        try:
            config_data = json.loads(self.config_path.read_text())
            self.tasks = {task["task_id"]: task for task in config_data.get("tasks", [])}
            self.logger.info(f"✅ Loaded {len(self.tasks)} automation tasks")
            return self.tasks
        except Exception as e:
            self.logger.error(f"❌ Failed to load tasks config: {e}")
            return {}

    def register_task_callback(self, task_id: str, callback: Callable):
        """
        Register a callback function for a specific task.
        The callback will be invoked when the task is triggered.

        Args:
            task_id: The task identifier
            callback: Async function that accepts (task_id, task_data) and executes the task
        """
        with self._lock:
            self.task_callbacks[task_id] = callback
            self.logger.info(f"Registered callback for task: {task_id}")

    def start(self):
        """Start the automation scheduler."""
        with self._lock:
            if self.running:
                self.logger.warning("Automation manager already running")
                return

            self.running = True

        try:
            self._schedule_all_tasks()
            if not self.scheduler.running:
                self.scheduler.start()
            self.logger.info("✅ Automation manager started successfully")

            # Publish startup event
            self.event_publisher.publish(
                "automation_started",
                {
                    "timestamp": datetime.now().isoformat(),
                    "tasks_count": len(self.tasks),
                },
            )
        except Exception as e:
            self.logger.error(f"❌ Failed to start automation manager: {e}")
            self.running = False

    def stop(self):
        """Stop the automation scheduler."""
        with self._lock:
            if not self.running:
                return

            self.running = False

        try:
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown()
            self.logger.info("✅ Automation manager stopped")
        except Exception as e:
            self.logger.error(f"❌ Error stopping automation manager: {e}")

    def _schedule_all_tasks(self):
        """Schedule all enabled tasks."""
        for task_id, task in self.tasks.items():
            if task.get("enabled", True):
                self._schedule_task(task_id, task)

    def _schedule_task(self, task_id: str, task: Dict[str, Any]):
        """
        Schedule a single task using APScheduler.

        Args:
            task_id: Task identifier
            task: Task configuration dictionary
        """
        try:
            schedule_config = task.get("schedule", {})
            schedule_type = schedule_config.get("type", "interval")

            trigger = None
            if schedule_type == "cron":
                cron_expr = schedule_config.get("cron_expression", "0 9 * * *")
                trigger = CronTrigger.from_crontab(cron_expr)
            elif schedule_type == "interval":
                interval_mins = schedule_config.get("interval_minutes", 60)
                trigger = IntervalTrigger(minutes=interval_mins)

            if trigger:
                self.scheduler.add_job(
                    self._execute_task_wrapper,
                    trigger=trigger,
                    args=[task_id, task],
                    id=task_id,
                    name=task.get("name", task_id),
                    replace_existing=True,
                    coalesce=True,
                    max_instances=1,
                )

                human_readable = schedule_config.get("human_readable", "")
                self.logger.info(f"📅 Scheduled task '{task.get('name')}' - {human_readable}")

        except Exception as e:
            self.logger.error(f"❌ Failed to schedule task {task_id}: {e}")

    def _execute_task_wrapper(self, task_id: str, task: Dict[str, Any]):
        """
        Wrapper for task execution with error handling and notifications.

        Args:
            task_id: Task identifier
            task: Task configuration
        """
        try:
            self.logger.info(f"🚀 Executing task: {task.get('name', task_id)}")

            # Check for threshold-based triggers
            if "check_tool" in task:
                result = self._check_threshold(task)
                if not result.get("should_proceed", True):
                    self.logger.info(f"Task {task_id} threshold check: no action needed")
                    return

            # Execute the registered callback if it exists
            if task_id in self.task_callbacks:
                callback = self.task_callbacks[task_id]
                callback(task_id, task)

            # Publish task execution event
            self._publish_task_event(task_id, task, "execution_complete", "success")

        except Exception as e:
            self.logger.error(f"❌ Error executing task {task_id}: {e}")
            self._publish_task_event(task_id, task, "execution_error", str(e))

    def _check_threshold(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if a threshold condition is met for the task.

        Returns:
            Dictionary with 'should_proceed' boolean and check results
        """
        check_tool = task.get("check_tool")
        check_params = task.get("check_params", {})

        # This would be called by the executing agent to check thresholds
        # For now, return allow-to-proceed
        return {
            "should_proceed": True,
            "check_tool": check_tool,
            "params": check_params,
        }

    def _publish_task_event(self, task_id: str, task: Dict[str, Any], event_type: str, details: Any = None):
        """Publish a task execution event."""
        self.event_publisher.publish(
            f"task_{event_type}",
            {
                "task_id": task_id,
                "task_name": task.get("name"),
                "timestamp": datetime.now().isoformat(),
                "details": details,
            },
        )

    def reload_tasks(self):
        """Reload tasks from configuration file."""
        with self._lock:
            old_count = len(self.tasks)
            self._load_tasks()

            # Re-schedule all tasks
            if self.running and self.scheduler:
                self.scheduler.remove_all_jobs()
                self._schedule_all_tasks()

            new_count = len(self.tasks)
            self.logger.info(f"🔄 Reloaded tasks: {old_count} -> {new_count}")

    def get_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks."""
        return list(self.tasks.values())

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task."""
        return self.tasks.get(task_id)

    def update_task(self, task_id: str, updates: Dict[str, Any]):
        """Update a task configuration."""
        if task_id not in self.tasks:
            self.logger.warning(f"Task not found: {task_id}")
            return False

        try:
            with self._lock:
                self.tasks[task_id].update(updates)
                self._save_tasks()

                # Re-schedule if running
                if self.running and self.scheduler:
                    job = self.scheduler.get_job(task_id)
                    if job:
                        job.remove()
                    self._schedule_task(task_id, self.tasks[task_id])

            self.logger.info(f"✅ Updated task: {task_id}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to update task {task_id}: {e}")
            return False

    def _save_tasks(self):
        """Save tasks to configuration file."""
        try:
            config_data = {
                "tasks": list(self.tasks.values()),
                "last_updated": datetime.now().isoformat(),
            }
            self.config_path.write_text(json.dumps(config_data, indent=2))
        except Exception as e:
            self.logger.error(f"❌ Failed to save tasks: {e}")


# Singleton instance
_automation_manager: Optional[AutomationManager] = None


def get_automation_manager(ollash_root_dir: Path = None, event_publisher: EventPublisher = None) -> AutomationManager:
    """Get or create the automation manager singleton."""
    global _automation_manager

    if _automation_manager is None:
        if ollash_root_dir is None:
            ollash_root_dir = Path(__file__).resolve().parent.parent.parent.parent
        if event_publisher is None:
            event_publisher = EventPublisher()

        # Get logger from AgentKernel (which is a singleton)
        # AgentKernel needs ollash_root_dir to initialize if it hasn't already been.
        kernel_logger = AgentKernel(ollash_root_dir=ollash_root_dir).get_logger()

        _automation_manager = AutomationManager(ollash_root_dir, event_publisher, kernel_logger)

    return _automation_manager
