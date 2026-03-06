"""
Manages the lifecycle of OllamaClient instances based on configured agent roles.
"""

from typing import Dict, Optional, List, Any

from backend.core.config_schemas import LLMModelsConfig, ToolSettingsConfig
from backend.interfaces.imodel_provider import IModelProvider
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.llm_recorder import LLMRecorder
from backend.utils.core.llm.ollama_client import OllamaClient
from backend.utils.core.llm.token_tracker import TokenTracker
from backend.utils.core.system.execution_bridge import bridge


class LLMClientManager(IModelProvider):
    """
    Manages the provisioning and lifecycle of OllamaClient instances.
    It maps abstract "agent roles" to specific, configured LLM models.
    """

    def __init__(
        self,
        config: LLMModelsConfig,
        tool_settings: ToolSettingsConfig,
        logger: AgentLogger,
        recorder: Optional[LLMRecorder] = None,
        token_tracker: Optional[TokenTracker] = None,
    ):
        self.config = config
        self.tool_settings = tool_settings
        self.logger = logger
        self.recorder = recorder
        self.token_tracker = token_tracker
        self.clients_by_model: Dict[str, OllamaClient] = {}
        # Use sync info to avoid async publish in constructor
        self.logger.info_sync("LLMClientManager initialized.")

    def _log_role_assignments(self):
        self.logger.info_sync("Agent Role to Model Assignments:")
        if not self.config.agent_roles:
            self.logger.warning_sync("No agent roles are defined in the configuration.")
            return
        for role, model in self.config.agent_roles.items():
            self.logger.info_sync(f"  - Role: '{role}' -> Model: '{model}'")

    def get_client(self, role: str) -> OllamaClient:
        """
        Retrieves an OllamaClient for a given agent role.
        Resolved to a model name using the configuration.
        Cached client instances, one per model.
        """
        model_name = self.config.agent_roles.get(role)

        if not model_name:
            if role != "default":
                self.logger.warning_sync(
                    f"Role '{role}' not found in agent_roles config. "
                    f"Falling back to default model '{self.config.default_model}'."
                )
            model_name = self.config.default_model

        return self.get_client_by_model(model_name, role)

    def get_client_by_model(self, model_name: str, role: str = "custom") -> OllamaClient:
        """Retrieves or creates an OllamaClient for a specific model name."""
        # If a client for this *model* already exists, return it.
        if model_name in self.clients_by_model:
            return self.clients_by_model[model_name]

        # Otherwise, create a new client for this model and cache it.
        self.logger.info_sync(f"Creating new OllamaClient for model '{model_name}' (for role '{role}').")

        new_client = OllamaClient(
            url=str(self.config.ollama_url),
            model=model_name,
            timeout=self.config.default_timeout,
            logger=self.logger,
            config=self.tool_settings.model_dump(),  # Pass tool settings
            llm_recorder=self.recorder,
            token_tracker=self.token_tracker,
        )

        self.clients_by_model[model_name] = new_client
        return new_client

    def get_tiered_client(self, tier: str) -> Optional[OllamaClient]:
        """Retrieves a client based on the tier name (nano, medium, large, extra_large)."""
        model_name = getattr(self.config, tier, None)
        if not model_name:
            self.logger.warning_sync(f"Tier '{tier}' not configured. Falling back to default.")
            return self.get_client("default")
        return self.get_client_by_model(model_name, role=f"tier_{tier}")

    def get_escalated_client(self, current_model_name: str) -> OllamaClient:
        """Finds the next more powerful model tier relative to the current model."""
        tiers = ["nano", "medium", "large", "extra_large"]
        current_tier_idx = -1
        
        # Identify current tier
        for i, tier in enumerate(tiers):
            if getattr(self.config, tier) == current_model_name:
                current_tier_idx = i
                break
        
        # If not found or already at max, return extra_large if available, or default
        if current_tier_idx == -1 or current_tier_idx == len(tiers) - 1:
            xl = getattr(self.config, "extra_large")
            if xl: return self.get_client_by_model(xl, "escalation")
            return self.get_client("default")
            
        # Get next tier
        next_tier = tiers[current_tier_idx + 1]
        next_model = getattr(self.config, next_tier)
        
        if not next_model:
            # Skip empty tiers
            return self.get_escalated_client(getattr(self.config, tiers[current_tier_idx])) # recursive but safe
            
        self.logger.info_sync(f"Escalating from {current_model_name} to {next_model} ({next_tier})")
        return self.get_client_by_model(next_model, "escalation")

    def get_embedding_client(self) -> "OllamaClient":
        """
        Retrieves a dedicated client for embedding tasks.
        """
        embedding_model = self.config.embedding
        if not embedding_model:
            raise ValueError("No embedding model is configured in 'LLMModelsConfig'.")

        return self.get_client("embedding")

    def get_vision_client(self) -> "OllamaClient":
        """
        Retrieves a dedicated client for vision/multimodal tasks.
        Uses the configured vision_model or falls back to 'llava'.
        """
        vision_model = getattr(self.config, "vision_model", None) or "llava"

        if vision_model in self.clients_by_model:
            return self.clients_by_model[vision_model]

        self.logger.info_sync(f"Creating vision client for model '{vision_model}'.")
        new_client = OllamaClient(
            url=str(self.config.ollama_url),
            model=vision_model,
            timeout=self.config.default_timeout,
            logger=self.logger,
            config=self.tool_settings.model_dump(),
            llm_recorder=self.recorder,
            token_tracker=self.token_tracker,
        )
        self.clients_by_model[vision_model] = new_client
        return new_client

    def get_all_clients(self) -> Dict[str, "OllamaClient"]:
        """
        Returns a dictionary of all initialized OllamaClient instances, keyed by model name.
        """
        return self.clients_by_model

    # F40: Global context and VRAM management
    def set_global_context(self, context: List[int]):
        for client in self.clients_by_model.values():
            client.set_session_context(context)

    def set_global_keep_alive(self, keep_alive: str):
        for client in self.clients_by_model.values():
            client.set_keep_alive(keep_alive)

    def release_all_vram(self):
        for client in self.clients_by_model.values():
            client.unload_model()

    async def close_all_sessions_async(self):
        """Asynchronously closes all active HTTP sessions for all clients."""
        for model, client in list(self.clients_by_model.items()):
            await client.close()
        self.clients_by_model.clear()

    def close_all_sessions(self):
        """Closes all active HTTP sessions for all clients."""
        for model, client in list(self.clients_by_model.items()):
            # Use bridge to run the async close in sync context
            bridge.run(client.close())
        self.clients_by_model.clear()
