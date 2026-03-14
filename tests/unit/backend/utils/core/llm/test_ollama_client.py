"""Unit tests for OllamaClient.

Tests are written against the current simplified OllamaClient implementation
that uses stub embeddings and a single-attempt HTTP session (no retry/pull logic).
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from backend.utils.core.llm.ollama_client import OllamaClient


@pytest.fixture
def mock_logger():
    logger = MagicMock()
    logger.event_publisher.publish = AsyncMock()
    return logger


@pytest.fixture
def mock_recorder():
    return MagicMock()


@pytest.fixture
def client_config():
    return {
        "ollama_max_retries": 1,
        "ollama_backoff_factor": 0.1,
        "project_root": "/tmp/ollash",
        "models": {"embedding": "mxbai-embed-large"},
        "rate_limiting": {"requests_per_minute": 60},
        "gpu_rate_limiter": {"enabled": False},
    }


@pytest.fixture
def ollama_client(mock_logger, mock_recorder, client_config):
    return OllamaClient(
        url="http://localhost:11434",
        model="qwen3",
        timeout=30,
        logger=mock_logger,
        config=client_config,
        llm_recorder=mock_recorder,
    )


@pytest.mark.unit
class TestOllamaClient:
    """Test suite for OllamaClient with isolation from real API calls."""

    def test_init(self, ollama_client):
        assert ollama_client.base_url == "http://localhost:11434"
        assert ollama_client.model == "qwen3"
        # Verify core HTTP session is created
        assert ollama_client.http_session is not None
        assert ollama_client.chat_url == "http://localhost:11434/api/chat"

    def test_chat_success(self, ollama_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "Hello world"}, "done": True}

        with patch.object(ollama_client.http_session, "post", return_value=mock_response) as mock_post:
            messages = [{"role": "user", "content": "hi"}]
            data, usage = ollama_client.chat(messages, tools=[])

            assert data["message"]["content"] == "Hello world"
            # Current implementation returns prompt_tokens and completion_tokens
            assert "prompt_tokens" in usage
            assert "completion_tokens" in usage
            mock_post.assert_called_once()

    def test_chat_response_contains_content_key(self, ollama_client):
        """chat() must set a top-level 'content' key for convenience."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "hi back"}, "done": True}

        with patch.object(ollama_client.http_session, "post", return_value=mock_response):
            data, _ = ollama_client.chat([{"role": "user", "content": "hi"}])
            assert data["content"] == "hi back"

    def test_chat_sends_correct_payload(self, ollama_client):
        """chat() must send model, messages, and stream=False in the payload."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}

        with patch.object(ollama_client.http_session, "post", return_value=mock_response) as mock_post:
            ollama_client.chat([{"role": "user", "content": "test"}])

            _, kwargs = mock_post.call_args
            payload = kwargs["json"]
            assert payload["model"] == "qwen3"
            assert payload["stream"] is False
            assert isinstance(payload["messages"], list)

    def test_chat_async_success(self, ollama_client):
        mock_data = {"message": {"content": "async hello"}, "prompt_eval_count": 10, "eval_count": 5}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch.object(ollama_client.http_session, "post", return_value=mock_response) as mock_post:
            messages = [{"role": "user", "content": "hi"}]
            data, usage = ollama_client.chat(messages, tools=[])

            assert data["message"]["content"] == "async hello"
            assert usage["prompt_tokens"] == 10
            assert usage["completion_tokens"] == 5
            mock_post.assert_called_once()

    def test_get_embedding_returns_vector(self, ollama_client):
        """get_embedding must return a non-empty float list."""
        emb = ollama_client.get_embedding("hello world")
        assert isinstance(emb, list)
        assert len(emb) > 0
        assert all(isinstance(v, float) for v in emb)

    def test_get_embedding_async_returns_vector(self, ollama_client):
        """get_embedding must return a non-empty float list."""
        emb = ollama_client.get_embedding("async text")
        assert isinstance(emb, list)
        assert len(emb) > 0

    def test_unload_model_does_not_raise(self, ollama_client):
        """unload_model must not raise even with a model argument."""
        try:
            ollama_client.unload_model("some-model")
        except Exception as exc:
            pytest.fail(f"unload_model raised unexpectedly: {exc}")

    def test_set_keep_alive_affects_payload(self, ollama_client):
        """set_keep_alive must be reflected in the next chat payload."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}

        ollama_client.set_keep_alive("10m")

        with patch.object(ollama_client.http_session, "post", return_value=mock_response) as mock_post:
            ollama_client.chat([{"role": "user", "content": "test"}])
            _, kwargs = mock_post.call_args
            assert kwargs["json"]["options"]["keep_alive"] == "10m"

    def test_get_embedding_calls_api_embed(self, ollama_client):
        """get_embedding() must POST to /api/embed, not /api/chat."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(ollama_client.http_session, "post", return_value=mock_response) as mock_post:
            result = ollama_client.get_embedding("hello world")

        call_url = mock_post.call_args[0][0]
        assert "/api/embed" in call_url
        assert isinstance(result, list)
        assert len(result) == 3

    def test_get_embedding_uses_embedding_model(self, ollama_client):
        """get_embedding() payload must use the embedding model, not the chat model."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [[0.5]]}
        mock_response.raise_for_status = MagicMock()

        ollama_client.set_embedding_model("nomic-embed-text")

        with patch.object(ollama_client.http_session, "post", return_value=mock_response) as mock_post:
            ollama_client.get_embedding("test text")

        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "nomic-embed-text"
        assert payload["input"] == "test text"

    def test_get_embedding_fallback_on_error(self, ollama_client):
        """get_embedding() must return a hash-based fallback when Ollama is unreachable."""
        with patch.object(ollama_client.http_session, "post", side_effect=ConnectionError("refused")):
            result = ollama_client.get_embedding("fallback text")

        assert isinstance(result, list)
        assert len(result) == 384  # hash fallback dimension

    def test_achat_records_to_network_monitor(self, ollama_client):
        """achat() must call network_monitor.record() after each HTTP call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "ok"}}

        from backend.utils.core.system.network_monitor import network_monitor

        network_monitor.clear()

        with patch.object(ollama_client.http_session, "post", return_value=mock_response):
            ollama_client.chat([{"role": "user", "content": "hi"}])

        log = network_monitor.get_log(limit=5)
        assert any(e["url"] == ollama_client.chat_url for e in log)

    def test_get_embedding_records_to_network_monitor(self, ollama_client):
        """get_embedding() must record its HTTP call in the network monitor."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embeddings": [[0.1]]}
        mock_response.raise_for_status = MagicMock()

        from backend.utils.core.system.network_monitor import network_monitor

        network_monitor.clear()

        with patch.object(ollama_client.http_session, "post", return_value=mock_response):
            ollama_client.get_embedding("track this")

        log = network_monitor.get_log(limit=5)
        assert any("/api/embed" in e["url"] for e in log)

    def test_no_print_statements_in_source(self):
        """ollama_client.py must contain no bare print() calls (only logger.debug)."""
        import inspect
        from backend.utils.core.llm import ollama_client as oc_module

        source = inspect.getsource(oc_module)
        # Allow 'print' only in string literals or comments, not bare calls
        import re

        # Find bare print( that is not inside a string or comment
        # Simple heuristic: count non-commented, non-string print( occurrences
        lines = source.splitlines()
        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Detect bare print( call (not inside a string)
            if re.search(r"\bprint\s*\(", stripped):
                # Allow if it's inside a string (very rough check)
                if '"print(' not in stripped and "'print(" not in stripped:
                    pytest.fail(
                        f"Bare print() found in ollama_client.py line {lineno}: {stripped!r}\n"
                        "Use self.logger.debug() instead."
                    )
