"""Unit tests for methods added to FileManager (refactored to sync)."""

import pytest

from backend.utils.core.io.file_manager import FileManager


class TestFileManagerSyncRefactored:
    @pytest.mark.unit
    def test_write_file_sync(self, tmp_path):
        fm = FileManager(root_path=str(tmp_path))
        result = fm.write_file("hello.txt", "world")
        assert "hello.txt" in result
        assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "world"

    @pytest.mark.unit
    def test_read_file_sync(self, tmp_path):
        (tmp_path / "test.txt").write_text("content here", encoding="utf-8")
        fm = FileManager(root_path=str(tmp_path))
        result = fm.read_file("test.txt")
        assert result == "content here"

    @pytest.mark.unit
    def test_read_file_sync_raises_on_missing(self, tmp_path):
        fm = FileManager(root_path=str(tmp_path))
        with pytest.raises(FileNotFoundError):
            fm.read_file("nonexistent.txt")

    @pytest.mark.unit
    def test_delete_file_sync(self, tmp_path):
        target = tmp_path / "to_delete.txt"
        target.write_text("bye", encoding="utf-8")
        fm = FileManager(root_path=str(tmp_path))
        fm.delete_file("to_delete.txt")
        assert not target.exists()

    @pytest.mark.unit
    def test_write_file_tracking_sync(self, tmp_path):
        fm = FileManager(root_path=str(tmp_path))
        called_with = []
        original_write = fm.write_file

        def tracking_write(path, content):
            called_with.append((path, content))
            return original_write(path, content)

        fm.write_file = tracking_write
        fm.write_file("trace.txt", "traced")
        assert called_with == [("trace.txt", "traced")]
