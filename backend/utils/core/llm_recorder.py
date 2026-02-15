import json
from typing import Dict, List, Optional
from backend.utils.core.agent_logger import AgentLogger # Use AgentLogger for structured logging


class LLMRecorder:
    """
    Records detailed information about LLM interactions, including prompts, responses,
    token usage, latency, and model specific details.
    Uses AgentLogger for structured logging, automatically including correlation IDs.
    """
    def __init__(self, logger: AgentLogger):
        self._logger = logger

    def record_request(self, model: str, messages: List[Dict], tools: List[Dict], options: Dict):
        """
        Records an LLM request before it is sent.
        """
        prompt_hash = hash(json.dumps(messages)) # Use hash to avoid logging potentially very large prompts directly
        self._logger.info(
            f"LLM Request for {model}",
            extra={
                "event_type": "llm_request",
                "model": model,
                "prompt_hash": prompt_hash,
                "messages_preview": messages[0].get("content", "")[:100] if messages else "",
                "tool_names": [t["function"]["name"] for t in tools],
                "options": options,
            }
        )

    def record_response(self, model: str, response_data: Dict, usage: Dict, latency: float, success: bool, error: Optional[str] = None):
        """
        Records an LLM response after it is received or an error occurs.
        """
        response_hash = hash(json.dumps(response_data)) # Use hash to avoid logging potentially very large responses directly
        self._logger.info(
            f"LLM Response from {model}",
            extra={
                "event_type": "llm_response",
                "model": model,
                "response_hash": response_hash,
                "success": success,
                "latency_ms": latency * 1000,
                "usage": usage,
                "error": error,
            }
        )

    def record_embedding_request(self, model: str, text: str):
        """
        Records an embedding request before it is sent.
        """
        text_hash = hash(text)
        self._logger.info(
            f"Embedding Request for {model}",
            extra={
                "event_type": "embedding_request",
                "model": model,
                "text_hash": text_hash,
                "text_preview": text[:100],
            }
        )

    def record_embedding_response(self, model: str, embedding_len: int, latency: float, success: bool, error: Optional[str] = None):
        """
        Records an embedding response after it is received or an error occurs.
        """
        self._logger.info(
            f"Embedding Response from {model}",
            extra={
                "event_type": "embedding_response",
                "model": model,
                "embedding_length": embedding_len,
                "success": success,
                "latency_ms": latency * 1000,
                "error": error,
            }
        )
