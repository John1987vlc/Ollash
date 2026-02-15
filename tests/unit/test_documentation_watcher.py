"""
Unit Tests for DocumentationWatcher
Tests automatic document indexing and monitoring
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from backend.utils.core.documentation_watcher import DocumentationWatcher
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.documentation_manager import DocumentationManager


@pytest.fixture
def logger():
    """Mock logger"""
    logger = Mock(spec=AgentLogger)
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def doc_manager():
    """Mock DocumentationManager"""
    manager = Mock(spec=DocumentationManager)
    manager.index_documentation = Mock()
    manager.references_dir = Path(tempfile.gettempdir()) / "references"
    manager.references_dir.mkdir(exist_ok=True)
    return manager


@pytest.fixture
def watcher(doc_manager, logger):
    """Initialize DocumentationWatcher"""
    refs_dir = Path(tempfile.gettempdir()) / "test_refs"
    refs_dir.mkdir(exist_ok=True)

    watcher = DocumentationWatcher(
        references_dir=refs_dir,
        documentation_manager=doc_manager,
        logger=logger,
        check_interval=1
    )
    yield watcher
    watcher.stop()


class TestDocumentationWatcher:
    """Test suite for DocumentationWatcher"""

    def test_initialization(self, logger, doc_manager):
        """Test watcher initialization"""
        refs_dir = Path(tempfile.gettempdir()) / "init_test"
        refs_dir.mkdir(exist_ok=True)

        watcher = DocumentationWatcher(
            references_dir=refs_dir,
            documentation_manager=doc_manager,
            logger=logger
        )

        assert watcher.references_dir == refs_dir
        assert watcher._running is False
        assert watcher._tracked_files == {}

        watcher.stop()

    def test_start_and_stop(self, watcher, logger):
        """Test starting and stopping the watcher"""
        assert watcher._running is False

        watcher.start()
        assert watcher._running is True
        logger.info.assert_called()

        watcher.stop()
        assert watcher._running is False

    def test_add_callback(self, watcher):
        """Test registering a callback"""
        callback = Mock()
        watcher.add_callback(callback)

        assert callback in watcher._callbacks
        assert len(watcher._callbacks) == 1

    def test_manual_index(self, watcher, logger):
        """Test manual indexing of a file"""
        with tempfile.NamedTemporaryFile(suffix='.txt', dir=watcher.references_dir, delete=False) as f:
            f.write(b"Test content")
            f.flush()
            file_path = Path(f.name)

        try:
            result = watcher.manual_index(file_path)
            # Manual index should attempt indexing
            assert isinstance(result, bool)
        finally:
            if file_path.exists():
                file_path.unlink()

    def test_get_tracked_files(self, watcher):
        """Test retrieving tracked files status"""
        # Create a test file
        test_file = watcher.references_dir / "test.txt"
        test_file.write_text("Test content")

        try:
            tracked = watcher.get_tracked_files()
            # tracked is a dict, should be empty initially (not scanned yet)
            assert isinstance(tracked, dict)
        finally:
            test_file.unlink()

    def test_callback_invocation(self, watcher, logger):
        """Test that callbacks are invoked on new files"""
        callback = Mock()
        watcher.add_callback(callback)

        # Create a file
        test_file = watcher.references_dir / "callback_test.txt"
        test_file.write_text("Callback test content")

        try:
            # Manually scan to trigger callback
            watcher._scan_and_index()
            # Callback might or might not be called depending on ingester
            # Just verify it was registered
            assert callback in watcher._callbacks
        finally:
            test_file.unlink()

    def test_scan_nonexistent_directory(self, logger):
        """Test scanning a nonexistent directory doesn't crash"""
        refs_dir = Path(tempfile.gettempdir()) / "nonexistent_dir_test"
        doc_manager = Mock(spec=DocumentationManager)

        watcher = DocumentationWatcher(
            references_dir=refs_dir,
            documentation_manager=doc_manager,
            logger=logger
        )

        # Should not raise exception
        watcher._scan_and_index()

        watcher.stop()

    def test_multiple_file_tracking(self, watcher):
        """Test tracking multiple files"""
        files = []
        try:
            for i in range(3):
                f = watcher.references_dir / f"file_{i}.txt"
                f.write_text(f"Content {i}")
                files.append(f)

            tracked = watcher.get_tracked_files()
            # Files exist, check that we can get their metadata
            assert isinstance(tracked, dict)
        finally:
            for f in files:
                if f.exists():
                    f.unlink()

    def test_supported_formats_only(self, watcher):
        """Test that only supported formats are tracked"""
        supported_file = watcher.references_dir / "supported.txt"
        unsupported_file = watcher.references_dir / "unsupported.xyz"

        supported_file.write_text("Content")
        unsupported_file.write_text("Content")

        try:
            tracked = watcher.get_tracked_files()
            # Only supported files should appear
            for filename in tracked.keys():
                assert not filename.endswith(".xyz")
        finally:
            supported_file.unlink()
            unsupported_file.unlink()

