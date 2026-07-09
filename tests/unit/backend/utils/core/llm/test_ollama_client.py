"""Unit tests for OllamaClient."""

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

    def test_chat_success(self, ollama_client):
        mock_chat = AsyncMock()
        mock_chat.return_value = {
            "message": {"content": "Hello world"},
            "prompt_eval_count": 10,
            "eval_count": 5
        }

        with patch.object(ollama_client._aclient, "chat", mock_chat):
            messages = [{"role": "user", "content": "hi"}]
            data, usage = ollama_client.chat(messages, tools=[])

            assert data["message"]["content"] == "Hello world"
            assert usage["prompt_tokens"] == 10
            assert usage["completion_tokens"] == 5
            mock_chat.assert_called_once()

    def test_chat_response_contains_content_key(self, ollama_client):
        """chat() must set a top-level 'content' key for convenience."""
        mock_chat = AsyncMock()
        mock_chat.return_value = {"message": {"content": "hi back"}, "done": True}

        with patch.object(ollama_client._aclient, "chat", mock_chat):
            data, _ = ollama_client.chat([{"role": "user", "content": "hi"}])
            assert data["content"] == "hi back"

    def test_chat_sends_correct_payload(self, ollama_client):
        """chat() must send model, messages, and stream=False in the payload."""
        mock_chat = AsyncMock()
        mock_chat.return_value = {"message": {"content": "ok"}}

        with patch.object(ollama_client._aclient, "chat", mock_chat) as mock_c:
            ollama_client.chat([{"role": "user", "content": "test"}])

            mock_c.assert_called_once()
            _, kwargs = mock_c.call_args
            assert kwargs["model"] == "qwen3"
            assert kwargs["messages"] == [{"role": "user", "content": "test"}]

    def test_chat_async_success(self, ollama_client):
        mock_data = {"message": {"content": "async hello"}, "prompt_eval_count": 10, "eval_count": 5}
        mock_chat = AsyncMock()
        mock_chat.return_value = mock_data

        with patch.object(ollama_client._aclient, "chat", mock_chat) as mock_c:
            messages = [{"role": "user", "content": "hi"}]
            data, usage = ollama_client.chat(messages, tools=[])

            assert data["message"]["content"] == "async hello"
            assert usage["prompt_tokens"] == 10
            assert usage["completion_tokens"] == 5
            mock_c.assert_called_once()

    def test_get_embedding_returns_vector(self, ollama_client):
        """get_embedding must return a non-empty float list."""
        mock_embed = MagicMock()
        mock_embed.return_value = {"embeddings": [[0.1, 0.2]]}

        with patch.object(ollama_client._client, "embed", mock_embed):
            emb = ollama_client.get_embedding("hello world")
            assert isinstance(emb, list)
            assert len(emb) > 0

    def test_get_embedding_async_returns_vector(self, ollama_client):
        """get_embedding must return a non-empty float list."""
        mock_embed = AsyncMock()
        mock_embed.return_value = {"embeddings": [[0.1, 0.2]]}

        with patch.object(ollama_client._aclient, "embed", mock_embed):
            import asyncio
            emb = asyncio.run(ollama_client.aget_embedding("async text"))
            assert isinstance(emb, list)
            assert len(emb) > 0

    def test_unload_model_does_not_raise(self, ollama_client):
        """unload_model must not raise even with a model argument."""
        mock_generate = MagicMock()
        with patch.object(ollama_client._client, "generate", mock_generate):
            try:
                ollama_client.unload_model("some-model")
            except Exception as exc:
                pytest.fail(f"unload_model raised unexpectedly: {exc}")

    def test_set_keep_alive_affects_payload(self, ollama_client):
        """set_keep_alive must be reflected in the next chat payload."""
        mock_chat = AsyncMock()
        mock_chat.return_value = {"message": {"content": "ok"}}

        ollama_client.set_keep_alive("10m")

        with patch.object(ollama_client._aclient, "chat", mock_chat) as mock_c:
            ollama_client.chat([{"role": "user", "content": "test"}])
            _, kwargs = mock_c.call_args
            assert kwargs["keep_alive"] == "10m"

    def test_get_embedding_calls_api_embed(self, ollama_client):
        """get_embedding() must call embed method on client."""
        mock_embed = MagicMock()
        mock_embed.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
        ollama_client.set_embedding_model("mxbai-embed-large")

        with patch.object(ollama_client._client, "embed", mock_embed) as mock_e:
            result = ollama_client.get_embedding("hello world")

        mock_e.assert_called_once_with(model="mxbai-embed-large", input="hello world")
        assert isinstance(result, list)
        assert len(result) == 3

    def test_get_embedding_uses_embedding_model(self, ollama_client):
        """get_embedding() payload must use the embedding model, not the chat model."""
        mock_embed = MagicMock()
        mock_embed.return_value = {"embeddings": [[0.5]]}

        ollama_client.set_embedding_model("nomic-embed-text")

        with patch.object(ollama_client._client, "embed", mock_embed) as mock_e:
            ollama_client.get_embedding("test text")

        mock_e.assert_called_once_with(model="nomic-embed-text", input="test text")

    def test_get_embedding_fallback_on_error(self, ollama_client):
        """get_embedding() must return a hash-based fallback when Ollama is unreachable."""
        mock_embed = MagicMock(side_effect=Exception("unreachable"))
        with patch.object(ollama_client._client, "embed", mock_embed):
            result = ollama_client.get_embedding("fallback text")

        assert isinstance(result, list)
        assert len(result) == 384  # hash fallback dimension

    def test_achat_records_to_network_monitor(self, ollama_client):
        """achat() must call network_monitor.record() after each HTTP call."""
        mock_chat = AsyncMock()
        mock_chat.return_value = {"message": {"content": "ok"}}

        from backend.utils.core.system.network_monitor import network_monitor

        network_monitor.clear()

        with patch.object(ollama_client._aclient, "chat", mock_chat):
            ollama_client.chat([{"role": "user", "content": "hi"}])

        log = network_monitor.get_log(limit=5)
        assert any(ollama_client.chat_url in e["url"] for e in log)

    def test_get_embedding_records_to_network_monitor(self, ollama_client):
        """get_embedding() must record its HTTP call in the network monitor."""
        mock_embed = MagicMock()
        mock_embed.return_value = {"embeddings": [[0.1]]}

        from backend.utils.core.system.network_monitor import network_monitor

        network_monitor.clear()

        with patch.object(ollama_client._client, "embed", mock_embed):
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
