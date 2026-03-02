"""Unit tests for critic_loop.py — Feature 1."""

import pytest
from unittest.mock import MagicMock


@pytest.mark.unit
class TestCriticLoopReview:
    def _make_critic(self, response_content: str):
        from backend.utils.core.analysis.critic_loop import CriticLoop

        mock_client = MagicMock()
        mock_client.chat.return_value = ({"content": response_content}, {})

        mock_manager = MagicMock()
        mock_manager.get_client.return_value = mock_client

        mock_logger = MagicMock()
        return CriticLoop(mock_manager, mock_logger)

    def test_no_errors_returns_none(self):
        critic = self._make_critic('{"has_errors": false, "errors": []}')
        result = critic.review("test.py", "import os\n\nos.getcwd()", "python")
        assert result is None

    def test_errors_returns_joined_string(self):
        critic = self._make_critic(
            '{"has_errors": true, "errors": ["Missing colon on line 2", "Indentation error"]}'
        )
        result = critic.review("test.py", "def foo()\n  pass", "python")
        assert result is not None
        assert "Missing colon" in result
        assert "Indentation error" in result

    def test_malformed_json_returns_none(self):
        critic = self._make_critic("This is not JSON at all")
        result = critic.review("test.py", "x = 1", "python")
        assert result is None

    def test_llm_exception_returns_none(self):
        from backend.utils.core.analysis.critic_loop import CriticLoop

        mock_manager = MagicMock()
        mock_manager.get_client.side_effect = RuntimeError("LLM down")
        mock_logger = MagicMock()

        critic = CriticLoop(mock_manager, mock_logger)
        result = critic.review("test.py", "x = 1", "python")
        assert result is None

    def test_unknown_language_returns_none(self):
        critic = self._make_critic('{"has_errors": false, "errors": []}')
        result = critic.review("file.bin", "binary", "unknown")
        assert result is None

    def test_empty_content_returns_none(self):
        critic = self._make_critic('{"has_errors": true, "errors": ["X"]}')
        result = critic.review("test.py", "", "python")
        assert result is None

    def test_errors_list_is_semicolon_joined(self):
        critic = self._make_critic(
            '{"has_errors": true, "errors": ["err1", "err2", "err3"]}'
        )
        result = critic.review("test.py", "x = 1", "python")
        assert result == "err1; err2; err3"

    def test_markdown_fenced_json_is_parsed(self):
        critic = self._make_critic(
            "```json\n{\"has_errors\": false, \"errors\": []}\n```"
        )
        result = critic.review("test.py", "x = 1", "python")
        assert result is None
