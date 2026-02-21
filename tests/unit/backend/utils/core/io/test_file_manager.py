import pytest
from backend.utils.core.io.file_manager import FileManager


@pytest.fixture
def file_manager(tmp_path):
    return FileManager(root_path=str(tmp_path))


class TestFileManager:
    """Test suite for FileManager filesystem operations."""

    def test_write_and_read_file(self, file_manager, tmp_path):
        file_path = "test.txt"
        content = "Hello Ollash"

        result = file_manager.write_file(file_path, content)
        assert "Escrito" in result

        # Verify physically
        assert (tmp_path / file_path).read_text() == content

        # Read back
        read_content = file_manager.read_file(file_path)
        assert read_content == content

    def test_read_file_not_found(self, file_manager):
        with pytest.raises(FileNotFoundError):
            file_manager.read_file("non_existent.txt")

    def test_create_directory(self, file_manager, tmp_path):
        dir_path = "sub/dir"
        result = file_manager.create_directory(dir_path)
        assert "creado" in result
        assert (tmp_path / dir_path).is_dir()

    def test_list_directory(self, file_manager, tmp_path):
        (tmp_path / "file1.txt").write_text("1")
        (tmp_path / "file2.txt").write_text("2")
        (tmp_path / "subdir").mkdir()

        items = file_manager.list_directory(".")
        assert len(items) == 3
        assert "file1.txt" in items
        assert "subdir" in items

    def test_find_files(self, file_manager, tmp_path):
        (tmp_path / "test.py").write_text("")
        (tmp_path / "other.txt").write_text("")

        files = file_manager.find_files("*.py")
        assert len(files) == 1
        assert "test.py" in files[0]

    def test_delete_file(self, file_manager, tmp_path):
        f = tmp_path / "delete_me.txt"
        f.write_text("bye")

        file_manager.delete_file("delete_me.txt")
        assert not f.exists()

    def test_delete_directory(self, file_manager, tmp_path):
        d = tmp_path / "delete_dir"
        d.mkdir()
        (d / "inner.txt").write_text("inside")

        file_manager.delete_file("delete_dir")
        assert not d.exists()

    def test_get_file_info(self, file_manager, tmp_path):
        f = tmp_path / "info.txt"
        f.write_text("some content")

        info = file_manager.get_file_info("info.txt")
        assert info["nombre"] == "info.txt"
        assert info["tamaño"] == len("some content")
        assert info["es_archivo"] is True

    def test_get_file_info_error(self, file_manager):
        info = file_manager.get_file_info("missing")
        assert "error" in info
