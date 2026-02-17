"""Ollama LLM provider implementation.

Wraps the existing OllamaClient to conform to the ILLMProvider interface.
"""

from typing import Any, Dict, List, Optional

from backend.utils.core.agent_logger import AgentLogger


class OllamaProvider:
    """LLM provider backed by a local Ollama server.

    Wraps OllamaClient with the standard provider interface.
    """

    PROVIDER_TYPE = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mistral:latest",
        timeout: int = 300,
        logger: Optional[AgentLogger] = None,
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.logger = logger
        self._client = None

    def _get_client(self) -> Any:
        """Lazy-initialize the OllamaClient."""
        if self._client is None:
            from backend.utils.core.ollama_client import OllamaClient

            self._client = OllamaClient(
                url=self.base_url,
                model=self.model,
                timeout=self.timeout,
                logger=self.logger,
            )
        return self._client

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.5,
    ) -> Dict[str, Any]:
        """Send a chat request to Ollama."""
        client = self._get_client()
        return client.chat(messages=messages, tools=tools, temperature=temperature)

    def embed(self, text: str) -> List[float]:
        """Generate embeddings via Ollama."""
        client = self._get_client()
        return client.embed(text=text)

    def supports_tools(self) -> bool:
        """Ollama supports tool calling."""
        return True

    def supports_vision(self) -> bool:
        """Vision support depends on the model (llava, bakllava)."""
        vision_models = {"llava", "bakllava", "llava-llama3", "moondream"}
        return any(vm in self.model.lower() for vm in vision_models)

    def get_raw_client(self) -> Any:
        """Get the underlying OllamaClient for backward compatibility."""
        return self._get_client()
