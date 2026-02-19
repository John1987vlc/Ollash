from abc import ABC
from typing import Any, Optional


class IntentRoutingMixin(ABC):
    """
    Mixin for handling intent classification and routing requests to appropriate
    LLM models based on the classified intent.
    Assumes the inheriting class provides:
    - self.logger (AgentLogger)
    - self.config (Dict)
    - self.llm_manager (IModelProvider)
    """

    async def _classify_intent(self, prompt: str) -> str:
        """
        Classifies the user's intent based on the prompt to route to the most
        suitable LLM model or tool chain.
        """
        # This is a placeholder for actual intent classification logic.
        # In a real scenario, this would involve an LLM call specifically
        # tasked with classifying intent, or a rule-based system.

        # For demonstration, we'll use a very simple heuristic or default.
        # The actual implementation might use the 'orchestration' model or 'generalist'
        # model provided by the llm_manager to classify intent.

        # Example: Using an orchestration model for intent classification
        orchestration_client = self.llm_manager.get_client("orchestration")
        if orchestration_client:
            try:
                # This would be a detailed prompt to the orchestration model
                # asking it to classify the intent (e.g., code generation, network task, etc.)
                # and return a specific keyword.
                messages = [
                    {
                        "role": "system",
                        "content": "You are an intent classifier. Given a user prompt, classify its primary intent as one of: 'code', 'network', 'system', 'cybersecurity', 'planning', 'general', 'prototyping', 'testing', 'reviewing', 'analysing', 'writing'.",
                    },
                    {
                        "role": "user",
                        "content": f"""User prompt: {prompt}

Classify the intent:""",
                    },
                ]

                response, _ = await orchestration_client.achat(messages, tools=[])

                # Extract intent from the response. The LLM is instructed to return only the intent string.
                # Use .strip() to remove leading/trailing whitespace, and .lower() for case-insensitivity.
                if response and response.get("message") and response["message"].get("content"):
                    classified_intent = response["message"]["content"].strip().lower()

                    # Validate if the classified intent is one of the expected intents
                    valid_intents = [
                        "code",
                        "network",
                        "system",
                        "cybersecurity",
                        "planning",
                        "general",
                        "prototyping",
                        "testing",
                        "reviewing",
                        "analysing",
                        "writing",
                    ]
                    if classified_intent in valid_intents:
                        # F25: If it's prototyping or code, ensure we use the coder role
                        if classified_intent == "prototyping":
                            classified_intent = "code"
                        
                        self.logger.debug(f"Intent classified: {classified_intent} for prompt: {prompt[:50]}...")
                        return classified_intent
                    else:
                        self.logger.warning(
                            f"LLM classified intent '{classified_intent}' is not a valid intent. Falling back to 'default'."
                        )
                        return "default"
                else:
                    self.logger.warning(
                        "Orchestration model response for intent classification was empty or malformed. Falling back to 'default'."
                    )
                    return "default"
            except Exception as e:
                self.logger.warning(
                    f"Failed to classify intent using orchestration model: {e}. Falling back to default."
                )
                return "default"
        else:
            self.logger.warning(
                "Orchestration LLM client not available for intent classification. Falling back to default."
            )
            return "default"

    def _select_model_for_intent(self, intent: str) -> Optional[Any]:
        """
        Selects an LLM client based on the classified intent.
        """
        # Map intents to model roles defined in LLMClientManager.LLM_ROLES
        # This mapping should ideally come from configuration.
        model_role_map = self.config.get(
            "intent_to_model_role_map",
            {
                "code": "coder",
                "network": "generalist",  # No specific network model in LLM_ROLES, fallback to generalist
                "system": "generalist",  # No specific system model in LLM_ROLES, fallback to generalist
                "cybersecurity": "generalist",  # No specific cybersecurity model in LLM_ROLES, fallback to generalist
                "planning": "planner",
                "general": "generalist",
                "prototyping": "prototyper",
                "testing": "test_generator",
                "reviewing": "senior_reviewer",
                "analysing": "analyst",
                "writing": "writer",
                "default": "default",
            },
        )

        model_role = model_role_map.get(intent, "default")
        client = self.llm_manager.get_client(model_role)

        if not client:
            self.logger.warning(
                f"LLM client for role '{model_role}' (intent: '{intent}') not found. Falling back to 'default'."
            )
            client = self.llm_manager.get_client("default")

        if not client:
            self.logger.error("Default LLM client also not available. Agent cannot function without an LLM.")
            raise RuntimeError("No LLM client available for processing request.")

        return client
