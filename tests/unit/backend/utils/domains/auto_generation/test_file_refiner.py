import pytest
from unittest.mock import MagicMock
from backend.utils.domains.auto_generation.file_refiner import FileRefiner


@pytest.fixture
def mock_deps():
    return {
        "llm_client": MagicMock(),
        "logger": MagicMock(),
        "response_parser": MagicMock(),
        "documentation_manager": MagicMock(),
    }


@pytest.fixture
def refiner(mock_deps):
    return FileRefiner(**mock_deps)


async def test_simplify_file_content_success(refiner, mock_deps):
    mock_deps["llm_client"].chat.return_value = ({"message": {"content": "```python\ndef simplified(): pass\n```"}}, {})
    mock_deps["response_parser"].extract_code.return_value = "def simplified(): pass"

    result = await refiner.simplify_file_content("test.py", "def complex():\n    pass")

    assert result == "def simplified(): pass"
    mock_deps["llm_client"].chat.assert_called()


async def test_simplify_file_content_failure(refiner, mock_deps):
    # Simulate LLM error
    mock_deps["llm_client"].chat.side_effect = Exception("LLM Down")

    result = await refiner.simplify_file_content("test.py", "content")

    assert result is None
    mock_deps["logger"].error.assert_called()
