import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb

from backend.utils.core.ollama_client import OllamaClient
from backend.utils.core.preference_manager import PreferenceManager


class MemoryManager:
    def __init__(
        self,
        project_root: Path,
        logger: Any,
        config: Optional[Dict] = None,
        embedding_client: Optional[Any] = None,
        summarization_client: Optional[Any] = None,
        llm_recorder: Any = None,
    ):
        self.project_root = project_root
        self.memory_file = self.project_root / ".agent_memory.json"
        self.logger = logger
        self.config = config or {}
        self.llm_recorder = llm_recorder  # Store llm_recorder
        self.memory: Dict[str, Any] = {}
        self._load_memory()

        # --> NEW: Initialize PreferenceManager
        self.preference_manager = PreferenceManager(project_root, logger)

        # Context management parameters
        self.max_context_tokens = self.config.get("max_context_tokens", 4000)
        self.summarization_threshold_ratio = self.config.get("summarization_threshold_ratio", 0.7)
        self.keep_last_n_messages = self.config.get("keep_last_n_messages", 3)

        # LRU cache settings
        self._reasoning_cache_max_size: int = self.config.get("reasoning_cache_max_size", 500)

        # Cumulative summary: persisted across summarization rounds
        self._cumulative_summary: str = self.get("cumulative_summary", "")

        # Reasoning Cache (ChromaDB)
        self.chroma_client = chromadb.Client()
        self.reasoning_cache_collection = self.chroma_client.get_or_create_collection(name="reasoning_cache")

        # Accept injected clients or create fallback instances
        models_config = self.config.get("models", {})
        ollama_url = os.environ.get(
            "OLLASH_OLLAMA_URL",
            self.config.get("ollama_url", "http://localhost:11434"),
        )
        self.summarization_model = models_config.get(
            "summarization",
            self.config.get(
                "summarization_model",
                self.config.get("summary_model", "ministral-3:8b"),
            ),
        )

        if embedding_client is not None:
            self.embedding_client = embedding_client
        else:
            # Create a consolidated config dictionary for OllamaClient
            ollama_client_config_dict = {
                "ollama_max_retries": self.config.get("ollama_max_retries", 5),
                "ollama_backoff_factor": self.config.get("ollama_backoff_factor", 1.0),
                "ollama_retry_status_forcelist": self.config.get(
                    "ollama_retry_status_forcelist", [429, 500, 502, 503, 504]
                ),
                "embedding_cache": self.config.get("embedding_cache", {}),
                "project_root": str(self.project_root),  # Pass project_root as string
                "ollama_embedding_model": self.config.get("ollama_embedding_model", "all-minilm"),
            }
            ollama_timeout = self.config.get("timeout", 300)  # Extract timeout here
            self.embedding_client = OllamaClient(
                url=ollama_url,
                model=self.config.get("embedding", "all-minilm"),  # Use specific model or default
                timeout=ollama_timeout,  # Pass as positional argument
                logger=self.logger,
                config=ollama_client_config_dict,
                llm_recorder=self.llm_recorder,
            )

        if summarization_client is not None:
            self._summarization_client = summarization_client
        else:
            ollama_timeout = self.config.get("timeout", 300)  # Extract timeout here
            self._summarization_client = OllamaClient(
                url=ollama_url,
                model=self.summarization_model,
                timeout=ollama_timeout,  # Pass as positional argument
                logger=self.logger,
                config=ollama_client_config_dict,  # Use the consolidated config dict
                llm_recorder=self.llm_recorder,
            )

    # ----------------------------------------------------------------
    # Persistence
    # ----------------------------------------------------------------

    def _load_memory(self):
        """Loads memory from the .agent_memory.json file."""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.memory = json.load(f)
                self.logger.info(f"Memory loaded from {self.memory_file}")
            except json.JSONDecodeError as e:
                self.logger.error(f"Error decoding memory file {self.memory_file}: {e}")
                self.memory = {}
            except Exception as e:
                self.logger.error(f"Unexpected error loading memory from {self.memory_file}: {e}")
                self.memory = {}
        else:
            self.logger.info("No existing memory file found, starting with empty memory.")

    def _save_memory(self):
        """Saves current memory to the .agent_memory.json file."""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=2)
            self.logger.info(f"Memory saved to {self.memory_file}")
        except Exception as e:
            self.logger.error(f"Error saving memory to {self.memory_file}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a value from memory."""
        return self.memory.get(key, default)

    def set(self, key: str, value: Any):
        """Sets a value in memory and saves immediately."""
        self.memory[key] = value
        self._save_memory()

    # ----------------------------------------------------------------
    # Preference Management
    # ----------------------------------------------------------------

    def get_preference_manager(self) -> PreferenceManager:
        """Returns the PreferenceManager instance."""
        return self.preference_manager

    # ----------------------------------------------------------------
    # Conversation history
    # ----------------------------------------------------------------

    def update_conversation_history(self, history: List[Dict]):
        """Updates and saves the conversation history."""
        self.set("conversation_history", history)

    def get_conversation_history(self) -> List[Dict]:
        """Retrieves the conversation history."""
        return self.get("conversation_history", [])

    # ----------------------------------------------------------------
    # Domain context
    # ----------------------------------------------------------------

    def update_domain_context_memory(self, domain_context: Dict[str, str]):
        """Updates and saves the domain context memory."""
        self.set("domain_context_memory", domain_context)

    def get_domain_context_memory(self) -> Dict[str, str]:
        """Retrieves the domain context memory."""
        return self.get("domain_context_memory", {})

    # ----------------------------------------------------------------
    # Token estimation
    # ----------------------------------------------------------------

    @staticmethod
    def estimate_tokens(messages: List[Dict]) -> int:
        """Estimates the total number of tokens in a list of messages (~1 token per 4 chars)."""
        total_chars = 0
        for message in messages:
            if message.get("content"):
                total_chars += len(message["content"])
            if message.get("tool_calls"):
                total_chars += len(json.dumps(message["tool_calls"]))
        return total_chars // 4

    # ----------------------------------------------------------------
    # Intelligent context management
    # ----------------------------------------------------------------

    def needs_summarization(self, conversation: List[Dict], system_prompt: str = "") -> bool:
        """Returns True when the conversation + system prompt approaches MAX_CONTEXT_TOKENS."""
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(conversation)
        current_tokens = self.estimate_tokens(all_messages)
        threshold = int(self.max_context_tokens * self.summarization_threshold_ratio)
        return current_tokens >= threshold

    def summarize_and_clean(self, conversation: List[Dict]) -> List[Dict]:
        """
        Cumulative context summarization.

        1. Splits conversation into old messages and recent messages (kept intact).
        2. Summarizes old messages via the summarization model, incorporating any
           previous cumulative summary so context is never lost.
        3. Replaces old messages with a single summary system message.
        4. Returns the cleaned conversation list.
        """
        if len(conversation) <= self.keep_last_n_messages:
            self.logger.info("Not enough conversation history to summarize.")
            return conversation

        messages_to_summarize = conversation[: -self.keep_last_n_messages]
        remaining_messages = conversation[-self.keep_last_n_messages :]

        if not messages_to_summarize:
            return conversation

        self.logger.info(
            f"Summarizing {len(messages_to_summarize)} old messages (keeping last {len(remaining_messages)})."
        )

        # Build the summarization prompt, including the previous cumulative summary
        context_preamble = ""
        if self._cumulative_summary:
            context_preamble = (
                f"Previous cumulative summary of earlier conversation:\n"
                f"{self._cumulative_summary}\n\n"
                f"Now summarize the following additional conversation, incorporating the above context:\n"
            )

        summarization_prompt = [
            {
                "role": "system",
                "content": (
                    "You are an expert summarizer. Condense the following conversation history "
                    "into a concise summary (2-4 sentences) that captures the main points, "
                    "decisions made, tools used, results obtained, and current state of the task. "
                    "This summary will be used as context for future interactions. "
                    "Focus on key information that the agent needs to continue effectively."
                ),
            },
            {
                "role": "user",
                "content": (
                    context_preamble
                    + "\n".join(f"[{m.get('role', '?')}]: {m.get('content', '')[:500]}" for m in messages_to_summarize)
                ),
            },
        ]

        try:
            response_data, _ = self._summarization_client.chat(summarization_prompt, tools=[])
            new_summary = response_data.get("message", {}).get("content", "")

            if not new_summary:
                self.logger.warning("Summarization returned empty. Keeping conversation as-is.")
                return conversation

            # Update cumulative summary
            self._cumulative_summary = new_summary
            self.set("cumulative_summary", new_summary)

            cleaned = [
                {
                    "role": "system",
                    "content": f"Previous Conversation Summary: {new_summary}",
                }
            ] + remaining_messages

            tokens_before = self.estimate_tokens(conversation)
            tokens_after = self.estimate_tokens(cleaned)
            self.logger.info(
                f"Conversation summarized: {tokens_before} -> {tokens_after} tokens "
                f"({len(conversation)} -> {len(cleaned)} messages)."
            )
            return cleaned

        except Exception as e:
            self.logger.error(f"Failed to summarize conversation history: {e}")
            return conversation

    # ----------------------------------------------------------------
    # Reasoning cache (ChromaDB)
    # ----------------------------------------------------------------

    def add_to_reasoning_cache(self, error: str, solution: str):
        """Adds an error and its solution to the reasoning cache with LRU eviction."""
        try:
            error_embedding = self.embedding_client.get_embedding(error)
            error_hash = str(hash(error))

            # LRU eviction: remove oldest entries if cache exceeds max size
            self._evict_reasoning_cache_if_needed()

            self.reasoning_cache_collection.add(
                embeddings=[error_embedding],
                documents=[solution],
                metadatas=[{"error": error}],
                ids=[error_hash],
            )
            self.logger.info(f"Added new reasoning to cache for error: {error[:100]}...")
        except Exception as e:
            self.logger.error(f"Failed to add to reasoning cache: {e}")

    def _evict_reasoning_cache_if_needed(self):
        """Evicts oldest entries from reasoning cache when it exceeds max size."""
        try:
            count = self.reasoning_cache_collection.count()
            if count >= self._reasoning_cache_max_size:
                # Remove the oldest 10% of entries
                evict_count = max(1, count // 10)
                all_items = self.reasoning_cache_collection.peek(evict_count)
                if all_items and all_items.get("ids"):
                    self.reasoning_cache_collection.delete(ids=all_items["ids"])
                    self.logger.info(f"Evicted {len(all_items['ids'])} old entries from reasoning cache (LRU).")
        except Exception as e:
            self.logger.error(f"Failed to evict reasoning cache: {e}")

    def search_reasoning_cache(self, error: str, threshold: float = 0.95) -> str | None:
        """Searches for a similar error in the reasoning cache and returns a solution if found."""
        try:
            error_embedding = self.embedding_client.get_embedding(error)

            results = self.reasoning_cache_collection.query(query_embeddings=[error_embedding], n_results=1)

            if results and results["distances"][0] and results["distances"][0][0] >= threshold:
                solution = results["documents"][0][0]
                self.logger.info(
                    f"Found similar reasoning in cache with similarity {results['distances'][0][0]}. Reusing solution."
                )
                return solution
            else:
                self.logger.info("No sufficiently similar reasoning found in cache.")
                return None
        except Exception as e:
            self.logger.error(f"Failed to search reasoning cache: {e}")
            return None
