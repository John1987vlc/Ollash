"""Unit tests for ProjectIngestionService."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.utils.core.io.project_ingestion_service import ProjectIngestionService


@pytest.fixture
def mock_logger():
    return MagicMock()


def make_service(tmp_path, read_fn=None, logger=None):
    """Helper to create a ProjectIngestionService with a logger and optional custom reader."""
    if logger is None:
        logger = MagicMock()
    if read_fn is None:
        def read_fn(path: str) -> str:
            return Path(path).read_text(encoding="utf-8")
    return ProjectIngestionService(file_reader=read_fn, logger=logger)


@pytest.mark.unit
class TestIngest:
    def test_returns_empty_on_nonexistent_path(self, tmp_path, mock_logger):
        svc = make_service(tmp_path, logger=mock_logger)
        files, structure, paths, readme = svc.ingest(tmp_path / "does_not_exist")
        assert files == {}
        assert structure == {}
        assert paths == []
        assert readme == ""
        mock_logger.error.assert_called_once()

    def test_ingests_python_file(self, tmp_path, mock_logger):
        (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")
        svc = make_service(tmp_path, logger=mock_logger)
        files, structure, paths, _ = svc.ingest(tmp_path)
        assert "app.py" in files
        assert files["app.py"] == "print('hello')"
        assert "app.py" in paths

    def test_ignores_binary_extensions(self, tmp_path, mock_logger):
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        svc = make_service(tmp_path, logger=mock_logger)
        files, _, paths, _ = svc.ingest(tmp_path)
        assert "image.png" not in files

    def test_excludes_node_modules(self, tmp_path, mock_logger):
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "package.js").write_text("module.exports = {}", encoding="utf-8")
        svc = make_service(tmp_path, logger=mock_logger)
        files, _, _, _ = svc.ingest(tmp_path)
        assert not any("node_modules" in p for p in files)

    def test_excludes_pycache(self, tmp_path, mock_logger):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "app.pyc").write_bytes(b"bytecode")
        svc = make_service(tmp_path, logger=mock_logger)
        files, _, _, _ = svc.ingest(tmp_path)
        assert not any("__pycache__" in p for p in files)

    def test_readme_not_included_in_files(self, tmp_path, mock_logger):
        (tmp_path / "README.md").write_text("# Project", encoding="utf-8")
        svc = make_service(tmp_path, logger=mock_logger)
        files, _, paths, readme = svc.ingest(tmp_path)
        assert "README.md" not in files
        assert "README.md" not in paths
        assert readme == "# Project"

    def test_multiple_languages(self, tmp_path, mock_logger):
        (tmp_path / "app.py").write_text("pass", encoding="utf-8")
        (tmp_path / "index.js").write_text("const x = 1;", encoding="utf-8")
        svc = make_service(tmp_path, logger=mock_logger)
        files, _, _, _ = svc.ingest(tmp_path)
        assert "app.py" in files
        assert "index.js" in files

    def test_normalises_backslashes_in_paths(self, tmp_path, mock_logger):
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "main.py").write_text("x = 1", encoding="utf-8")
        svc = make_service(tmp_path, logger=mock_logger)
        files, _, paths, _ = svc.ingest(tmp_path)
        for p in paths:
            assert "\\" not in p

    def test_unreadable_file_is_skipped(self, tmp_path, mock_logger):
        (tmp_path / "good.py").write_text("pass", encoding="utf-8")
        (tmp_path / "bad.py").write_text("fail", encoding="utf-8")

        def flaky_reader(path: str) -> str:
            if "bad" in path:
                raise IOError("permission denied")
            return Path(path).read_text(encoding="utf-8")

        svc = make_service(tmp_path, read_fn=flaky_reader, logger=mock_logger)
        files, _, _, _ = svc.ingest(tmp_path)
        assert "good.py" in files
        assert "bad.py" not in files
        mock_logger.warning.assert_called()

    def test_logs_ingestion_count(self, tmp_path, mock_logger):
        (tmp_path / "a.py").write_text("a", encoding="utf-8")
        (tmp_path / "b.py").write_text("b", encoding="utf-8")
        svc = make_service(tmp_path, logger=mock_logger)
        svc.ingest(tmp_path)
        info_msgs = [str(call) for call in mock_logger.info.call_args_list]
        assert any("2" in msg for msg in info_msgs)


@pytest.mark.unit
class TestBuildStructure:
    def test_flat_file_creates_correct_node(self, tmp_path, mock_logger):
        (tmp_path / "app.py").write_text("x", encoding="utf-8")
        svc = make_service(tmp_path, logger=mock_logger)
        _, structure, _, _ = svc.ingest(tmp_path)
        assert "app.py" in structure
        assert structure["app.py"]["type"] == "file"
        assert structure["app.py"]["language"] == "python"
        assert structure["app.py"]["extension"] == ".py"

    def test_nested_file_creates_directory_nodes(self, tmp_path, mock_logger):
        sub = tmp_path / "src" / "utils"
        sub.mkdir(parents=True)
        (sub / "helper.py").write_text("pass", encoding="utf-8")
        svc = make_service(tmp_path, logger=mock_logger)
        _, structure, _, _ = svc.ingest(tmp_path)
        assert "src" in structure
        assert "utils" in structure["src"]
        assert "helper.py" in structure["src"]["utils"]

    def test_empty_project_gives_empty_structure(self, tmp_path, mock_logger):
        svc = make_service(tmp_path, logger=mock_logger)
        _, structure, _, _ = svc.ingest(tmp_path)
        assert structure == {}
