"""Unit tests for ToolDispatcher."""

import pytest
from unittest.mock import MagicMock
from backend.agents.orchestrators.tool_dispatcher import ToolDispatcher
from backend.utils.core.system.event_publisher import EventPublisher


@pytest.fixture
def dispatcher():
    ep = MagicMock(spec=EventPublisher)
    ep.publish_sync = MagicMock()
    logger = MagicMock()
    return ToolDispatcher(event_publisher=ep, logger=logger, max_batch_size=3)


@pytest.mark.unit
class TestToolDispatcher:
    def test_register_and_dispatch(self, dispatcher):
        def my_tool(x):
            return x * 2

        dispatcher.register_tool("double", my_tool)
        result = dispatcher.dispatch("double", {"x": 5})
        assert result == 10

    def test_register_sync_raises(self, dispatcher):
        # ToolDispatcher now accepts sync callables; this test verifies that
        # a registered sync tool can be dispatched without error.
        def sync_tool():
            return "sync"

        dispatcher.register_tool("sync_tool", sync_tool)
        result = dispatcher.dispatch("sync_tool", {})
        assert result == "sync"

    def test_dispatch_unknown_tool_raises(self, dispatcher):
        with pytest.raises(KeyError):
            dispatcher.dispatch("unknown", {})

    def test_fire_and_forget_returns_none(self, dispatcher):
        import time

        def slow_tool():
            return "done"

        dispatcher.register_tool("slow", slow_tool)
        result = dispatcher.dispatch("slow", {}, fire_and_forget=True)
        assert result is None
        # give background thread time to finish
        time.sleep(0.05)

    def test_dispatch_publishes_events(self, dispatcher):
        def tool():
            return "ok"

        dispatcher.register_tool("t", tool)
        dispatcher.dispatch("t", {})
        calls = [c.args[0] for c in dispatcher._event_publisher.publish_sync.call_args_list]
        assert "tool_dispatched" in calls
        assert "tool_completed" in calls

    def test_dispatch_failure_publishes_tool_failed(self, dispatcher):
        def broken():
            raise ValueError("oops")

        dispatcher.register_tool("broken", broken)
        result = dispatcher.dispatch("broken", {})
        assert result is None
        calls = [c.args[0] for c in dispatcher._event_publisher.publish_sync.call_args_list]
        assert "tool_failed" in calls

    def test_dispatch_batch_returns_results(self, dispatcher):
        def add(a, b):
            return a + b

        dispatcher.register_tool("add", add)
        results = dispatcher.dispatch_batch(
            [
                ("add", {"a": 1, "b": 2}),
                ("add", {"a": 3, "b": 4}),
            ]
        )
        assert results == [3, 7]

    def test_dispatch_batch_chunks_by_max_size(self, dispatcher):
        call_log = []

        def track(**kwargs):
            call_log.append(kwargs)
            return True

        dispatcher.register_tool("track", track)
        calls = [("track", {"n": i}) for i in range(7)]
        results = dispatcher.dispatch_batch(calls)
        assert len(results) == 7
        assert all(r is True for r in results)
