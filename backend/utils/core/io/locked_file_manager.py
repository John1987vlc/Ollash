"""
Locked File Manager — Thread-safe FileManager with per-path locks.

Extends FileManager with:
- Per-path threading.Lock for synchronous callers (AutomationManager background threads).
- Per-path asyncio.Lock for async coroutine callers (agent phases).

This prevents file corruption when a background automation task and an active
agent phase attempt to write to the same file concurrently.

Drop-in replacement: inherits FileManager so all existing callers are compatible.
"""

import asyncio
import threading
from pathlib import Path
from typing import Dict

from backend.utils.core.io.file_manager import FileManager
from backend.utils.core.system.agent_logger import AgentLogger


class LockedFileManager(FileManager):
    """Thread-safe and asyncio-safe FileManager with per-path locking.

    Two separate lock registries:
    - _async_locks: Dict[str, asyncio.Lock] — for async coroutine callers.
    - _thread_locks: Dict[str, threading.Lock] — for sync/threaded callers.

    The _registry_lock (threading.Lock) protects the dicts themselves so that
    creating a new lock entry is also thread-safe.

    Usage:
        # Sync (thread-safe):
        mgr.write_file("src/app.py", content)

        # Async (asyncio-safe):
        await mgr.write_file_async("src/app.py", content)
    """

    def __init__(self, root_path: str = None, logger: AgentLogger = None):
        super().__init__(root_path=root_path)
        self.logger = logger
        self._async_locks: Dict[str, asyncio.Lock] = {}
        self._thread_locks: Dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lock accessors (thread-safe creation)
    # ------------------------------------------------------------------

    def _get_async_lock(self, path: str) -> asyncio.Lock:
        """Return (or create) the asyncio.Lock for *path*."""
        normalized = str(Path(path))
        with self._registry_lock:
            if normalized not in self._async_locks:
                self._async_locks[normalized] = asyncio.Lock()
            return self._async_locks[normalized]

    def _get_thread_lock(self, path: str) -> threading.Lock:
        """Return (or create) the threading.Lock for *path*."""
        normalized = str(Path(path))
        with self._registry_lock:
            if normalized not in self._thread_locks:
                self._thread_locks[normalized] = threading.Lock()
            return self._thread_locks[normalized]

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def write_file(self, path: str, content: str) -> str:
        """Thread-safe synchronous file write with per-path locking."""
        lock = self._get_thread_lock(str(path))
        with lock:
            return super().write_file(path, content)

    # ------------------------------------------------------------------
    # Async extension
    # ------------------------------------------------------------------

    async def write_file_async(self, path: str, content: str) -> str:
        """Async-safe file write with per-path asyncio lock.

        Use this method from async contexts (e.g. inside agent phases) to
        prevent concurrent coroutines from writing the same file at the same
        time while avoiding blocking the event loop.

        Args:
            path: Relative or absolute file path.
            content: File content to write.

        Returns:
            Result string from the underlying write_file implementation.
        """
        lock = self._get_async_lock(str(path))
        async with lock:
            # Delegate to the sync implementation (which also holds the thread lock)
            return super().write_file(path, content)
