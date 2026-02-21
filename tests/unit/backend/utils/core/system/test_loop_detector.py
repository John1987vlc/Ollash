import pytest
import time
from unittest.mock import MagicMock
from backend.utils.core.system.loop_detector import LoopDetector


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_embedding_client():
    client = MagicMock()
    # Default behavior: different strings give different embeddings
    client.get_embedding.side_effect = lambda x: [float(hash(x) % 100)] * 384
    return client


@pytest.fixture
def detector(mock_logger, mock_embedding_client):
    return LoopDetector(
        logger=mock_logger,
        embedding_client=mock_embedding_client,
        threshold=2,  # Small threshold for testing
        similarity_threshold=0.9,
        stagnation_timeout_minutes=1,
    )


class TestLoopDetector:
    """Test suite for Semantic Loop and Stagnation detection."""

    def test_record_action(self, detector):
        detector.record_action("tool", {"arg": 1}, "ok")
        assert len(detector.history) == 1
        assert detector.history[0]["tool_name"] == "tool"

    def test_detect_loop_semantic_similarity(self, detector, mock_embedding_client):
        # Force same embedding for two different actions to simulate semantic similarity
        mock_embedding_client.get_embedding.side_effect = None
        mock_embedding_client.get_embedding.return_value = [1.0] * 384

        detector.record_action("tool1", {"a": 1}, "res1")
        detector.record_action("tool1", {"a": 1}, "res1")  # Same action

        assert detector.detect_loop() is True
        detector.logger.warning.assert_called()

    def test_detect_loop_no_loop(self, detector, mock_embedding_client):
        # Different embeddings
        mock_embedding_client.get_embedding.side_effect = [[1.0] * 384, [0.0] * 384]

        detector.record_action("tool1", {}, "res1")
        detector.record_action("tool2", {}, "res2")

        assert detector.detect_loop() is False

    def test_stagnation_detection(self, detector, mock_embedding_client):
        # Different embeddings to avoid similarity loop
        mock_embedding_client.get_embedding.side_effect = [[1.0] * 384, [0.0] * 384]

        # Manipulate last meaningful action time to be old
        from datetime import datetime, timedelta

        detector.last_meaningful_action_time = datetime.now() - timedelta(minutes=2)

        # We need at least 'threshold' items in history
        detector.record_action("t1", {"a": 1}, "r1")
        detector.record_action("t2", {"a": 2}, "r2")

        # Call detect_loop
        assert detector.detect_loop() is True

        # Check if warning was logged.
        # Since it's a MagicMock, we check if it was called with a string containing "Stagnation"
        found = False
        for call in detector.logger.warning.call_args_list:
            if "Stagnation" in str(call.args[0]):
                found = True
                break
        assert found, f"Stagnation warning not found in {detector.logger.warning.call_args_list}"

    def test_update_progress_meaningful(self, detector):
        old_time = detector.last_meaningful_action_time
        time.sleep(0.01)

        # select_agent_type adds 1.0 to progress, which should trigger a meaningful action update
        detector.update_progress("select_agent_type", {"ok": True})

        assert detector.progress_score == 1.0
        assert detector.last_meaningful_action_time > old_time

    def test_reset(self, detector):
        detector.record_action("t", {}, "r")
        detector.progress_score = 5.0
        detector.reset()

        assert len(detector.history) == 0
        assert detector.progress_score == 0.0
