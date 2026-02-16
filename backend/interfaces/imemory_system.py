from abc import ABC, abstractmethod
from typing import Any, List, Optional


class IMemorySystem(ABC):
    """
    Abstract Base Class defining the interface for agent memory management.
    This provides a consistent way for agents to interact with persistent
    storage (e.g., ChromaDB) without direct knowledge of the underlying
    database implementation.
    """

    @abstractmethod
    async def store_agent_memory(self, agent_id: str, key: str, data: Any) -> None:
        """
        Stores a piece of data in the agent's memory under a specific key.

        Args:
            agent_id: The unique identifier for the agent.
            key: The key under which to store the data.
            data: The data to be stored (can be any serializable type).
        """
        pass

    @abstractmethod
    async def retrieve_agent_memory(self, agent_id: str, key: str) -> Optional[Any]:
        """
        Retrieves a piece of data from the agent's memory using its key.

        Args:
            agent_id: The unique identifier for the agent.
            key: The key for the data to retrieve.

        Returns:
            The retrieved data, or None if the key is not found.
        """
        pass

    @abstractmethod
    async def list_agent_memory_keys(self, agent_id: str) -> List[str]:
        """
        Lists all keys under which data is stored for a specific agent.

        Args:
            agent_id: The unique identifier for the agent.

        Returns:
            A list of strings representing the keys in the agent's memory.
        """
        pass

    @abstractmethod
    async def clear_agent_memory(self, agent_id: str, key: Optional[str] = None) -> None:
        """
        Clears all or a specific part of an agent's memory.

        Args:
            agent_id: The unique identifier for the agent.
            key: If provided, only clears the data associated with this key.
                 If None, clears all memory for the agent.
        """
        pass
