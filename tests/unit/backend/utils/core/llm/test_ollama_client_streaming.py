"""Unit tests — OllamaClient.stream_chat (P4)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


def _ndjson(*chunks: dict) -> bytes:
    """Build NDJSON bytes from a sequence of chunk dicts."""
    return b"\n".join(json.dumps(c).encode() for c in chunks)


@pytest.mark.unit
class TestOllamaClientStreamChat:
    @pytest.mark.asyncio
    async def test_stream_chat_accumulates_content(self):
        client = _make_client()

        chunks = [
            {"message": {"content": "Hello"}, "done": False},
            {"message": {"content": ", world"}, "done": False},
            {"message": {"content": "!"}, "done": True, "prompt_eval_count": 5, "eval_count": 3},
        ]
        ndjson_data = _ndjson(*chunks)

        # Mock aiohttp response
        mock_resp = AsyncMock()
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        async def _iter_lines(self):
            for line in ndjson_data.split(b"\n"):
                yield line

        mock_resp.content.__aiter__ = _iter_lines

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        with patch.object(client, "_get_aiohttp_session", return_value=mock_session):
            result, usage = await client.stream_chat(
                messages=[{"role": "user", "content": "Hi"}],
                chunk_callback=None,
            )

        assert result["content"] == "Hello, world!"
        assert usage["prompt_tokens"] == 5
        assert usage["completion_tokens"] == 3

    @pytest.mark.asyncio
    async def test_stream_chat_calls_chunk_callback(self):
        client = _make_client()
        received = []

        async def callback(chunk: str):
            received.append(chunk)

        chunks = [
            {"message": {"content": "A"}, "done": False},
            {"message": {"content": "B"}, "done": True, "prompt_eval_count": 1, "eval_count": 2},
        ]
        ndjson_data = _ndjson(*chunks)

        mock_resp = AsyncMock()
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        async def _iter_lines(self):
            for line in ndjson_data.split(b"\n"):
                yield line

        mock_resp.content.__aiter__ = _iter_lines

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.closed = False

        with patch.object(client, "_get_aiohttp_session", return_value=mock_session):
            await client.stream_chat(
                messages=[{"role": "user", "content": "Hi"}],
                chunk_callback=callback,
            )

        assert "A" in received
        assert "B" in received
