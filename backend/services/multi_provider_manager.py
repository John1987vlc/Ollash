"""Multi-Provider LLM Manager

Routes LLM requests to different providers (Ollama, OpenAI-compatible, etc.)
based on role configuration. Extends LLMClientManager for backward compatibility.
"""

from typing import Any, Dict, List, Optional

from backend.core.config_schemas import LLMModelsConfig, ToolSettingsConfig
from backend.interfaces.imodel_provider import IModelProvider
from backend.services.providers.ollama_provider import OllamaProvider
from backend.services.providers.openai_compatible_provider import OpenAICompatibleProvider
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.exceptions import ProviderConnectionError


class ProviderConfig:
    """Configuration for an LLM provider."""

    def __init__(
        self,
        name: str,
        provider_type: str = "ollama",
        base_url: str = "http://localhost:11434",
        api_key: Optional[str] = None,
        models: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ):
        self.name = name
        self.provider_type = provider_type
        self.base_url = base_url
        self.api_key = api_key
        self.models = models or {}
        self.timeout = timeout


class MultiProviderManager(IModelProvider):
    """Manages multiple LLM providers and routes requests by role.

    Extends the provider pattern to support:
    - Local Ollama server
    - OpenAI-compatible APIs (Groq, Together, OpenRouter, etc.)
    - Role-based provider selection

    Usage:
        manager = MultiProviderManager(llm_config, tool_settings, logger)
        manager.register_provider(ProviderConfig(
            name="groq", provider_type="openai_compatible",
            base_url="https://api.groq.com/openai",
            api_key="gsk_...",
            models={"senior_reviewer": "llama-3.3-70b-versatile"}
        ))
        client = manager.get_client("senior_reviewer")  # Returns Groq provider
    """

    def __init__(
        self,
        config: LLMModelsConfig,
        tool_settings: ToolSettingsConfig,
        logger: AgentLogger,
        recorder: Optional[Any] = None,
    ):
        self.config = config
        self.tool_settings = tool_settings
        self.logger = logger
        self.recorder = recorder

        # Provider instances keyed by provider name
        self._providers: Dict[str, Any] = {}
        # Role -> provider name mapping (overrides default Ollama)
        self._role_provider_map: Dict[str, str] = {}
        # Cache of initialized provider+model pairs
        self._client_cache: Dict[str, Any] = {}

        # Register default Ollama provider
        self._register_default_ollama()

    def _register_default_ollama(self) -> None:
        """Register the default Ollama provider from config."""
        ollama = OllamaProvider(
            base_url=str(self.config.ollama_url),
            model=self.config.default_model,
            timeout=self.config.default_timeout,
            logger=self.logger,
            config=self.tool_settings.model_dump(),
            recorder=self.recorder,
        )
        self._providers["ollama"] = ollama
        self.logger.info("MultiProviderManager: Default Ollama provider registered.")

    def register_provider(self, provider_config: ProviderConfig) -> None:
        """Register a new LLM provider.

        Args:
            provider_config: Configuration for the provider.
        """
        if provider_config.provider_type == "ollama":
            provider = OllamaProvider(
                base_url=provider_config.base_url,
                model=provider_config.models.get("default", self.config.default_model),
                timeout=provider_config.timeout,
                logger=self.logger,
                config=self.tool_settings.model_dump(),
                recorder=self.recorder,
            )
        elif provider_config.provider_type == "openai_compatible":
            provider = OpenAICompatibleProvider(
                base_url=provider_config.base_url,
                api_key=provider_config.api_key,
                model=provider_config.models.get("default", "default"),
                timeout=provider_config.timeout,
                logger=self.logger,
                provider_name=provider_config.name,
            )
        else:
            self.logger.error(f"Unknown provider type: {provider_config.provider_type}")
            return

        self._providers[provider_config.name] = provider

        # Map roles to this provider
        for role, model in provider_config.models.items():
            if role != "default":
                self._role_provider_map[role] = provider_config.name

        self.logger.info(
            f"Provider '{provider_config.name}' ({provider_config.provider_type}) registered "
            f"with {len(provider_config.models)} model mappings."
        )

    def get_client(self, role: str) -> Any:
        """Get an LLM client for a given role.

        Routes to the appropriate provider based on configuration.
        Falls back to default Ollama if no specific provider is mapped.

        Args:
            role: The agent role (e.g., "coder", "senior_reviewer").

        Returns:
            An LLM client (OllamaClient, OllamaProvider, or OpenAICompatibleProvider).
        """
        cache_key = f"{role}"
        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        # Check if this role has a specific provider
        provider_name = self._role_provider_map.get(role)

        if provider_name and provider_name in self._providers:
            provider = self._providers[provider_name]
            # If provider has a specific model for this role, reconfigure
            if isinstance(provider, OpenAICompatibleProvider):
                # OpenAI-compatible providers can have per-role models
                # We need to find the model from the provider config
                provider_config_models = getattr(provider, "_role_models", {})
                model = provider_config_models.get(role, provider.model)
                if model != provider.model:
                    # Create a new provider instance with the role-specific model
                    provider = OpenAICompatibleProvider(
                        base_url=provider.base_url,
                        api_key=provider.api_key,
                        model=model,
                        timeout=provider.timeout,
                        logger=self.logger,
                        provider_name=provider.provider_name,
                    )
            self._client_cache[cache_key] = provider
            return provider

        # Fall back to Ollama with role-based model from config
        model_name = self.config.agent_roles.get(role, self.config.default_model)
        ollama_provider = self._providers.get("ollama")

        if ollama_provider:
            # Get or create an OllamaClient via the Ollama provider pattern
            from backend.utils.core.llm.ollama_client import OllamaClient
            from backend.utils.core.llm.llm_recorder import LLMRecorder

            if model_name not in self._client_cache:
                # Ensure we have a recorder
                if self.recorder is None:
                    self.recorder = LLMRecorder(self.logger)

                client = OllamaClient(
                    url=str(self.config.ollama_url),
                    model=model_name,
                    timeout=self.config.default_timeout,
                    logger=self.logger,
                    config=self.tool_settings.model_dump(),
                    llm_recorder=self.recorder,
                )
                self._client_cache[model_name] = client
            self._client_cache[cache_key] = self._client_cache[model_name]
            return self._client_cache[cache_key]

        raise ProviderConnectionError("ollama", "No Ollama provider available")

    def get_embedding_client(self) -> Any:
        """Get a client for embedding generation."""
        if not self.config.embedding:
            raise ValueError("No embedding model configured.")
        return self.get_client("embedding")

    def get_all_clients(self) -> Dict[str, Any]:
        """Get all initialized clients."""
        return dict(self._client_cache)

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """List all registered providers with their capabilities."""
        result = []
        for name, provider in self._providers.items():
            result.append(
                {
                    "name": name,
                    "type": getattr(provider, "PROVIDER_TYPE", "unknown"),
                    "supports_tools": provider.supports_tools(),
                    "supports_vision": provider.supports_vision(),
                }
            )
        return result
