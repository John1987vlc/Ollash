from typing import List, Dict, Any, Optional
from datetime import datetime
from colorama import Fore, Style
import json
from pathlib import Path

from src.utils.core.tool_decorator import ollash_tool

class PlanningTools:
    def __init__(self, logger: Any, project_root: Path, agent_instance: Any):
        self.logger = logger
        self.project_root = project_root
        self.agent = agent_instance # Store reference to the DefaultAgent instance

    @ollash_tool(
        name="plan_actions",
        description="Display and return the action plan for a given goal.",
        parameters={
            "goal": {"type": "string", "description": "The main objective."},
            "steps": {"type": "array", "description": "A list of steps to achieve the goal.", "items": {"type": "string"}},
            "requires_confirmation": {"type": "boolean", "description": "Whether the plan requires user confirmation before execution."},
        },
        toolset_id="planning_tools",
        agent_types=["orchestrator", "planner"],
        required=["goal", "steps"]
    )
    def plan_actions(self, goal: str, steps: List[str], requires_confirmation: bool = False):
        """Display and return the action plan"""
        plan = {
            "goal": goal,
            "steps": steps,
            "requires_confirmation": requires_confirmation,
            "created_at": datetime.now().isoformat()
        }
        
        self.logger.info(f"\n{Fore.CYAN}{'='*60}")
        self.logger.info("📋 ACTION PLAN")
        self.logger.info(f"{'='*60}{Style.RESET_ALL}")
        self.logger.info(f"🎯 Goal: {Fore.WHITE}{goal}{Style.RESET_ALL}")
        self.logger.info(f"\n📝 Steps ({len(steps)}):")
        for i, step in enumerate(steps, 1):
            self.logger.info(f"  {Fore.YELLOW}{i}.{Style.RESET_ALL} {step}")
        self.logger.info(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
        
        self.logger.info(f"Plan created: {goal}")
        for i, step in enumerate(steps, 1):
            self.logger.debug(f"  Step {i}: {step}")
        
        return {
            "ok": True,
            "goal": goal,
            "steps": steps,
            "plan_displayed": True,
            "plan_data": plan # Return the full plan data
        }

    @ollash_tool(
        name="run_async_tool",
        description="Submits a tool for asynchronous execution and returns a task ID.",
        parameters={
            "tool_name": {"type": "string", "description": "The name of the tool to execute asynchronously."},
        },
        toolset_id="planning_tools",
        agent_types=["orchestrator"],
        required=["tool_name"]
    )
    def run_async_tool(self, tool_name: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Submits a tool for asynchronous execution and returns a task ID.
        """
        try:
            tool_func = self.agent._get_tool_from_toolset(tool_name)
            task_id = self.agent.async_tool_executor.submit(tool_func, **kwargs)
            return {"ok": True, "task_id": task_id, "status": "submitted"}
        except (ValueError, AttributeError) as e:
            self.logger.error(f"Error submitting async tool {tool_name}: {e}")
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="check_async_task_status",
        description="Checks the status of an asynchronous task by its ID.",
        parameters={
            "task_id": {"type": "string", "description": "The ID of the task to check."},
        },
        toolset_id="planning_tools",
        agent_types=["orchestrator"],
        required=["task_id"]
    )
    def check_async_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Checks the status of an asynchronous task by its ID.
        """
        status = self.agent.async_tool_executor.get_status(task_id)
        return {"ok": True, **status}

    @ollash_tool(
        name="set_user_preference",
        description="Sets a preference value for the user.",
        parameters={
            "key": {"type": "string", "description": "The preference key."},
            "value": {"type": "string", "description": "The preference value."},
        },
        toolset_id="planning_tools",
        agent_types=["orchestrator"],
        required=["key", "value"]
    )
    def set_user_preference(self, key: str, value: Any) -> Dict[str, Any]:
        """Sets a user preference."""
        try:
            self.agent.memory_manager.get_preference_manager().set(key, value)
            self.logger.info(f"Set user preference '{key}' to '{value}'")
            return {"ok": True, "key": key, "value": value}
        except Exception as e:
            self.logger.error(f"Failed to set user preference '{key}': {e}")
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="get_user_preference",
        description="Gets a preference value for the user.",
        parameters={
            "key": {"type": "string", "description": "The preference key."},
            "default": {"type": "string", "description": "The default value if the key is not found."},
        },
        toolset_id="planning_tools",
        agent_types=["orchestrator"],
        required=["key"]
    )
    def get_user_preference(self, key: str, default: Any = None) -> Dict[str, Any]:
        """Gets a user preference."""
        try:
            value = self.agent.memory_manager.get_preference_manager().get(key, default)
            return {"ok": True, "key": key, "value": value}
        except Exception as e:
            self.logger.error(f"Failed to get user preference '{key}': {e}")
            return {"ok": False, "error": str(e)}

