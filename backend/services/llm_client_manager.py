"""
Manages the lifecycle of OllamaClient instances based on configured agent roles.
"""

from typing import Dict, Optional

from backend.core.config_schemas import LLMModelsConfig, ToolSettingsConfig
from backend.interfaces.imodel_provider import IModelProvider
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.llm_recorder import LLMRecorder
from backend.utils.core.ollama_client import OllamaClient


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
    ):
        self.config = config
        self.tool_settings = tool_settings
        self.logger = logger
        self.recorder = recorder
        self.clients_by_model: Dict[str, OllamaClient] = {}
        self.logger.info("LLMClientManager initialized.")
        self._log_role_assignments()

    def _log_role_assignments(self):
        self.logger.info("Agent Role to Model Assignments:")
        if not self.config.agent_roles:
            self.logger.warning("No agent roles are defined in the configuration.")
            return
        for role, model in self.config.agent_roles.items():
            self.logger.info(f"  - Role: '{role}' -> Model: '{model}'")

    def get_client(self, role: str) -> OllamaClient:
        """
        Retrieves an OllamaClient for a given agent role.
        It resolves the role to a model name using the configuration and
        manages a cache of client instances, one per model.
        """
        model_name = self.config.agent_roles.get(role)

        if not model_name:
            self.logger.warning(
                f"Role '{role}' not found in agent_roles config. "
                f"Falling back to default model '{self.config.default_model}'."
            )
            model_name = self.config.default_model

        # If a client for this *model* already exists, return it.
        if model_name in self.clients_by_model:
            return self.clients_by_model[model_name]

        # Otherwise, create a new client for this model and cache it.
        self.logger.info(f"Creating new OllamaClient for model '{model_name}' (for role '{role}').")

        new_client = OllamaClient(
            url=str(self.config.ollama_url),
            model=model_name,
            timeout=self.config.default_timeout,
            logger=self.logger,
            config=self.tool_settings.model_dump(),  # Pass tool settings
            llm_recorder=self.recorder,
        )

        self.clients_by_model[model_name] = new_client
        return new_client

    def get_embedding_client(self) -> "OllamaClient":
        """
        Retrieves a dedicated client for embedding tasks.
        """
        embedding_model = self.config.embedding
        if not embedding_model:
            raise ValueError("No embedding model is configured in 'LLMModelsConfig'.")

        # Use "embedding" as a special role to get a dedicated client
        return self.get_client("embedding")

    def get_all_clients(self) -> Dict[str, "OllamaClient"]:
        """
        Returns a dictionary of all initialized OllamaClient instances, keyed by model name.
        """
        return self.clients_by_model
