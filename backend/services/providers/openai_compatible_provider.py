"""OpenAI-compatible LLM provider implementation.

Supports any API that implements the OpenAI chat completions format:
Groq, Together, OpenRouter, local vLLM, etc.
"""

from typing import Any, Dict, List, Optional

import aiohttp

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.exceptions import ProviderAuthenticationError, ProviderConnectionError


class OpenAICompatibleProvider:
    """LLM provider for OpenAI-compatible APIs.

    Works with: Groq, Together AI, OpenRouter, Fireworks AI,
    local vLLM/text-generation-inference servers, etc.
    """

    PROVIDER_TYPE = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        model: str = "default",
        timeout: int = 120,
        logger: Optional[AgentLogger] = None,
        provider_name: str = "openai_compatible",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.logger = logger
        self.provider_name = provider_name

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.5,
    ) -> Dict[str, Any]:
        """Send a synchronous chat request to the OpenAI-compatible API."""
        import requests

        url = f"{self.base_url}/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout,
            )

            if resp.status_code == 401:
                raise ProviderAuthenticationError(self.provider_name)
            resp.raise_for_status()

            data = resp.json()

            # Normalize to Ollama-like response format for compatibility
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})

            return {
                "message": {
                    "role": message.get("role", "assistant"),
                    "content": message.get("content", ""),
                    "tool_calls": message.get("tool_calls"),
                },
                "usage": data.get("usage", {}),
            }
        except ProviderAuthenticationError:
            raise
        except requests.exceptions.ConnectionError as e:
            raise ProviderConnectionError(self.provider_name, str(e)) from e
        except Exception as e:
            if self.logger:
                self.logger.error(f"OpenAI-compatible API error: {e}")
            raise ProviderConnectionError(self.provider_name, str(e)) from e

    async def async_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.5,
    ) -> Dict[str, Any]:
        """Send an async chat request to the OpenAI-compatible API."""
        url = f"{self.base_url}/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=self._get_headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status == 401:
                        raise ProviderAuthenticationError(self.provider_name)
                    resp.raise_for_status()
                    data = await resp.json()

                    choice = data.get("choices", [{}])[0]
                    message = choice.get("message", {})

                    return {
                        "message": {
                            "role": message.get("role", "assistant"),
                            "content": message.get("content", ""),
                            "tool_calls": message.get("tool_calls"),
                        },
                        "usage": data.get("usage", {}),
                    }
        except ProviderAuthenticationError:
            raise
        except aiohttp.ClientConnectorError as e:
            raise ProviderConnectionError(self.provider_name, str(e)) from e
        except Exception as e:
            if self.logger:
                self.logger.error(f"Async OpenAI-compatible API error: {e}")
            raise ProviderConnectionError(self.provider_name, str(e)) from e

    def embed(self, text: str) -> List[float]:
        """Generate embeddings via the OpenAI-compatible embeddings API."""
        import requests

        url = f"{self.base_url}/v1/embeddings"
        payload = {"model": self.model, "input": text}

        try:
            resp = requests.post(url, headers=self._get_headers(), json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [{}])[0].get("embedding", [])
        except Exception as e:
            if self.logger:
                self.logger.error(f"Embedding API error: {e}")
            return []

    def supports_tools(self) -> bool:
        """Most OpenAI-compatible APIs support tool calling."""
        return True

    def supports_vision(self) -> bool:
        """Vision support depends on the model."""
        return False
