from abc import ABC, abstractmethod
from typing import Any


class IToolExecutor(ABC):
    """
    Abstract Base Class defining the interface for executing tools.
    This decouples the agent's decision-making logic from the concrete
    implementation of how tools are invoked and their results processed.
    """

    @abstractmethod
    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Executes a tool identified by its name with the given arguments.

        Args:
            tool_name: The name of the tool to be executed.
            **kwargs: Arbitrary keyword arguments to pass to the tool's function.

        Returns:
            The result of the tool's execution.
        """
        pass
