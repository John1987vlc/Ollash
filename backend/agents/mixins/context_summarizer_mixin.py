from abc import ABC
from typing import Dict, List
import tiktoken # For token counting (example)



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
        try:
            # Attempt to use tiktoken if available and configured
            encoding_name = self.config.get("token_encoding_name", "cl100k_base")
            encoding = tiktoken.get_encoding(encoding_name)
            return len(encoding.encode(text))
        except Exception:
            # Fallback to a simpler, less accurate method if tiktoken fails or isn't used
            self.logger.warning("tiktoken not available or configured. Falling back to word count heuristic for tokens.")
            return len(text.split()) // 2 # Roughly 2 chars per token

    async def _manage_context_window(self, messages: List[Dict]) -> List[Dict]:
        """
        Manages the context window by summarizing older messages if token capacity
        exceeds a configured threshold.
        """
        max_tokens = self.config.get("max_context_tokens", 8000)
        summarize_threshold = self.config.get("summarize_threshold_ratio", 0.7)

        current_tokens = self._count_tokens(str(messages)) # Crude token count for all messages

        if current_tokens < max_tokens * summarize_threshold:
            return messages # No summarization needed yet

        self.logger.info(f"Context window approaching limit ({current_tokens}/{max_tokens} tokens). Initiating summarization.")
        self.event_publisher.publish("context_management", {"status": "summarizing", "tokens_before": current_tokens})

        summarizer_client = self.llm_manager.get_client("writer") # Use writer or generalist model for summarization
        if not summarizer_client:
            self.logger.error("Summarization LLM client not available. Cannot summarize context.")
            return messages # Cannot summarize, return original messages

        summarized_messages = []
        # A simple summarization strategy: summarize oldest messages until below threshold
        # More advanced strategies would use a 'cascade summarizer' or similar.

        # Find a good point to split messages for summarization.
        # This example is basic; a real one would be more sophisticated.
        num_messages_to_summarize = len(messages) // 2 # Summarize half of the messages

        messages_to_summarize = messages[:num_messages_to_summarize]
        remaining_messages = messages[num_messages_to_summarize:]

        summary_prompt = [
            {"role": "system", "content": "You are a helpful assistant that summarizes conversation history concisely."},
            {"role": "user", "content": f"""Please summarize the following conversation history:

{str(messages_to_summarize)}"""}
        ]

        try:
            summary_response, _ = await summarizer_client.achat(summary_prompt, tools=[])
            summary_content = summary_response["message"]["content"]

            summarized_messages.append({"role": "system", "content": f"Summarized conversation history: {summary_content}"})
            summarized_messages.extend(remaining_messages)

            tokens_after = self._count_tokens(str(summarized_messages))
            self.logger.info(f"Context summarized. Tokens after: {tokens_after}/{max_tokens}.")
            self.event_publisher.publish("context_management", {"status": "summarized", "tokens_after": tokens_after})
            return summarized_messages

        except Exception as e:
            self.logger.error(f"Error during context summarization: {e}. Returning original messages.")
            self.event_publisher.publish("context_management", {"status": "error", "error_message": str(e)})
            return messages
