"""
Automation Task Executor - Executes scheduled automation tasks with conditional triggers
"""

import asyncio
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from backend.agents.default_agent import DefaultAgent
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.core.system.metrics_database import get_metrics_database
from backend.utils.core.system.notification_manager import get_notification_manager
from backend.utils.core.system.trigger_manager import get_trigger_manager
from frontend.services.chat_event_bridge import ChatEventBridge

logger = logging.getLogger(__name__)


class AutomationTaskExecutor:
    """Executes automated tasks with specified agents."""

    def __init__(self, ollash_root_dir: Path, event_publisher: EventPublisher):
        """
        Initialize the executor.

        Args:
            ollash_root_dir: Root directory of Ollash
            event_publisher: Event publisher instance for notifications
        """
        self.ollash_root_dir = ollash_root_dir
        self.event_publisher = event_publisher
        self.notification_manager = get_notification_manager()
        self.metrics_db = get_metrics_database(ollash_root_dir)
        self.trigger_manager = get_trigger_manager()
        self._lock = threading.Lock()

    def evaluate_conditional_triggers(self, context: Dict[str, Any] = None) -> list:
        """
        Evaluate all conditional triggers and return triggered rules.

        Args:
            context: Optional system context. If None, will gather from metrics.

        Returns:
            List of triggered rules with their actions
        """
        if context is None:
            context = self._gather_system_context()

        return self.trigger_manager.evaluate_all(context, cooldown_minutes=5)

    def _gather_system_context(self) -> Dict[str, Any]:
        """
        Gather current system context from metrics database.

        Returns:
            Dictionary with system state information
        """
        try:
            context = {
                "timestamp": datetime.now().isoformat(),
                "system": {},
                "network": {},
                "security": {},
            }

            # Gather system metrics
            for metric_file in self.metrics_db.db_path.glob("system_*.json"):
                metric_name = metric_file.stem.replace("system_", "")
                latest = self.metrics_db.get_latest_metric("system", metric_name)
                if latest:
                    context["system"][metric_name] = latest.get("value")

            # Gather network metrics
            for metric_file in self.metrics_db.db_path.glob("network_*.json"):
                metric_name = metric_file.stem.replace("network_", "")
                latest = self.metrics_db.get_latest_metric("network", metric_name)
                if latest:
                    context["network"][metric_name] = latest.get("value")

            # Gather security metrics
            for metric_file in self.metrics_db.db_path.glob("security_*.json"):
                metric_name = metric_file.stem.replace("security_", "")
                latest = self.metrics_db.get_latest_metric("security", metric_name)
                if latest:
                    context["security"][metric_name] = latest.get("value")

            return context

        except Exception as e:
            logger.error(f"Error gathering system context: {e}")
            return {"timestamp": datetime.now().isoformat()}

    async def execute_triggered_actions(self, triggered_rules: list) -> list:
        """
        Execute actions from triggered rules.

        Args:
            triggered_rules: List of triggered rules with actions

        Returns:
            List of execution results
        """
        results = []

        for rule in triggered_rules:
            actions = rule.get("actions", [])

            for action in actions:
                try:
                    action_type = action.get("type")

                    if action_type == "execute_prompt":
                        # Execute an agent prompt
                        result = await self.execute_task(
                            task_id=f"trigger_{rule['trigger_id']}_{datetime.now().timestamp()}",
                            task_data={
                                "name": action.get("name", "Triggered Action"),
                                "agent": action.get("agent", "orchestrator"),
                                "prompt": action.get("prompt", ""),
                                "notifyEmail": action.get("notify_email", False),
                            },
                        )
                        results.append(result)

                    elif action_type == "send_notification":
                        # Send notification
                        self.notification_manager.send_alert(
                            title=action.get("title", "Automation Alert"),
                            message=action.get("message", ""),
                            severity=action.get("severity", "info"),
                        )
                        results.append({"action": "notification_sent", "status": "success"})

                    elif action_type == "publish_event":
                        # Publish event
                        self.event_publisher.publish(
                            action.get("event_name", "automation:triggered"),
                            event_data=action.get("event_data", {}),
                        )
                        results.append({"action": "event_published", "status": "success"})

                except Exception as e:
                    logger.error(f"Error executing triggered action: {e}")
                    results.append(
                        {
                            "action": action.get("name", "unknown"),
                            "status": "error",
                            "error": str(e),
                        }
                    )

        return results

    async def execute_task(
        self,
        task_id: str,
        task_data: Dict[str, Any],
        recipient_emails: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Execute an automation task.

        Args:
            task_id: Unique task identifier
            task_data: Task configuration with keys:
                - name: Task name
                - agent: Agent type ('system', 'network', 'cybersecurity', etc.)
                - prompt: Prompt to execute
                - notifyEmail: Whether to send email notification
            recipient_emails: List of email addresses for notifications

        Returns:
            dict with execution result: {
                'status': 'success' | 'error',
                'output': str,
                'error': str (if error),
                'executed_at': ISO timestamp
            }
        """
        task_name = task_data.get("name", "Unknown Task")
        agent_type = task_data.get("agent", "orchestrator")
        prompt = task_data.get("prompt", "")
        notify_email = task_data.get("notifyEmail", False)

        result = {
            "task_id": task_id,
            "task_name": task_name,
            "agent_type": agent_type,
            "status": "error",
            "output": "",
            "error": None,
        }

        try:
            logger.info(f"Executing task {task_id}: {task_name} with agent {agent_type}")

            # Create a temporary event bridge for this execution
            bridge = ChatEventBridge(self.event_publisher)

            # Create agent instance
            agent = DefaultAgent(
                project_root=None,
                auto_confirm=True,
                base_path=self.ollash_root_dir,
                event_bridge=bridge,
            )

            # Set agent type
            if agent_type and agent_type in agent._agent_tool_name_mappings:
                agent.active_agent_type = agent_type
                agent.active_tool_names = agent._agent_tool_name_mappings[agent_type]

            # Execute prompt in thread to avoid blocking
            output = await asyncio.to_thread(agent.chat, prompt)

            result["status"] = "success"
            result["output"] = output
            logger.info(f"Task {task_id} completed successfully")

            # Send email notification if requested
            if notify_email and recipient_emails:
                self.notification_manager.send_task_completion(
                    task_name=task_name,
                    agent_type=agent_type,
                    result=output,
                    recipient_emails=recipient_emails,
                    success=True,
                )

            # Publish event for UI feedback
            self.event_publisher.publish(
                "task:completed",
                event_data={
                    "task_id": task_id,
                    "task_name": task_name,
                    "output": output,
                },
            )

        except Exception as e:
            error_msg = str(e)
            result["status"] = "error"
            result["error"] = error_msg
            logger.error(f"Task {task_id} failed with error: {error_msg}", exc_info=True)

            # Send error notification email
            if notify_email and recipient_emails:
                self.notification_manager.send_error_notification(
                    task_name=task_name,
                    error_message=error_msg,
                    error_type="Agent Execution Error",
                    recipient_emails=recipient_emails,
                )

            # Publish error event
            self.event_publisher.publish(
                "task:error",
                event_data={
                    "task_id": task_id,
                    "task_name": task_name,
                    "error": error_msg,
                },
            )

        return result

    def execute_task_sync(
        self,
        task_id: str,
        task_data: Dict[str, Any],
        recipient_emails: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Execute task synchronously (blocking).
        Used by APScheduler which doesn't support async callbacks.

        Args:
            task_id: Unique task identifier
            task_data: Task configuration
            recipient_emails: List of email addresses

        Returns:
            dict with execution result
        """
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(self.execute_task(task_id, task_data, recipient_emails))
            return result
        finally:
            loop.close()


# Global executor instance
_executor_instance = None


def get_task_executor(
    ollash_root_dir: Optional[Path] = None,
    event_publisher: Optional[EventPublisher] = None,
) -> AutomationTaskExecutor:
    """
    Get or create the global task executor instance.

    Args:
        ollash_root_dir: Root directory (required for first initialization)
        event_publisher: Event publisher (required for first initialization)

    Returns:
        AutomationTaskExecutor instance
    """
    global _executor_instance

    if _executor_instance is None:
        if ollash_root_dir is None or event_publisher is None:
            raise ValueError("ollash_root_dir and event_publisher required for first initialization")
        _executor_instance = AutomationTaskExecutor(ollash_root_dir, event_publisher)

    return _executor_instance
