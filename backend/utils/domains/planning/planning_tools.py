from typing import Any, Dict, List
from pathlib import Path # Added
from backend.utils.core.tool_decorator import ollash_tool

class PlanningTools:
    """
    A collection of tools related to planning, agent orchestration, and asynchronous task management.
    """
    def __init__(self, logger: Any, project_root: Path, agent_instance: Any):
        self.logger = logger
        self.project_root = project_root
        self.agent_instance = agent_instance # Used for delegating tool execution

    @ollash_tool(
        name="plan_actions",
        description="Create a step-by-step plan before taking actions. ALWAYS use this first.",
        parameters={
            "goal": {"type": "string", "description": "Main objective to accomplish"},
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Detailed list of steps to accomplish the goal"
            },
            "requires_confirmation": {
                "type": "boolean",
                "description": "Whether this plan requires user confirmation before execution"
            }
        },
        required=["goal", "steps"],
        toolset_id="planning_tools",
        agent_types=["orchestrator"]
    )
    def plan_actions(self, goal: str, steps: List[str], requires_confirmation: bool = False) -> Dict:
        """
        Creates a step-by-step plan for the agent to follow.
        """
        self.logger.info(f"Agent planning actions for goal: {goal}")
        for i, step in enumerate(steps):
            self.logger.info(f"Step {i+1}: {step}")
        
        return {
            "ok": True,
            "result": {
                "message": "Plan created successfully.",
                "goal": goal,
                "steps": steps,
                "requires_confirmation": requires_confirmation
            }
        }

    @ollash_tool(
        name="select_agent_type",
        description="Switches the agent's active persona and toolset to a specialized domain (e.g., 'code', 'system', 'network', 'cybersecurity', 'orchestrator'). This is a meta-tool for agent self-modification.",
        parameters={
            "agent_type": {"type": "string", "enum": ["orchestrator", "code", "network", "system", "cybersecurity", "bonus"], "description": "The type of specialized agent to switch to."},
            "reason": {"type": "string", "description": "Explanation for why the agent type switch is necessary."}
        },
        required=["agent_type", "reason"],
        toolset_id="planning_tools",
        agent_types=["orchestrator"]
    )
    def select_agent_type(self, agent_type: str, reason: str) -> Dict:
        """
        Allows the orchestrator agent to switch to a specialized agent type.
        This tool is handled internally by the agent to change its context and available tools.
        """
        self.logger.info(f"Agent requesting switch to agent type: {agent_type} because {reason}")
        # This tool's actual logic (changing agent type) is handled by the calling agent (DefaultAgent)
        return {
            "ok": True,
            "result": {
                "message": f"Agent switch requested to {agent_type} for reason: {reason}. This action is handled internally by the agent."
            }
        }

    @ollash_tool(
        name="run_async_tool",
        description="Submits a tool for asynchronous execution and returns a task ID.",
        parameters={
            "tool_name": {"type": "string", "description": "The name of the tool to execute asynchronously."},
            "kwargs": {"type": "object", "description": "The keyword arguments to pass to the tool."}
        },
        required=["tool_name"],
        toolset_id="planning_tools",
        agent_types=["orchestrator"] # Orchestrator can initiate async tasks
    )
    async def run_async_tool(self, tool_name: str, kwargs: Dict = None) -> Dict:
        """
        Submits a tool to the asynchronous executor.
        """
        if kwargs is None:
            kwargs = {}
        self.logger.info(f"Submitting tool '{tool_name}' for async execution with args: {kwargs}")
        
        # Delegate to the agent's async_tool_executor
        if hasattr(self.agent_instance, 'async_tool_executor') and self.agent_instance.async_tool_executor:
            # The async_tool_executor expects a tool_call dict, not individual name/kwargs
            tool_call_dict = {"function": {"name": tool_name, "arguments": kwargs}}
            task_id = await self.agent_instance.async_tool_executor.submit_single_tool_call(tool_call_dict)
            return {
                "ok": True,
                "result": {
                    "message": f"Tool '{tool_name}' submitted for async execution.",
                    "task_id": task_id
                }
            }
        else:
            self.logger.error("AsyncToolExecutor not available on agent instance.")
            return {
                "ok": False,
                "result": {
                    "error": "Asynchronous tool executor not initialized."
                }
            }

    @ollash_tool(
        name="check_async_task_status",
        description="Checks the status of an asynchronous task by its ID.",
        parameters={
            "task_id": {"type": "string", "description": "The ID of the task to check."}
        },
        required=["task_id"],
        toolset_id="planning_tools",
        agent_types=["orchestrator"]
    )
    async def check_async_task_status(self, task_id: str) -> Dict:
        """
        Checks the status of a previously submitted asynchronous task.
        """
        self.logger.info(f"Checking status for async task ID: {task_id}")
        
        if hasattr(self.agent_instance, 'async_tool_executor') and self.agent_instance.async_tool_executor:
            status = await self.agent_instance.async_tool_executor.get_task_status(task_id)
            return {
                "ok": True,
                "result": {
                    "task_id": task_id,
                    "status": status.get('status'),
                    "output": status.get('output'),
                    "error": status.get('error')
                }
            }
        else:
            self.logger.error("AsyncToolExecutor not available on agent instance.")
            return {
                "ok": False,
                "result": {
                    "error": "Asynchronous tool executor not initialized."
                }
            }