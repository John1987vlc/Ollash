"""Unit tests for async methods added to FileManager."""

import asyncio

import pytest

from backend.utils.core.io.file_manager import FileManager


class TestFileManagerAsync:
    @pytest.mark.unit
    def test_write_file_async_delegates_to_sync(self, tmp_path):
        fm = FileManager(root_path=str(tmp_path))

        async def run():
            result = await fm.write_file_async("hello.txt", "world")
            return result

        result = asyncio.run(run())
        assert "hello.txt" in result
        assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "world"

    @pytest.mark.unit
    def test_read_file_async_returns_content(self, tmp_path):
        (tmp_path / "test.txt").write_text("content here", encoding="utf-8")
        fm = FileManager(root_path=str(tmp_path))

        async def run():
            return await fm.read_file_async("test.txt")

        result = asyncio.run(run())
        assert result == "content here"

    @pytest.mark.unit
    def test_read_file_async_raises_on_missing(self, tmp_path):
        fm = FileManager(root_path=str(tmp_path))

        async def run():
            return await fm.read_file_async("nonexistent.txt")

        with pytest.raises(FileNotFoundError):
            asyncio.run(run())

    @pytest.mark.unit
    def test_delete_file_async_removes_file(self, tmp_path):
        target = tmp_path / "to_delete.txt"
        target.write_text("bye", encoding="utf-8")
        fm = FileManager(root_path=str(tmp_path))

        async def run():
            return await fm.delete_file_async("to_delete.txt")

        asyncio.run(run())
        assert not target.exists()

    @pytest.mark.unit
    def test_write_file_async_uses_asyncio_to_thread(self, tmp_path):
        """Verify that asyncio.to_thread is used (non-blocking by design)."""
        fm = FileManager(root_path=str(tmp_path))

        called_with = []

        original_write = fm.write_file

        def tracking_write(path, content):
            called_with.append((path, content))
            return original_write(path, content)

        fm.write_file = tracking_write

        async def run():
            return await fm.write_file_async("trace.txt", "traced")

        asyncio.run(run())
        assert called_with == [("trace.txt", "traced")]
