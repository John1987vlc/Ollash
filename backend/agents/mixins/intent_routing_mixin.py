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
            logger.info(f"Classifying intent for instruction: '{instruction[:50]}...'")
            loader = PromptLoader()
            # loader.load_prompt is async
            prompts = await loader.load_prompt("core/services.yaml")

            if not prompts:
                logger.warning("Could not load core/services.yaml prompts for intent classification.")
                return "orchestrator"

            intent_def = prompts.get("intent_classification", {})
            system = intent_def.get("system", "")
            user_template = intent_def.get("user", "")
            user = user_template.format(text=instruction)

            # Use orchestration client for classification
            client = self.llm_manager.get_client("orchestration")

            logger.info(f"Calling LLM ({client.model}) for intent classification...")
            # client.achat is async
            response, _ = await client.achat(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                tools=[],
                options_override={"temperature": 0.0},
            )

            if not response or "message" not in response:
                logger.warning(f"Empty response from LLM during intent classification. Response: {response}")
                return "orchestrator"

            content = response.get("message", {}).get("content", "").lower()
            logger.debug(f"Raw intent classification response: {content}")

            # F33: Use parser to clean thinking blocks
            content, _ = LLMResponseParser.remove_think_blocks(content)

            # Basic keyword matching fallback if LLM is verbose
            valid_intents = ["orchestrator", "code", "network", "system", "cybersecurity"]
            final_intent = "orchestrator"
            for intent in valid_intents:
                if intent in content:
                    logger.info(f"Classified intent: '{intent}'")
                    final_intent = intent
                    break

            if final_intent == "orchestrator":
                logger.info("Could not determine specific intent from LLM output, defaulting to 'orchestrator'.")

            # F30: Publish routing event for real-time UI feedback
            if hasattr(self, "event_publisher") and self.event_publisher:
                await self.event_publisher.publish(
                    "routing", {"intent": final_intent, "message": f"Routing request to {final_intent} specialist..."}
                )

            return final_intent
        except Exception as e:
            logger.error(f"Intent classification failed with error: {e}", exc_info=True)
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
