import pytest
from unittest.mock import MagicMock
from backend.utils.core.system.event_publisher import EventPublisher


@pytest.fixture
def publisher():
    return EventPublisher()


class TestEventPublisher:
    """Test suite for internal Pub/Sub event system."""

    def test_subscribe_and_publish(self, publisher):
        callback = MagicMock()
        publisher.subscribe("test_event", callback)

        publisher.publish("test_event", {"key": "value"})

        callback.assert_called_once_with(event_type="test_event", event_data={"key": "value"})

    def test_multiple_subscribers(self, publisher):
        cb1 = MagicMock()
        cb2 = MagicMock()
        publisher.subscribe("event", cb1)
        publisher.subscribe("event", cb2)

        publisher.publish("event", {"data": 1})

        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_unsubscribe(self, publisher):
        callback = MagicMock()
        publisher.subscribe("event", callback)
        publisher.unsubscribe("event", callback)

        publisher.publish("event", {"data": 1})
        callback.assert_not_called()

    def test_publish_kwargs(self, publisher):
        callback = MagicMock()
        publisher.subscribe("event", callback)

        publisher.publish("event", direct_data={"a": 1}, extra="info")

        # event_data should be merged
        callback.assert_called_once()
        args, kwargs = callback.call_args
        assert kwargs["event_data"]["direct_data"] == {"a": 1}
        assert kwargs["event_data"]["extra"] == "info"

    def test_callback_exception_isolation(self, publisher):
        cb_fail = MagicMock(side_effect=Exception("Boom"))
        cb_ok = MagicMock()

        publisher.subscribe("event", cb_fail)
        publisher.subscribe("event", cb_ok)

        # This should not raise and should call cb_ok
        publisher.publish("event", {})

        cb_fail.assert_called_once()
        cb_ok.assert_called_once()
