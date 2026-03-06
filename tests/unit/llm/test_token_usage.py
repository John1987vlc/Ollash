from unittest.mock import MagicMock, patch, AsyncMock
from backend.utils.core.llm.token_tracker import TokenTracker
from backend.utils.core.llm.ollama_client import OllamaClient


def test_token_tracker_accumulation():
    """Test that TokenTracker correctly adds up tokens from multiple calls."""
    tracker = TokenTracker()

    # First call
    tracker.add_usage(100, 50)

    assert tracker.session_prompt_tokens == 100
    assert tracker.session_completion_tokens == 50
    assert tracker.session_total_tokens == 150
    assert tracker.last_request_tokens == 150

    # Second call
    tracker.add_usage(200, 75)

    assert tracker.session_prompt_tokens == 300
    assert tracker.session_completion_tokens == 125
    assert tracker.session_total_tokens == 425
    assert tracker.last_request_tokens == 275


@patch("requests.Session.post")
def test_ollama_client_updates_tracker(mock_post):
    """Test that OllamaClient automatically updates the tracker after a chat."""
    tracker = TokenTracker()
    logger = MagicMock()
    logger.event_publisher.publish = AsyncMock()

    # Mock Ollama response with specific token counts
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"message": {"content": "Hello!"}, "prompt_eval_count": 15, "eval_count": 5}
    mock_post.return_value = mock_response

    client = OllamaClient(
        url="http://localhost:11434",
        model="test-model",
        timeout=30,
        logger=logger,
        config={},
        llm_recorder=None,
        token_tracker=tracker,
    )

    # Perform chat
    client.chat([{"role": "user", "content": "Hi"}])

    # Verify tracker was updated
    assert tracker.session_prompt_tokens == 15
    assert tracker.session_completion_tokens == 5
    assert tracker.session_total_tokens == 20
    assert tracker.request_count == 1


def test_token_tracker_summary_format():
    """Test that the summary string contains the expected numbers."""
    tracker = TokenTracker()
    tracker.add_usage(1000, 500)

    summary = tracker.get_session_summary()

    assert "Prompt tokens: 1,000" in summary
    assert "Completion tokens: 500" in summary
    assert "Total tokens: 1,500" in summary
    assert "Requests: 1" in summary
