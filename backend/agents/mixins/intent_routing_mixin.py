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
        clean_input = prompt.strip().lower()

        # F33: Hardcoded Keyword Fallback (Prioritize precision for known IT tasks)
        system_priority = ["ram", "cpu", "disk", "process", "os", "operating system", "sistema operativo", "hardware", "memoria", "disco"]
        network_priority = ["ip address", "ping", "port", "dns", "mac address", "conexion", "network", "red", "ip pública"]
        code_priority = ["python", "javascript", "code", "script", "refactor", "bug", "fix", "program", "function", "clase"]
        git_priority = ["git", "commit", "push", "pull", "branch", "repo", "repository"]

        if any(kw in clean_input for kw in system_priority):
            self.logger.info("🎯 Intent auto-classified (Keyword): 'system'")
            return "system"
        if any(kw in clean_input for kw in network_priority):
            self.logger.info("🎯 Intent auto-classified (Keyword): 'network'")
            return "network"
        if any(kw in clean_input for kw in git_priority):
            self.logger.info("🎯 Intent auto-classified (Keyword): 'git'")
            return "system" # Git is handled by system/orchestrator
        if any(kw in clean_input for kw in code_priority):
            self.logger.info("🎯 Intent auto-classified (Keyword): 'code'")
            return "code"

        # Example: Using an orchestration model for intent classification
        orchestration_client = self.llm_manager.get_client("orchestration")
        if orchestration_client:
            try:
                from backend.utils.core.llm.prompt_loader import PromptLoader

                loader = PromptLoader()
                prompts = loader.load_prompt("core/services.yaml")

                system = prompts.get("intent_classification", {}).get("system", "")
                user_template = prompts.get("intent_classification", {}).get("user", "")
                user = user_template.format(text=prompt)

                response, _ = await orchestration_client.achat(
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], tools=[]
                )

                # Extract intent from the response. The LLM is instructed to return only the intent string.
                # Use .strip() to remove leading/trailing whitespace, and .lower() for case-insensitivity.
                if response and response.get("message") and response["message"].get("content"):
                    raw_content = response["message"]["content"].strip().lower()

                    # F33: Radical filtering of translation noise
                    clean_content = raw_content
                    if "**input language:**" in clean_content:
                        # Try to extract content after the noise
                        if "output:**" in clean_content:
                            clean_content = clean_content.split("output:**", 1)[1].strip()
                        else:
                            clean_content = clean_content.split("**input language:**", 1)[1].strip()

                    # Clean Markdown and quotes
                    clean_content = clean_content.replace("*", "").replace("_", "").replace("'", "").replace("\"", "")

                    self.logger.debug(f"🔍 Intent Router sanitized string: '{clean_content}'")

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

                    # F27: Search for the keyword within the string to handle extra conversational text
                    classified_intent = "default"

                    # SYSTEM PRIORITY (Highest)
                    system_keywords = ["ram", "cpu", "disk", "process", "os", "sistema operativo", "operating system", "memoria", "hardware", "disco", "driver", "controlador"]
                    # NETWORK PRIORITY
                    network_keywords = ["ip", "ping", "port", "dns", "mac address", "conexion", "network", "red"]

                    if any(kw in clean_content for kw in system_keywords):
                        classified_intent = "system"
                    elif any(kw in clean_content for kw in network_keywords):
                        classified_intent = "network"
                    else:
                        for intent in valid_intents:
                            if intent in clean_content:
                                classified_intent = intent
                                break

                    if classified_intent != "default":
                        # F25: If it's prototyping or code, ensure we use the coder role
                        if classified_intent == "prototyping":
                            classified_intent = "code"

                        self.logger.info(f"🎯 Intent classified: '{classified_intent}' for prompt: '{prompt[:50]}...'")
                        return classified_intent
                    else:
                        self.logger.warning(
                            f"LLM failed to provide a clear intent in: '{clean_content}'. Falling back to 'default'."
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
                "network": "network",
                "system": "system",
                "cybersecurity": "generalist",
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
