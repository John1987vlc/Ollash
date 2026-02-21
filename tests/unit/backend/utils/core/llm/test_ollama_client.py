import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import requests

from backend.utils.core.llm.ollama_client import OllamaClient


@pytest.fixture
def mock_logger():
    return MagicMock()


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


class TestOllamaClient:
    """Test suite for OllamaClient with isolation from real API calls."""

    def test_init(self, ollama_client):
        assert ollama_client.base_url == "http://localhost:11434"
        assert ollama_client.model == "qwen3"
        assert ollama_client.embedding_model == "mxbai-embed-large"

    def test_chat_success(self, ollama_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "Hello world"}, "done": True}

        with patch.object(ollama_client.http_session, "post", return_value=mock_response) as mock_post:
            messages = [{"role": "user", "content": "hi"}]
            data, usage = ollama_client.chat(messages, tools=[])

            assert data["message"]["content"] == "Hello world"
            assert "total_tokens" in usage
            mock_post.assert_called_once()

    def test_chat_model_not_found_pull_retry(self, ollama_client):
        resp_404 = MagicMock()
        resp_404.status_code = 404
        resp_404.text = "model not found"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"message": {"content": "fixed"}}

        with patch.object(ollama_client.http_session, "post") as mock_post:
            with patch.object(ollama_client, "_pull_model", return_value=True) as mock_pull:
                error_404 = requests.exceptions.HTTPError(response=resp_404)
                mock_post.side_effect = [error_404, resp_200]

                messages = [{"role": "user", "content": "hi"}]
                data, usage = ollama_client.chat(messages, tools=[])

                assert data["message"]["content"] == "fixed"
                assert mock_pull.called
                assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_achat_success(self, ollama_client):
        mock_data = {"message": {"content": "async hello"}}

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_data)
        mock_response.raise_for_status = MagicMock()

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock()

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_ctx)

        with patch.object(ollama_client, "_get_aiohttp_session", return_value=mock_session):
            messages = [{"role": "user", "content": "hi"}]
            data, usage = await ollama_client.achat(messages, tools=[])

            assert data["message"]["content"] == "async hello"
            assert usage["total_tokens"] > 0

    def test_get_embedding_cached(self, ollama_client):
        ollama_client._embedding_cache.put("hello", [0.1, 0.2])

        with patch.object(ollama_client.http_session, "post") as mock_post:
            emb = ollama_client.get_embedding("hello")
            assert emb == [0.1, 0.2]
            mock_post.assert_not_called()

    def test_get_embedding_api_call(self, ollama_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"embedding": [0.5, 0.6]}

        with patch.object(ollama_client.http_session, "post", return_value=mock_response):
            emb = ollama_client.get_embedding("new text")
            assert emb == [0.5, 0.6]
            assert ollama_client._embedding_cache.get("new text") == [0.5, 0.6]

    @pytest.mark.asyncio
    async def test_aget_embedding_success(self, ollama_client):
        mock_data = {"embedding": [0.9, 0.8]}

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_data)
        mock_response.raise_for_status = MagicMock()

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock()

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_ctx)

        with patch.object(ollama_client, "_get_aiohttp_session", return_value=mock_session):
            emb = await ollama_client.aget_embedding("async text")
            assert emb == [0.9, 0.8]

    def test_unload_model(self, ollama_client):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(ollama_client.http_session, "post", return_value=mock_response) as mock_post:
            ollama_client.unload_model("target-model")
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert kwargs["json"]["keep_alive"] == 0
            assert kwargs["json"]["model"] == "target-model"
