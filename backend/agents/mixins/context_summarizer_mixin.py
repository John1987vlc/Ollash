from abc import ABC
import json
from typing import Dict, List

import tiktoken  # For token counting (example)


class ContextSummarizerMixin(ABC):
    """
    Mixin for managing context window and automatic summarization.
    Assumes the inheriting class provides:
    - self.logger (AgentLogger)
    - self.get_config_value (method from AgentKernel/ConfigLoader)
    - self.llm_manager (IModelProvider)
    - self.token_tracker (TokenTracker)
    - self.event_publisher (EventPublisher)
    """

    # Placeholder for a simple token counter. In a real system, this would be more robust.
    def _count_tokens(self, text: str) -> int:
        """Counts tokens in a given text using a basic heuristic or a proper tokenizer."""
        if not text:
            return 0
        try:
            # Attempt to use tiktoken if available and configured
            encoding_name = self.config.get("token_encoding_name", "cl100k_base")
            encoding = tiktoken.get_encoding(encoding_name)
            return len(encoding.encode(text))
        except Exception:
            # F24: Better heuristic: 1 token approx 3.5 chars for code/technical text
            return len(text) // 3

    async def _manage_context_window(self, messages: List[Dict]) -> List[Dict]:
        """
        Manages the context window by summarizing older messages if token capacity
        exceeds a configured threshold.
        """
        max_tokens = self.config.get("max_context_tokens", 2048)
        summarize_threshold = self.config.get("summarize_threshold_ratio", 0.7)

        # F24: More accurate message string representation for counting
        full_conversation_text = json.dumps(messages)
        current_tokens = self._count_tokens(full_conversation_text)

        if current_tokens < max_tokens * summarize_threshold:
            return messages  # No summarization needed yet

        self.logger.warning(f"⚠️ Context window capacity reached ({current_tokens}/{max_tokens} tokens). Summarizing...")

        self.event_publisher.publish(
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

        summary_prompt = [
            {
                "role": "system",
                "content": "You are an expert technical summarizer. Condense the conversation history into a single paragraph focusing only on decisions made and project progress. DO NOT include code blocks.",
            },
            {
                "role": "user",
                "content": f"Summarize this conversation context:\n{json.dumps(messages_to_summarize)}",
            },
        ]

        try:
            summary_response, _ = await summarizer_client.achat(summary_prompt, tools=[])
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

            tokens_after = self._count_tokens(json.dumps(summarized_messages))
            self.logger.info(f"Context compressed: {current_tokens} -> {tokens_after} tokens.")
            return summarized_messages

        except Exception as e:
            self.logger.error(f"Error during context summarization: {e}. Returning original messages.")
            self.event_publisher.publish("context_management", {"status": "error", "error_message": str(e)})
            return messages
