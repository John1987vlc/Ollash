import asyncio
from typing import Any, Dict, List  # Added Callable

from backend.interfaces.itool_executor import IToolExecutor
from backend.utils.core.tools.tool_registry import ToolRegistry


class ToolExecutor(IToolExecutor):
    """
    Executes tools by delegating to an instantiated ToolRegistry.
    This class implements the IToolExecutor interface.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,  # Now receives an instantiated ToolRegistry
        agent_instance: Any,  # Pass the agent_instance down to ToolRegistry
    ):
        self.tool_registry = tool_registry
        self.agent_instance = agent_instance  # Used to pass to ToolRegistry's get_callable_tool_function

    def get_tool_definitions(self, tool_names: List[str]) -> List[Dict]:
        """Returns the OpenAPI-like definitions for a list of tool names."""
        return self.tool_registry.get_tool_definitions(tool_names)

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Executes a tool identified by its name with the given arguments.
        Delegates to the ToolRegistry to get and execute the callable function.
        Includes safety filtering for stray arguments from smaller models.
        """
        tool_func = self.tool_registry.get_callable_tool_function(tool_name, self.agent_instance)

        # F33: Robust argument filtering
        import inspect

        sig = inspect.signature(tool_func)
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

        # Log if we filtered something out
        if len(filtered_kwargs) < len(kwargs):
            ignored = set(kwargs.keys()) - set(filtered_kwargs.keys())
            # Use self.agent_instance.logger if available
            if hasattr(self.agent_instance, "logger"):
                self.agent_instance.logger.warning(f"⚠️ Filtered out unexpected arguments for {tool_name}: {ignored}")

        if asyncio.iscoroutinefunction(tool_func):
            result = await tool_func(**filtered_kwargs)
        else:
            result = tool_func(**filtered_kwargs)
            # F15: Extra safety check - if the result is a coroutine (async), await it
            if asyncio.iscoroutine(result):
                result = await result

        return result
