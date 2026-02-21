import pytest
import json
from unittest.mock import MagicMock
from backend.utils.domains.auto_generation.senior_reviewer import SeniorReviewer


@pytest.fixture
def mock_llm_client():
    return MagicMock()


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_parser():
    return MagicMock()


@pytest.fixture
def reviewer(mock_llm_client, mock_logger, mock_parser):
    return SeniorReviewer(llm_client=mock_llm_client, logger=mock_logger, response_parser=mock_parser)


class TestSeniorReviewer:
    """Test suite for Senior Architect Review logic."""

    def test_perform_review_success(self, reviewer, mock_llm_client, mock_parser):
        mock_review_data = {"status": "passed", "summary": "Great work", "issues": []}
        mock_llm_client.chat.return_value = ({"message": {"content": json.dumps(mock_review_data)}}, {})
        mock_parser.extract_json.return_value = mock_review_data

        result = reviewer.perform_review(
            project_description="desc",
            project_name="name",
            readme_content="# Title",
            json_structure={},
            current_files={"main.py": ""},
            review_attempt=1,
        )

        assert result["status"] == "passed"
        assert result["summary"] == "Great work"

    def test_perform_review_json_retry(self, reviewer, mock_llm_client, mock_parser):
        # 1. First call returns garbage
        # 2. Second call (retry) returns JSON

        mock_llm_client.chat.side_effect = [
            ({"message": {"content": "Garbage text"}}, {}),
            ({"message": {"content": '{"status": "failed", "summary": "fixed"}'}}, {}),
        ]

        mock_parser.extract_json.side_effect = [
            None,  # First fail
            {"status": "failed", "summary": "fixed"},  # Second success
        ]

        result = reviewer.perform_review(
            project_description="desc",
            project_name="name",
            readme_content="# Title",
            json_structure={},
            current_files={"main.py": ""},
            review_attempt=1,
        )

        assert result["summary"] == "fixed"
        assert mock_llm_client.chat.call_count == 2

    def test_perform_review_total_failure(self, reviewer, mock_llm_client, mock_parser):
        mock_llm_client.chat.return_value = ({"message": {"content": "Always garbage"}}, {})
        mock_parser.extract_json.return_value = None

        result = reviewer.perform_review(
            project_description="desc",
            project_name="name",
            readme_content="# Title",
            json_structure={},
            current_files={"main.py": ""},
            review_attempt=1,
        )

        assert result["status"] == "failed"
        assert "invalid JSON" in result["summary"]
