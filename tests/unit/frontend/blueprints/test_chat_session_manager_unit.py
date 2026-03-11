"""Unit tests for backend/services/chat_session_manager.py."""

from unittest.mock import patch

import pytest


class TestChatSessionManager:
    def test_create_session(self, tmp_path):
        with patch("backend.services.chat_session_manager.SimpleChatAgent"):
            from backend.utils.core.system.event_publisher import EventPublisher
            from backend.services.chat_session_manager import ChatSessionManager

            publisher = EventPublisher()
            mgr = ChatSessionManager(tmp_path, event_publisher=publisher)
            session_id = mgr.create_session()
            assert session_id is not None
            assert mgr.get_session(session_id) is not None

    def test_max_sessions_limit(self, tmp_path):
        with patch("backend.services.chat_session_manager.SimpleChatAgent"):
            from backend.utils.core.system.event_publisher import EventPublisher
            from backend.services.chat_session_manager import ChatSessionManager

            publisher = EventPublisher()
            mgr = ChatSessionManager(tmp_path, event_publisher=publisher)
            for _ in range(5):
                mgr.create_session()
            with pytest.raises(RuntimeError, match="Maximum"):
                mgr.create_session()

    def test_create_session_with_agent_type(self, tmp_path):
        with patch("backend.services.chat_session_manager.SimpleChatAgent") as MockAgent:
            from backend.utils.core.system.event_publisher import EventPublisher
            from backend.services.chat_session_manager import ChatSessionManager

            publisher = EventPublisher()
            mgr = ChatSessionManager(tmp_path, event_publisher=publisher)
            session_id = mgr.create_session(agent_type="code")

            # Session should be created and the SimpleChatAgent instantiated
            assert session_id is not None
            assert mgr.get_session(session_id) is not None
            MockAgent.assert_called_once()
