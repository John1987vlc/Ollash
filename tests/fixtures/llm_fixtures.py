"""LLM / Ollama fixtures — session-wide mock and error scenarios."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def block_ollama_globally():
    """Session-wide fixture that automatically mocks OllamaClient.

    Provides realistic mocked responses based on prompt content to avoid
    retry loops. All tests run without a real Ollama instance.
    """
    with patch("backend.utils.core.llm.ollama_client.OllamaClient") as mock_client:
        mock_instance = mock_client.return_value

        async def smart_achat(messages, **kwargs):
            prompt = str(messages).lower()
            content = "Mocked LLM Response"

            if "structure" in prompt or "folders" in prompt:
                content = json.dumps({
                    "folders": [
                        {"name": "src", "files": ["main.py"]},
                        {"name": "tests", "files": ["test_main.py"]},
                    ],
                    "root_files": ["README.md", "requirements.txt"],
                })
            elif "plan" in prompt or "logic" in prompt:
                content = "1. Setup project\n2. Implement core logic\n3. Add tests"
            elif "readme" in prompt:
                content = "# Mocked Project\nThis is a mocked project description for testing."

            return (
                {"message": {"content": content}},
                {"prompt_tokens": 10, "completion_tokens": 10},
            )

        # Async methods
        mock_instance.achat = AsyncMock(side_effect=smart_achat)
        mock_instance.agenerate = AsyncMock(
            side_effect=lambda prompt, **kwargs: (
                {"response": "Mocked response"},
                {"prompt_tokens": 5, "completion_tokens": 5},
            )
        )
        mock_instance.aembed = AsyncMock(return_value=[0.1] * 384)

        # Sync methods
        mock_instance.chat.side_effect = lambda messages, **kwargs: (
            {"message": {"content": "Mocked sync response"}},
            {"prompt_tokens": 5, "completion_tokens": 5},
        )
        mock_instance.generate.side_effect = lambda prompt, **kwargs: (
            {"response": "Mocked sync response"},
            {"prompt_tokens": 5, "completion_tokens": 5},
        )
        mock_instance.get_embedding.return_value = [0.1] * 384
        mock_instance.list_models.return_value = {"models": [{"name": "qwen3-coder:30b"}]}

        yield mock_client


@pytest.fixture
def mock_ollama(block_ollama_globally):
    """Fixture alias for backward compatibility with older tests."""
    return block_ollama_globally


@pytest.fixture
def ollama_network_error(monkeypatch):
    """Simulates a network-level connection failure (connection refused).

    Use this fixture in tests that verify agent resilience when Ollama is
    unreachable. Overrides the session-level mock for the duration of the test.
    """
    import httpx

    mock = MagicMock()
    mock.achat = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock.agenerate = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock.chat = MagicMock(side_effect=httpx.ConnectError("Connection refused"))
    mock.generate = MagicMock(side_effect=httpx.ConnectError("Connection refused"))
    mock.list_models = MagicMock(return_value={"models": []})

    monkeypatch.setattr(
        "backend.utils.core.llm.ollama_client.OllamaClient",
        lambda *a, **kw: mock,
    )
    return mock


@pytest.fixture
def ollama_timeout(monkeypatch):
    """Simulates a response timeout from Ollama.

    The async methods never return (infinite sleep), mimicking a server that
    accepts the connection but stops responding mid-request.
    """
    import asyncio

    mock = MagicMock()

    async def _timeout(*args, **kwargs):
        await asyncio.sleep(9999)

    mock.achat = AsyncMock(side_effect=_timeout)
    mock.agenerate = AsyncMock(side_effect=_timeout)
    mock.list_models = MagicMock(return_value={"models": []})

    monkeypatch.setattr(
        "backend.utils.core.llm.ollama_client.OllamaClient",
        lambda *a, **kw: mock,
    )
    return mock


@pytest.fixture
def ollama_partial_stream_error(monkeypatch):
    """Simulates a stream that delivers some tokens and then raises an error.

    Useful for testing partial-response recovery logic.
    """
    import httpx

    call_count = {"n": 0}

    mock = MagicMock()

    async def _partial(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] <= 1:
            # First call: deliver one chunk then raise
            raise httpx.RemoteProtocolError("Unexpected disconnect mid-stream")
        # Subsequent calls succeed (retry scenario)
        return (
            {"message": {"content": "Recovered response"}},
            {"prompt_tokens": 5, "completion_tokens": 5},
        )

    mock.achat = AsyncMock(side_effect=_partial)
    mock.agenerate = AsyncMock(side_effect=_partial)
    mock.list_models = MagicMock(return_value={"models": []})

    monkeypatch.setattr(
        "backend.utils.core.llm.ollama_client.OllamaClient",
        lambda *a, **kw: mock,
    )
    return mock
