"""
Automation Manager - Orchestrates scheduled tasks and proactive automation
Manages task scheduling and execution with notification integration
"""

import json
import logging
import threading
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.core.kernel import AgentKernel  # Import AgentKernel
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.core.system.task_models import ExecutionRecord

logger = logging.getLogger(__name__)


class AutomationManager:
    """Manages scheduled automation tasks and their execution."""

    MAX_HISTORY_PER_TASK: int = 50

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
        self._git_trigger: Optional[Any] = None  # Placeholder for Sprint 3 E5

        self._load_tasks()

    def _load_tasks(self) -> Dict[str, Any]:
        """Load tasks from configuration file."""
        if not self.config_path.exists():
            self.logger.info_sync(f"Tasks config not found at {self.config_path}")
            return {}

        try:
            config_data = json.loads(self.config_path.read_text())
            self.tasks = {task["task_id"]: task for task in config_data.get("tasks", [])}
            self.logger.info_sync(f"✅ Loaded {len(self.tasks)} automation tasks")
            return self.tasks
        except Exception as e:
            self.logger.debug(f"❌ Failed to load tasks config: {e}")
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
            self.logger.info_sync(f"Registered callback for task: {task_id}")

    async def start(self):
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
            await self.event_publisher.publish(
                "automation_started",
                {
                    "timestamp": datetime.now().isoformat(),
                    "tasks_count": len(self.tasks),
                },
            )
        except Exception as e:
            self.logger.error(f"Failed to start automation manager: {e}")
            self.running = False

    def stop(self):
        """Stop the automation scheduler."""
        with self._lock:
            if not self.running:
                return

            self.running = True  # Avoid start/stop recursion issues

        try:
            if self._git_trigger is not None:
                self._git_trigger.stop()
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown()
            self.logger.info_sync("✅ Automation manager stopped")
        except Exception as e:
            self.logger.debug(f"❌ Error stopping automation manager: {e}")
        finally:
            self.running = False

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
                # Helper to run async wrapper in APScheduler thread
                def _run_wrapper_sync():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        return loop.run_until_complete(self._execute_task_wrapper(task_id, task))
                    finally:
                        loop.close()

                self.scheduler.add_job(
                    _run_wrapper_sync,
                    trigger=trigger,
                    args=[],
                    id=task_id,
                    name=task.get("name", task_id),
                    replace_existing=True,
                    coalesce=True,
                    max_instances=1,
                )

                human_readable = schedule_config.get("human_readable", "")
                self.logger.info_sync(f"📅 Scheduled task '{task.get('name')}' - {human_readable}")

        except Exception as e:
            self.logger.debug(f"❌ Failed to schedule task {task_id}: {e}")

    async def _execute_task_wrapper(self, task_id: str, task: Dict[str, Any]):
        """
        Wrapper for task execution with error handling and notifications.

        Args:
            task_id: Task identifier
            task: Task configuration
        """
        start = datetime.now()
        try:
            self.logger.info(f"🚀 Executing task: {task.get('name', task_id)}")

            # Check for threshold-based triggers
            if "check_tool" in task:
                result = self._check_threshold(task)
                if not result.get("should_proceed", True):
                    self.logger.info(f"Task {task_id} threshold check: no action needed")
                    duration = (datetime.now() - start).total_seconds()
                    self.record_execution(
                        task_id,
                        ExecutionRecord(
                            status="skipped", summary="Threshold check: no action needed", duration_seconds=duration
                        ),
                    )
                    return

            # Execute the registered callback if it exists
            if task_id in self.task_callbacks:
                callback = self.task_callbacks[task_id]
                if asyncio.iscoroutinefunction(callback):
                    await callback(task_id, task)
                else:
                    callback(task_id, task)

            duration = (datetime.now() - start).total_seconds()
            self.record_execution(
                task_id,
                ExecutionRecord(
                    status="success",
                    summary=f"Task '{task.get('name', task_id)}' completed",
                    duration_seconds=duration,
                ),
            )
            # Publish task execution event
            await self._publish_task_event(task_id, task, "execution_complete", "success")

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_execution(
                task_id,
                ExecutionRecord(
                    status="error",
                    summary=f"Task '{task.get('name', task_id)}' failed",
                    errors=[str(e)],
                    duration_seconds=duration,
                ),
            )
            self.logger.error(f"Error executing task {task_id}: {e}")
            await self._publish_task_event(task_id, task, "execution_error", str(e))

    def record_execution(self, task_id: str, record: ExecutionRecord) -> None:
        """Append an execution record to the task history and persist to disk.

        Trims history to MAX_HISTORY_PER_TASK entries.

        Args:
            task_id: The task identifier.
            record: The execution outcome to record.
        """
        with self._lock:
            if task_id not in self.tasks:
                return
            task = self.tasks[task_id]
            history: List[Dict] = task.setdefault("execution_history", [])
            history.append(record.model_dump())
            # Keep only the most recent MAX_HISTORY_PER_TASK entries
            if len(history) > self.MAX_HISTORY_PER_TASK:
                task["execution_history"] = history[-self.MAX_HISTORY_PER_TASK :]
            # Update convenience fields
            if record.status == "success":
                task["last_success"] = record.timestamp
            elif record.status == "error":
                task["last_error"] = record.timestamp
            self._save_tasks()

    def get_last_execution_summary(self, task_id: str) -> Optional[ExecutionRecord]:
        """Return the most recent ExecutionRecord for a task, or None.

        Args:
            task_id: The task identifier.

        Returns:
            The most recent ExecutionRecord, or None if no history exists.
        """
        task = self.tasks.get(task_id)
        if not task:
            return None
        history = task.get("execution_history", [])
        if not history:
            return None
        try:
            return ExecutionRecord.model_validate(history[-1])
        except Exception:
            return None

    # ------------------------------------------------------------------
    # E5: Git event trigger
    # ------------------------------------------------------------------

    def enable_git_trigger(self, repo_path: Path, min_changed_lines: int = 5) -> None:
        """Start a GitChangeTrigger that reschedules interval tasks on git changes.

        Args:
            repo_path: Path to the git repository root to monitor.
            min_changed_lines: Minimum line-delta to fire the trigger.
        """
        from backend.utils.core.system.git_change_trigger import GitChangeTrigger

        if self._git_trigger is not None:
            self.logger.info_sync("GitChangeTrigger already enabled; ignoring duplicate call.")
            return
        self._git_trigger = GitChangeTrigger(
            repo_path=repo_path,
            on_change_callback=self._on_git_change_detected_sync,
            logger=self.logger,
            min_changed_lines=min_changed_lines,
        )
        self._git_trigger.start()
        self.logger.info_sync(f"GitChangeTrigger enabled for repo: {repo_path}")

    def _on_git_change_detected_sync(self) -> None:
        """Synchronous wrapper for git change detection."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._on_git_change_detected())
        finally:
            loop.close()

    async def _on_git_change_detected(self) -> None:
        """Callback invoked by GitChangeTrigger when external git changes are detected.

        Reschedules all enabled interval tasks to run immediately, then
        publishes a ``git_change_detected`` event for the UI.
        """
        self.logger.info("GitChangeTrigger: external changes detected, rescheduling interval tasks")
        with self._lock:
            for task_id, task in self.tasks.items():
                if not task.get("enabled", True):
                    continue
                schedule_type = task.get("schedule", {}).get("type", "interval")
                if schedule_type == "interval" and self.running and self.scheduler:
                    try:
                        job = self.scheduler.get_job(task_id)
                        if job:
                            job.modify(next_run_time=datetime.now())
                            self.logger.info(f"  Rescheduled task '{task_id}' to run now")
                    except Exception as exc:
                        self.logger.warning(f"  Could not reschedule task '{task_id}': {exc}")
        await self.event_publisher.publish(
            "git_change_detected",
            {"timestamp": datetime.now().isoformat()},
        )

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

    async def _publish_task_event(self, task_id: str, task: Dict[str, Any], event_type: str, details: Any = None):
        """Publish a task execution event."""
        await self.event_publisher.publish(
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
            self.logger.info_sync(f"🔄 Reloaded tasks: {old_count} -> {new_count}")

    def get_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks."""
        return list(self.tasks.values())

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task."""
        return self.tasks.get(task_id)

    def update_task(self, task_id: str, updates: Dict[str, Any]):
        """Update a task configuration."""
        if task_id not in self.tasks:
            self.logger.info_sync(f"Task not found: {task_id}")
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

            self.logger.info_sync(f"✅ Updated task: {task_id}")
            return True
        except Exception as e:
            self.logger.info_sync(f"❌ Failed to update task {task_id}: {e}")
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
            self.logger.info_sync(f"❌ Failed to save tasks: {e}")


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
