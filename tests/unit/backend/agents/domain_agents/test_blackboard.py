"""Unit tests for Blackboard."""

import pytest
from unittest.mock import MagicMock
from backend.agents.orchestrators.blackboard import Blackboard
from backend.utils.core.system.event_publisher import EventPublisher


@pytest.fixture
def blackboard():
    ep = MagicMock(spec=EventPublisher)
    ep.subscribe = MagicMock()
    ep.publish = MagicMock()
    logger = MagicMock()
    return Blackboard(event_publisher=ep, logger=logger)


@pytest.mark.unit
class TestBlackboard:
    @pytest.mark.asyncio
    async def test_write_and_read(self, blackboard):
        await blackboard.write("key", "value", "agent")
        assert blackboard.read("key") == "value"

    @pytest.mark.asyncio
    async def test_read_default_when_missing(self, blackboard):
        assert blackboard.read("nonexistent", default="fallback") == "fallback"

    @pytest.mark.asyncio
    async def test_write_publishes_event(self, blackboard):
        await blackboard.write("k", "v", "arch")
        blackboard._event_publisher.publish.assert_called_with(
            "blackboard_updated", key="k", agent_id="arch", version=1
        )

    @pytest.mark.asyncio
    async def test_invalidate_returns_default(self, blackboard):
        await blackboard.write("key", "original", "a")
        await blackboard.invalidate("key", "b")
        assert blackboard.read("key") is None

    @pytest.mark.asyncio
    async def test_invalidate_publishes_event(self, blackboard):
        await blackboard.write("key", "val", "a")
        blackboard._event_publisher.publish.reset_mock()
        await blackboard.invalidate("key", "b")
        blackboard._event_publisher.publish.assert_called_with("blackboard_invalidated", key="key", agent_id="b")

    @pytest.mark.asyncio
    async def test_snapshot_excludes_invalidated(self, blackboard):
        await blackboard.write("a", 1, "x")
        await blackboard.write("b", 2, "x")
        await blackboard.invalidate("a", "x")
        snap = blackboard.snapshot()
        assert "a" not in snap
        assert snap["b"] == 2

    @pytest.mark.asyncio
    async def test_read_prefix(self, blackboard):
        await blackboard.write("generated_files/src/main.py", "content1", "dev")
        await blackboard.write("generated_files/src/utils.py", "content2", "dev")
        await blackboard.write("scan_results/src/main.py", "{}", "auditor")
        result = blackboard.read_prefix("generated_files/")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_version_increments(self, blackboard):
        await blackboard.write("a", 1, "x")
        await blackboard.write("b", 2, "x")
        assert blackboard._version_counter == 2

    @pytest.mark.asyncio
    async def test_get_all_generated_files(self, blackboard):
        await blackboard.write("generated_files/src/main.py", "code", "dev")
        files = blackboard.get_all_generated_files()
        assert "src/main.py" in files
        assert files["src/main.py"] == "code"
