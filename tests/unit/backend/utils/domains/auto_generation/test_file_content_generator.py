import warnings

import pytest
from unittest.mock import MagicMock

# FileContentGenerator is deprecated — suppress the warning in this legacy test module
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from backend.utils.domains.auto_generation.file_content_generator import FileContentGenerator


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
def mock_doc_manager():
    return MagicMock()


@pytest.fixture
def generator(mock_llm_client, mock_logger, mock_parser, mock_doc_manager):
    return FileContentGenerator(
        llm_client=mock_llm_client,
        logger=mock_logger,
        response_parser=mock_parser,
        documentation_manager=mock_doc_manager,
    )


class TestFileContentGenerator:
    """Test suite for Phase 4: File Content Generation."""

    async def test_generate_file_success(self, generator, mock_llm_client, mock_parser, mock_doc_manager):
        mock_doc_manager.query_documentation.return_value = []
        mock_llm_client.chat.return_value = ({"message": {"content": "print('hello')"}}, {})
        mock_parser.extract_raw_content.return_value = "print('hello')"

        result = await generator.generate_file(
            file_path="src/main.py", readme_content="# Title", json_structure={}, related_files={}
        )

        assert result == "print('hello')"
        mock_llm_client.chat.assert_called_once()

    async def test_generate_json_file_validation(self, generator, mock_llm_client, mock_parser, mock_doc_manager):
        mock_doc_manager.query_documentation.return_value = []
        # LLM returns invalid JSON first
        mock_llm_client.chat.side_effect = [
            ({"message": {"content": "not json"}}, {}),
            ({"message": {"content": '{"ok": true}'}}, {}),
        ]
        mock_parser.extract_raw_content.side_effect = ["not json", '{"ok": true}']

        result = await generator.generate_file(
            file_path="config.json", readme_content="# Title", json_structure={}, related_files={}, max_retries=2
        )

        assert result == '{"ok": true}'
        assert mock_llm_client.chat.call_count == 2

    async def test_generate_file_failure_after_retries(self, generator, mock_llm_client, mock_parser, mock_doc_manager):
        mock_doc_manager.query_documentation.return_value = []
        mock_llm_client.chat.return_value = ({"message": {"content": ""}}, {})
        mock_parser.extract_raw_content.return_value = ""

        result = await generator.generate_file(
            file_path="fail.py", readme_content="# Readme", json_structure={}, related_files={}, max_retries=2
        )

        assert result == ""
        assert mock_llm_client.chat.call_count == 2
