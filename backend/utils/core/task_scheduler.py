"""Task Scheduler for Ollash - Manages scheduled task execution."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Manages scheduled automation tasks."""

    def __init__(self):
        """Initialize the task scheduler."""
        self.scheduler = None
        self._callback = None

    def initialize(self):
        """Initialize and start the scheduler."""
        if self.scheduler is None:
            self.scheduler = BackgroundScheduler(daemon=True)
            try:
                self.scheduler.start()
                logger.info("Task scheduler started successfully")
            except Exception as e:
                logger.error(f"Failed to start task scheduler: {e}")

    def set_callback(self, callback):
        """
        Set the callback function to execute tasks.
        
        Args:
            callback: Async function that takes (task_id, task_data) and executes the task
        """
        self._callback = callback

    def schedule_task(self, task_id: str, task_data: dict) -> bool:
        """
        Schedule a new task.
        
        Args:
            task_id: Unique task identifier
            task_data: Task configuration dict with keys:
                - schedule: 'hourly', 'daily', 'weekly', or 'custom'
                - cron: cron expression (if schedule is 'custom')
                - agent: agent type to use
                - prompt: prompt to execute
        
        Returns:
            bool: True if scheduled successfully, False otherwise
        """
        if self.scheduler is None:
            self.initialize()

        try:
            trigger = self._get_trigger(task_data)
            
            if trigger is None:
                logger.error(f"Invalid schedule configuration: {task_data}")
                return False

            # Create job args
            job_args = [task_id, task_data]

            # Schedule the job
            self.scheduler.add_job(
                func=self._execute_task,
                trigger=trigger,
                args=job_args,
                id=task_id,
                name=task_data.get('name', 'Unnamed Task'),
                replace_existing=True,
                max_instances=1
            )

            logger.info(f"Task {task_id} scheduled successfully")
            return True

        except Exception as e:
            logger.error(f"Error scheduling task {task_id}: {e}")
            return False

    def unschedule_task(self, task_id: str) -> bool:
        """
        Remove a scheduled task.
        
        Args:
            task_id: Task identifier to remove
        
        Returns:
            bool: True if removed successfully, False otherwise
        """
        if self.scheduler is None:
            return False

        try:
            self.scheduler.remove_job(task_id)
            logger.info(f"Task {task_id} unscheduled")
            return True
        except Exception as e:
            logger.error(f"Error unscheduling task {task_id}: {e}")
            return False

    def pause_task(self, task_id: str) -> bool:
        """Pause a task without removing it."""
        if self.scheduler is None:
            return False

        try:
            job = self.scheduler.get_job(task_id)
            if job:
                job.pause()
                logger.info(f"Task {task_id} paused")
                return True
            return False
        except Exception as e:
            logger.error(f"Error pausing task {task_id}: {e}")
            return False

    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        if self.scheduler is None:
            return False

        try:
            job = self.scheduler.get_job(task_id)
            if job:
                job.resume()
                logger.info(f"Task {task_id} resumed")
                return True
            return False
        except Exception as e:
            logger.error(f"Error resuming task {task_id}: {e}")
            return False

    def get_task_info(self, task_id: str) -> dict:
        """
        Get information about a scheduled task.
        
        Returns:
            dict with task details or None if not found
        """
        if self.scheduler is None:
            return None

        try:
            job = self.scheduler.get_job(task_id)
            if job:
                return {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger),
                    'paused': job.paused
                }
            return None
        except Exception as e:
            logger.error(f"Error getting task info {task_id}: {e}")
            return None

    def list_all_tasks(self) -> list:
        """Get all scheduled tasks."""
        if self.scheduler is None:
            return []

        try:
            jobs = self.scheduler.get_jobs()
            return [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger),
                    'paused': job.paused
                }
                for job in jobs
            ]
        except Exception as e:
            logger.error(f"Error listing tasks: {e}")
            return []

    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler:
            try:
                self.scheduler.shutdown()
                logger.info("Task scheduler shut down")
            except Exception as e:
                logger.error(f"Error shutting down scheduler: {e}")

    # ==================== Private Methods ====================

    def _get_trigger(self, task_data: dict):
        """
        Get the appropriate trigger based on schedule configuration.
        
        Args:
            task_data: Task configuration dict
        
        Returns:
            APScheduler trigger object or None
        """
        schedule_type = task_data.get('schedule')

        try:
            if schedule_type == 'hourly':
                return IntervalTrigger(hours=1)
            elif schedule_type == 'daily':
                # Daily at 8:00 AM
                return CronTrigger(hour=8, minute=0)
            elif schedule_type == 'weekly':
                # Weekly on Monday at 8:00 AM
                return CronTrigger(day_of_week='0', hour=8, minute=0)
            elif schedule_type == 'custom':
                # Use provided cron expression
                cron_expr = task_data.get('cron', '0 8 * * *')
                return CronTrigger.from_crontab(cron_expr)
            else:
                logger.warning(f"Unknown schedule type: {schedule_type}")
                return None
        except Exception as e:
            logger.error(f"Error creating trigger: {e}")
            return None

    async def _execute_task(self, task_id: str, task_data: dict):
        """
        Execute a scheduled task.
        
        Args:
            task_id: Task identifier
            task_data: Task configuration
        """
        try:
            logger.info(f"Executing task {task_id}")
            
            # Call the registered callback if available
            if self._callback:
                await self._callback(task_id, task_data)
            else:
                logger.warning(f"No callback registered for task execution")

        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}")


# Global scheduler instance
_scheduler_instance = None


def get_scheduler() -> TaskScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = TaskScheduler()
        _scheduler_instance.initialize()
    return _scheduler_instance
