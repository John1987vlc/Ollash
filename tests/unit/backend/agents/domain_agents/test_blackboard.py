"""Unit tests for Blackboard."""

import pytest
from unittest.mock import MagicMock
from backend.agents.orchestrators.blackboard import Blackboard
from backend.utils.core.system.event_publisher import EventPublisher


@pytest.fixture
def blackboard():
    ep = MagicMock(spec=EventPublisher)
    ep.subscribe = MagicMock()
    ep.publish_sync = MagicMock()
    logger = MagicMock()
    return Blackboard(event_publisher=ep, logger=logger)


@pytest.mark.unit
class TestBlackboard:
    def test_write_and_read(self, blackboard):
        blackboard.write("key", "value", "agent")
        assert blackboard.read("key") == "value"

    def test_read_default_when_missing(self, blackboard):
        assert blackboard.read("nonexistent", default="fallback") == "fallback"

    def test_write_publishes_event(self, blackboard):
        blackboard.write("k", "v", "arch")
        blackboard._event_publisher.publish_sync.assert_called_with(
            "blackboard_updated", key="k", agent_id="arch", version=1
        )

    def test_invalidate_returns_default(self, blackboard):
        blackboard.write("key", "original", "a")
        blackboard.invalidate("key", "b")
        assert blackboard.read("key") is None

    def test_invalidate_publishes_event(self, blackboard):
        blackboard.write("key", "val", "a")
        blackboard._event_publisher.publish_sync.reset_mock()
        blackboard.invalidate("key", "b")
        blackboard._event_publisher.publish_sync.assert_called_with("blackboard_invalidated", key="key", agent_id="b")

    def test_snapshot_excludes_invalidated(self, blackboard):
        blackboard.write("a", 1, "x")
        blackboard.write("b", 2, "x")
        blackboard.invalidate("a", "x")
        snap = blackboard.snapshot()
        assert "a" not in snap
        assert snap["b"] == 2

    def test_read_prefix(self, blackboard):
        blackboard.write("generated_files/src/main.py", "content1", "dev")
        blackboard.write("generated_files/src/utils.py", "content2", "dev")
        blackboard.write("scan_results/src/main.py", "{}", "auditor")
        result = blackboard.read_prefix("generated_files/")
        assert len(result) == 2

    def test_version_increments(self, blackboard):
        blackboard.write("a", 1, "x")
        blackboard.write("b", 2, "x")
        assert blackboard._version_counter == 2

    def test_get_all_generated_files(self, blackboard):
        blackboard.write("generated_files/src/main.py", "code", "dev")
        files = blackboard.get_all_generated_files()
        assert "src/main.py" in files
        assert files["src/main.py"] == "code"
