import pytest
from unittest.mock import MagicMock
from backend.utils.domains.auto_generation.project_planner import ProjectPlanner


@pytest.fixture
def mock_llm_client():
    return MagicMock()


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def planner(mock_llm_client, mock_logger):
    return ProjectPlanner(llm_client=mock_llm_client, logger=mock_logger)


class TestProjectPlanner:
    """Test suite for Phase 1: README Generation."""

    def test_generate_readme_success(self, planner, mock_llm_client):
        # Setup mock response
        mock_llm_client.chat.return_value = (
            {"message": {"content": "# Test Project\nGenerated README"}},
            {"usage": {}},
        )

        result = planner.generate_readme(
            project_description="Test Description", template_name="default", python_version="3.12"
        )

        assert "# Test Project" in result
        assert "Generated README" in result
        mock_llm_client.chat.assert_called_once()

        # Verify prompt templates were called correctly
        args, kwargs = mock_llm_client.chat.call_args
        messages = kwargs["messages"]
        assert any("Test Description" in m["content"] for m in messages if m["role"] == "user")
