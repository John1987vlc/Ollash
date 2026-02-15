from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IModelProvider(ABC):
    """
    Abstract Base Class defining the interface for any service that provides LLM clients.
    This ensures that agents can request LLM clients without knowing the underlying
    implementation details of how those clients are managed or provisioned.
    """

    @abstractmethod
    def get_client(self, role: str) -> Optional[Any]:
        """
        Retrieves an LLM client instance based on its designated role (e.g., "coder", "planner").
        The returned object should expose methods for interacting with the LLM (e.g., chat, generate).

        Args:
            role: The string identifier for the LLM client's role.

        Returns:
            An instance of an LLM client (e.g., OllamaClient) or None if not found.
        """
        pass

    @abstractmethod
    def get_embedding_client(self) -> Optional[Any]:
        """
        Retrieves an LLM client instance specifically designated for generating embeddings.

        Returns:
            An instance of an LLM client capable of generating embeddings (e.g., OllamaClient)
            or None if not found.
        """
        pass

    @abstractmethod
    def get_all_clients(self) -> Dict[str, Any]:
        """
        Retrieves a dictionary of all initialized LLM client instances, keyed by their roles.

        Returns:
            A dictionary where keys are role strings and values are LLM client instances.
        """
        pass
