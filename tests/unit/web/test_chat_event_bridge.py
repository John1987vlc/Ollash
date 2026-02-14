"""Unit tests for src/web/services/chat_event_bridge.py."""
import pytest
from unittest.mock import MagicMock

class TestChatEventBridge:
    def test_push_and_iter(self):
        from frontend.services.chat_event_bridge import ChatEventBridge
        from backend.utils.core.event_publisher import EventPublisher
        publisher = EventPublisher()
        bridge = ChatEventBridge(publisher)
        bridge.push_event("test", {"key": "value"})
        bridge.close()

        events = list(bridge.iter_events())
        # Should have at least the test event and stream_end
        data_events = [e for e in events if e.startswith("data:")]
        assert len(data_events) >= 2  # test event + stream_end

    def test_close_sends_stream_end(self):
        from frontend.services.chat_event_bridge import ChatEventBridge
        from backend.utils.core.event_publisher import EventPublisher
        publisher = EventPublisher()
        bridge = ChatEventBridge(publisher)
        bridge.close()

        events = list(bridge.iter_events())
        joined = "".join(events)
        assert "stream_end" in joined
