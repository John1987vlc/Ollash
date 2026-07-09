"""Unit tests — OllamaClient.stream_chat."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.utils.core.llm.ollama_client import OllamaClient


def _make_client() -> OllamaClient:
    logger = MagicMock()
    logger.event_publisher.publish = AsyncMock()
    return OllamaClient(
        url="http://localhost:11434",
        model="llama3",
        timeout=30,
        logger=logger,
        config=MagicMock(),
        llm_recorder=None,
    )


@pytest.mark.unit
class TestOllamaClientStreamChat:
    def test_stream_chat_accumulates_content(self):
        import asyncio

        client = _make_client()

        chunks = [
            {"message": {"content": "Hello"}, "done": False},
            {"message": {"content": ", world"}, "done": False},
            {"message": {"content": "!"}, "done": True, "prompt_eval_count": 5, "eval_count": 3},
        ]

        async def mock_chat(*args, **kwargs):
            async def generator():
                for chunk in chunks:
                    yield chunk
            return generator()

        with patch.object(client._aclient, "chat", mock_chat):
            result, usage = asyncio.run(
                client.stream_chat(
                    messages=[{"role": "user", "content": "Hi"}],
                    chunk_callback=None,
                )
            )

        assert result["content"] == "Hello, world!"
        assert usage["prompt_tokens"] == 5
        assert usage["completion_tokens"] == 3

    def test_stream_chat_calls_chunk_callback(self):
        import asyncio

        client = _make_client()
        received = []

        async def callback(chunk: str):
            received.append(chunk)

        chunks = [
            {"message": {"content": "A"}, "done": False},
            {"message": {"content": "B"}, "done": True, "prompt_eval_count": 1, "eval_count": 2},
        ]

        async def mock_chat(*args, **kwargs):
            async def generator():
                for chunk in chunks:
                    yield chunk
            return generator()

        with patch.object(client._aclient, "chat", mock_chat):
            asyncio.run(
                client.stream_chat(
                    messages=[{"role": "user", "content": "Hi"}],
                    chunk_callback=callback,
                )
            )

        assert "A" in received
        assert "B" in received
