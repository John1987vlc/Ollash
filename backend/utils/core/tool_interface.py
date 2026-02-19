import asyncio
from typing import Any, Dict, List  # Added Callable

from backend.interfaces.itool_executor import IToolExecutor
from backend.utils.core.tool_registry import ToolRegistry


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
        """
        tool_func = self.tool_registry.get_callable_tool_function(tool_name, self.agent_instance)

        if asyncio.iscoroutinefunction(tool_func):
            result = await tool_func(**kwargs)
        else:
            result = tool_func(**kwargs)
            # F15: Extra safety check - if the result is a coroutine (async), await it
            if asyncio.iscoroutine(result):
                result = await result

        return result
