"""Unit tests for ToolDispatcher."""

import asyncio
import pytest
from unittest.mock import MagicMock
from backend.agents.orchestrators.tool_dispatcher import ToolDispatcher
from backend.utils.core.system.event_publisher import EventPublisher


@pytest.fixture
def dispatcher():
    ep = MagicMock(spec=EventPublisher)
    ep.publish = MagicMock()
    logger = MagicMock()
    return ToolDispatcher(event_publisher=ep, logger=logger, max_batch_size=3)


@pytest.mark.unit
class TestToolDispatcher:
    @pytest.mark.asyncio
    async def test_register_and_dispatch(self, dispatcher):
        async def my_tool(x):
            return x * 2

        dispatcher.register_tool("double", my_tool)
        result = await dispatcher.dispatch("double", {"x": 5})
        assert result == 10

    def test_register_sync_raises(self, dispatcher):
        def sync_fn():
            pass

        with pytest.raises(TypeError, match="async coroutine"):
            dispatcher.register_tool("sync", sync_fn)

    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool_raises(self, dispatcher):
        with pytest.raises(KeyError):
            await dispatcher.dispatch("unknown", {})

    @pytest.mark.asyncio
    async def test_fire_and_forget_returns_none(self, dispatcher):
        async def slow_tool():
            await asyncio.sleep(0)
            return "done"

        dispatcher.register_tool("slow", slow_tool)
        result = await dispatcher.dispatch("slow", {}, fire_and_forget=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_publishes_events(self, dispatcher):
        async def tool():
            return "ok"

        dispatcher.register_tool("t", tool)
        await dispatcher.dispatch("t", {})
        calls = [c.args[0] for c in dispatcher._event_publisher.publish.call_args_list]
        assert "tool_dispatched" in calls
        assert "tool_completed" in calls

    @pytest.mark.asyncio
    async def test_dispatch_failure_publishes_tool_failed(self, dispatcher):
        async def broken():
            raise ValueError("oops")

        dispatcher.register_tool("broken", broken)
        result = await dispatcher.dispatch("broken", {})
        assert result is None
        calls = [c.args[0] for c in dispatcher._event_publisher.publish.call_args_list]
        assert "tool_failed" in calls

    @pytest.mark.asyncio
    async def test_dispatch_batch_returns_results(self, dispatcher):
        results_holder = []

        async def add(a, b):
            return a + b

        dispatcher.register_tool("add", add)
        results = await dispatcher.dispatch_batch(
            [
                ("add", {"a": 1, "b": 2}),
                ("add", {"a": 3, "b": 4}),
            ]
        )
        assert results == [3, 7]

    @pytest.mark.asyncio
    async def test_dispatch_batch_chunks_by_max_size(self, dispatcher):
        call_log = []

        async def track(**kwargs):
            call_log.append(kwargs)
            return True

        dispatcher.register_tool("track", track)
        calls = [("track", {"n": i}) for i in range(7)]
        results = await dispatcher.dispatch_batch(calls)
        assert len(results) == 7
        assert all(r is True for r in results)
