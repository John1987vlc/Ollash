import logging
from typing import Any

from backend.utils.core.llm.prompt_loader import PromptLoader
from backend.utils.core.llm.llm_response_parser import LLMResponseParser

logger = logging.getLogger(__name__)


class IntentRoutingMixin:
    """
    Mixin that provides intent classification and model routing logic.
    """

    async def _classify_intent(self, instruction: str) -> str:
        """
        Classifies the user's intent to route to the appropriate specialist or model.
        """
        try:
            loader = PromptLoader()
            prompts = await loader.load_prompt("core/services.yaml")

            intent_def = prompts.get("intent_classification", {})
            system = intent_def.get("system", "")
            user_template = intent_def.get("user", "")
            user = user_template.format(text=instruction)

            # Use orchestration client for classification
            client = self.llm_manager.get_client("orchestration")
            response, _ = await client.achat(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                tools=[],
                options_override={"temperature": 0.0},
            )

            content = response.get("message", {}).get("content", "").lower()
            # F33: Use parser to clean thinking blocks
            content, _ = LLMResponseParser.remove_think_blocks(content)

            # Basic keyword matching fallback if LLM is verbose
            valid_intents = ["orchestrator", "code", "network", "system", "cybersecurity"]
            for intent in valid_intents:
                if intent in content:
                    return intent

            return "orchestrator"
        except Exception as e:
            logger.warning(f"Intent classification failed: {e}. Defaulting to orchestrator.")
            return "orchestrator"

    def _select_model_for_intent(self, intent: str) -> Any:
        """
        Returns the appropriate LLM client based on the classified intent.
        """
        role_map = {
            "code": "coder",
            "network": "network",
            "system": "system",
            "cybersecurity": "cybersecurity",
            "orchestrator": "orchestration",
        }

        role = role_map.get(intent, "orchestration")
        return self.llm_manager.get_client(role)
