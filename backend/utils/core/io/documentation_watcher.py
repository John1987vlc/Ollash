"""
Watches the Knowledge Workspace and automatically indexes new documents.
Uses file system events to trigger DocumentationManager indexing.
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.io.documentation_manager import DocumentationManager
from backend.utils.core.io.multi_format_ingester import MultiFormatIngester


class DocumentationWatcher:
    """
    Monitors the knowledge_workspace/references directory and automatically
    indexes new documents when they are added.
    """

    def __init__(
        self,
        references_dir: Path,
        documentation_manager: DocumentationManager,
        logger: AgentLogger,
        config: Optional[Dict] = None,
        check_interval: int = 5,  # seconds between filesystem checks
    ):
        self.references_dir = references_dir
        self.doc_manager = documentation_manager
        self.logger = logger
        self.config = config or {}
        self.check_interval = check_interval

        self.ingester = MultiFormatIngester(logger, config)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._tracked_files: Dict[str, float] = {}  # filename -> last_modified
        self._callbacks: list = []  # User-defined callbacks on new docs

    def start(self):
        """Starts the watcher thread."""
        if self._running:
            self.logger.warning("DocumentationWatcher already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        self.logger.info("📁 DocumentationWatcher started")

    def stop(self):
        """Stops the watcher thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.logger.info("📁 DocumentationWatcher stopped")

    def add_callback(self, callback: Callable[[Path, str], None]):
        """
        Register a callback to be invoked when a new document is indexed.
        Signature: callback(file_path: Path, extracted_text: str)
        """
        self._callbacks.append(callback)

    def _watch_loop(self):
        """Main watch loop - runs in separate thread."""
        while self._running:
            try:
                self._scan_and_index()
            except Exception as e:
                self.logger.error(f"Error in DocumentationWatcher: {e}")

            time.sleep(self.check_interval)

    def _scan_and_index(self):
        """Scans references_dir for new/modified files and indexes them."""
        if not self.references_dir.exists():
            return

        for file_path in self.references_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Check if file is supported
            if file_path.suffix.lower() not in self.ingester.SUPPORTED_FORMATS:
                continue

            try:
                current_mtime = file_path.stat().st_mtime
                tracked_mtime = self._tracked_files.get(file_path.name)

                # New file or recently modified
                if tracked_mtime is None or current_mtime > tracked_mtime:
                    self._index_new_file(file_path)
                    self._tracked_files[file_path.name] = current_mtime

            except OSError as e:
                self.logger.debug(f"Could not stat {file_path}: {e}")

    def _index_new_file(self, file_path: Path):
        """Indexes a newly detected file."""
        try:
            # Extract text from file
            extracted_text = self.ingester.ingest_file(file_path)

            if not extracted_text:
                self.logger.warning(f"Could not extract text from {file_path.name}")
                return

            # Index into ChromaDB via DocumentationManager
            self.doc_manager.index_documentation(file_path)

            # Get metadata
            metadata = self.ingester.get_file_metadata(file_path)

            self.logger.info(f"✅ Auto-indexed: {file_path.name} ({metadata.get('word_count', 0)} words)")

            # Invoke user callbacks
            for callback in self._callbacks:
                try:
                    callback(file_path, extracted_text)
                except Exception as e:
                    self.logger.error(f"Callback error: {e}")

        except Exception as e:
            self.logger.error(f"Failed to auto-index {file_path.name}: {e}")

    def get_tracked_files(self) -> Dict[str, Dict]:
        """Returns information about tracked files."""
        result = {}
        for file_path in self.references_dir.rglob("*"):
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() not in self.ingester.SUPPORTED_FORMATS:
                continue

            metadata = self.ingester.get_file_metadata(file_path)
            if metadata:
                result[file_path.name] = {
                    **metadata,
                    "tracked": file_path.name in self._tracked_files,
                    "last_scanned": datetime.now().isoformat(),
                }

        return result

    def manual_index(self, file_path: Path) -> bool:
        """
        Manually trigger indexing of a specific file.
        Returns True if successful.
        """
        if not file_path.exists():
            self.logger.error(f"File not found: {file_path}")
            return False

        try:
            self._index_new_file(file_path)
            return True
        except Exception as e:
            self.logger.error(f"Manual index failed: {e}")
            return False
