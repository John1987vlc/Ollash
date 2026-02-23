"""Unit tests for LockedFileManager (E8)."""

import threading
import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.unit
class TestLockedFileManager:
    """Tests for thread-safe and asyncio-safe file locking."""

    @pytest.fixture
    def mock_logger(self):
        return MagicMock()

    @pytest.fixture
    def manager(self, tmp_path, mock_logger):
        from backend.utils.core.io.locked_file_manager import LockedFileManager

        return LockedFileManager(root_path=str(tmp_path), logger=mock_logger)

    # ------------------------------------------------------------------
    # Basic write
    # ------------------------------------------------------------------

    def test_write_file_creates_file(self, manager, tmp_path):
        manager.write_file("hello.txt", "world")
        assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "world"

    def test_write_file_returns_success_string(self, manager):
        result = manager.write_file("out.txt", "content")
        assert result is not None

    # ------------------------------------------------------------------
    # Lock identity
    # ------------------------------------------------------------------

    def test_same_path_returns_same_thread_lock(self, manager):
        lock1 = manager._get_thread_lock("src/app.py")
        lock2 = manager._get_thread_lock("src/app.py")
        assert lock1 is lock2

    def test_different_paths_return_different_thread_locks(self, manager):
        lock_a = manager._get_thread_lock("src/a.py")
        lock_b = manager._get_thread_lock("src/b.py")
        assert lock_a is not lock_b

    def test_same_path_returns_same_async_lock(self, manager):
        lock1 = manager._get_async_lock("src/app.py")
        lock2 = manager._get_async_lock("src/app.py")
        assert lock1 is lock2

    def test_different_paths_return_different_async_locks(self, manager):
        lock_a = manager._get_async_lock("src/a.py")
        lock_b = manager._get_async_lock("src/b.py")
        assert lock_a is not lock_b

    # ------------------------------------------------------------------
    # Thread safety: 10 concurrent writes to same path
    # ------------------------------------------------------------------

    def test_concurrent_writes_do_not_corrupt_file(self, manager, tmp_path):
        """10 threads writing different content to the same file should not corrupt it."""
        path = "concurrent.txt"
        errors = []

        def write_worker(thread_id: int):
            try:
                manager.write_file(path, f"thread-{thread_id}\n")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=write_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Threads raised errors: {errors}"
        # File must exist and contain valid content (one of the thread outputs)
        content = (tmp_path / path).read_text(encoding="utf-8")
        assert content.startswith("thread-")

    def test_concurrent_writes_different_paths_all_succeed(self, manager, tmp_path):
        """10 threads writing to 10 different files should all succeed."""
        errors = []

        def write_worker(thread_id: int):
            try:
                manager.write_file(f"file_{thread_id}.txt", f"content-{thread_id}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=write_worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        for i in range(10):
            assert (tmp_path / f"file_{i}.txt").read_text(encoding="utf-8") == f"content-{i}"

    # ------------------------------------------------------------------
    # Async write
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_write_file_async_creates_file(self, manager, tmp_path):
        await manager.write_file_async("async_out.txt", "async content")
        assert (tmp_path / "async_out.txt").read_text(encoding="utf-8") == "async content"

    @pytest.mark.asyncio
    async def test_write_file_async_returns_result(self, manager):
        result = await manager.write_file_async("async_out2.txt", "data")
        assert result is not None

    # ------------------------------------------------------------------
    # Inherits FileManager API (drop-in replacement)
    # ------------------------------------------------------------------

    def test_read_file_works_after_write(self, manager):
        manager.write_file("readable.txt", "hello")
        content = manager.read_file("readable.txt")
        assert content == "hello"
