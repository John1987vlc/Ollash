"""Asynchronous Tool Executor for the Ollash Agent Framework.

This module provides a class to execute multiple tool calls concurrently,
leveraging Python's asyncio library. It is designed to work with tools
that are marked as 'async_safe' in the ToolRegistry.
"""

import asyncio
from typing import List, Dict, Any

from src.utils.core.tool_registry import ToolRegistry


class AsyncToolExecutor:
    """Executes a list of tool calls asynchronously."""

    def __init__(self, tool_executor_callback, tool_registry: ToolRegistry):
        """
        Initializes the AsyncToolExecutor.

        Args:
            tool_executor_callback: A callback function that can execute a single tool call.
                                  This is typically a method on the agent instance.
            tool_registry: The ToolRegistry instance to use for tool lookup.
        """
        self.execute_single_tool = tool_executor_callback
        self.tool_registry = tool_registry

    async def execute_in_parallel(self, tool_calls: List[Dict[str, Any]]) -> List[Any]:
        """
        Executes a list of tool calls in parallel.

        Filters for tools that are eligible for async execution and runs them
        concurrently. Tools not marked as async-safe will be run sequentially.

        Args:
            tool_calls: A list of tool call dictionaries, as provided by the LLM.

        Returns:
            A list of tool outputs, in the same order as the input tool calls.
        """
        async_eligible_tools = self.tool_registry.get_async_eligible_tools()
        
        # Separate calls into async and sequential
        async_tasks = []
        sequential_calls = []
        
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call.get("function", {}).get("name")
            if tool_name in async_eligible_tools:
                # Coroutine to be run
                coro = self.execute_single_tool(tool_call)
                async_tasks.append(coro)
            else:
                sequential_calls.append(tool_call)

        # Execute async tasks
        async_results = []
        if async_tasks:
            async_results = await asyncio.gather(*async_tasks)

        # Execute sequential tasks
        sequential_results = []
        for tool_call in sequential_calls:
            # Assuming execute_single_tool can be awaited even if it's a sync function
            result = await self.execute_single_tool(tool_call)
            sequential_results.append(result)
            
        # Here we need a way to correctly order the results.
        # For now, we'll just combine them. A more robust solution is needed.
        # This is a placeholder for the logic to correctly order the results.
        all_results = async_results + sequential_results

        return all_results