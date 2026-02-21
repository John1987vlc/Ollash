import pytest
from unittest.mock import MagicMock, patch
from backend.utils.domains.auto_generation.structure_generator import StructureGenerator


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
def generator(mock_llm_client, mock_logger, mock_parser):
    with patch("backend.core.config.get_config") as mock_cfg:
        # Mock config to avoid real loading
        mock_cfg.return_value.TOOL_SETTINGS.max_depth = 2
        return StructureGenerator(llm_client=mock_llm_client, logger=mock_logger, response_parser=mock_parser)


class TestStructureGenerator:
    """Test suite for Phase 2: Structure Generation."""

    def test_generate_success(self, generator, mock_llm_client, mock_parser):
        # 1. Start with create_fallback_structure (default)
        # 2. _recursively_generate_sub_structure called for root

        mock_structure = {"folders": [{"name": "src", "files": ["main.py"]}], "files": ["README.md"]}
        mock_parser.extract_json.return_value = {"folders": [], "files": ["main.py"]}

        mock_llm_client.chat.return_value = ({"message": {"content": '{"files": ["main.py"]}'}}, {})

        result = generator.generate("# Readme")

        assert "files" in result
        assert "folders" in result
        assert mock_llm_client.chat.called

    def test_extract_file_paths(self):
        structure = {
            "files": ["root.txt"],
            "folders": [{"name": "src", "files": ["app.py"], "folders": [{"name": "utils", "files": ["helper.py"]}]}],
        }
        paths = StructureGenerator.extract_file_paths(structure)
        # Normalize paths to use forward slashes for the test assertion
        norm_paths = [p.replace("\\", "/") for p in paths]
        assert "root.txt" in norm_paths
        assert "src/app.py" in norm_paths
        assert "src/utils/helper.py" in norm_paths

    def test_create_fallback_structure(self):
        struct = StructureGenerator.create_fallback_structure("# Content")
        assert "path" in struct
        assert len(struct["folders"]) > 0
        assert "README.md" in struct["files"]
