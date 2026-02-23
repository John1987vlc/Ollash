import pytest
from unittest.mock import MagicMock
from backend.utils.domains.auto_generation.structure_generator import StructureGenerator

@pytest.fixture
def struct_gen():
    return StructureGenerator(MagicMock(), MagicMock(), MagicMock())

def test_extract_file_paths(struct_gen):
    structure = {
        "files": ["root.txt"],
        "folders": [
            {
                "name": "src",
                "files": ["app.py"],
                "folders": [{"name": "utils", "files": ["helper.py"]}]
            }
        ]
    }
    paths = struct_gen.extract_file_paths(structure)
    assert "root.txt" in paths
    assert "src/app.py" in paths
    assert "src/utils/helper.py" in paths

def test_create_fallback_structure(struct_gen):
    fallback = struct_gen.create_fallback_structure("readme", template_name="default")
    assert "src" in [f["name"] for f in fallback["folders"]]
    assert "README.md" in fallback["files"]
