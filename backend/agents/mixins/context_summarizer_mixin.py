from abc import ABC
import json
from typing import Dict, List

from backend.utils.core.llm.prompt_loader import PromptLoader


class ContextSummarizerMixin(ABC):
    """
    Mixin for managing context window and automatic summarization.
    """

    async def _manage_context_window(self, messages: List[Dict]) -> List[Dict]:
        """
        Manages the context window by summarizing older messages if the LAST
        Ollama request indicated we are near the capacity.
        """
        # Get the real token count from the last Ollama response
        current_tokens = getattr(self.token_tracker, "last_prompt_tokens", 0)

        # Standard configuration
        max_tokens = 16000
        summarize_threshold = 0.85

        if hasattr(self, "tool_settings_config"):
            max_tokens = getattr(self.tool_settings_config, "max_context_tokens", 16000)
            summarize_threshold = getattr(self.tool_settings_config, "summarize_threshold_ratio", 0.85)

        # If the last response was already too big, summarize now before the next one
        if current_tokens < max_tokens * summarize_threshold:
            return messages  # No summarization needed yet

        self.logger.warning(f"⚠️ Context window capacity reached ({current_tokens}/{max_tokens} tokens). Summarizing...")

        await self.event_publisher.publish(
            "context_management",
            {"status": "summarizing", "tokens_before": current_tokens},
        )

        summarizer_client = self.llm_manager.get_client("writer")
        if not summarizer_client:
            self.logger.error("Summarization LLM client not available.")
            return messages[-5:]  # Aggressive fallback: just keep last 5 messages

        # F24: Aggressive split: Keep only the System Prompt and the last 3 messages.
        # Summarize everything in between.
        system_prompt = messages[0] if messages and messages[0]["role"] == "system" else None

        if system_prompt:
            messages_to_summarize = messages[1:-3]
            remaining_messages = messages[-3:]
        else:
            messages_to_summarize = messages[:-3]
            remaining_messages = messages[-3:]

        if not messages_to_summarize:
            # If we only have a few messages but they are huge, just keep the last 2
            return ([system_prompt] if system_prompt else []) + messages[-2:]

        try:
            loader = PromptLoader()
            prompts = await loader.load_prompt("core/services.yaml")

            system = prompts.get("context_summarization", {}).get("system", "")
            user_template = prompts.get("context_summarization", {}).get("user", "")
            user = user_template.format(history=json.dumps(messages_to_summarize))

            summary_response, _ = await summarizer_client.achat(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], tools=[]
            )
            summary_content = summary_response["message"]["content"]

            summarized_messages = []
            if system_prompt:
                summarized_messages.append(system_prompt)

            summarized_messages.append(
                {
                    "role": "system",
                    "content": f"Summary of previous progress: {summary_content}",
                }
            )
            summarized_messages.extend(remaining_messages)

            self.logger.info(f"Context compressed: {current_tokens} tokens have been summarized.")
            return summarized_messages

        except Exception as e:
            self.logger.error(f"Error during context summarization: {e}. Returning original messages.")
            await self.event_publisher.publish("context_management", {"status": "error", "error_message": str(e)})
            return messages
