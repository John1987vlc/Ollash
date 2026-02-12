"""Unit tests for ConcurrentGPUAwareRateLimiter module."""

import pytest
import threading
import time
from unittest.mock import MagicMock

from src.utils.core.concurrent_rate_limiter import (
    GlobalGPUResourceTracker,
    ConcurrentGPUAwareRateLimiter,
    SessionResourceManager,
)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock()


class TestGlobalGPUResourceTracker:
    """Test GlobalGPUResourceTracker singleton."""

    def test_singleton_instance(self):
        """Test that tracker is a singleton."""
        tracker1 = GlobalGPUResourceTracker()
        tracker2 = GlobalGPUResourceTracker()
        
        assert tracker1 is tracker2

    def test_acquire_gpu_slot(self):
        """Test acquiring GPU slot."""
        tracker = GlobalGPUResourceTracker()
        
        # Reset tracker
        tracker._active_requests = 0
        tracker._used_gpu_memory_mb = 0
        
        # Should acquire slot
        acquired = tracker.acquire_gpu_slot(estimated_memory_mb=1000, timeout_seconds=1.0)
        assert acquired is True
        assert tracker._active_requests == 1
        assert tracker._used_gpu_memory_mb == 1000

    def test_release_gpu_resources(self):
        """Test releasing GPU resources."""
        tracker = GlobalGPUResourceTracker()
        
        # Reset
        tracker._active_requests = 0
        tracker._used_gpu_memory_mb = 0
        
        # Acquire and release
        tracker.acquire_gpu_slot(estimated_memory_mb=1000, timeout_seconds=1.0)
        
        tracker.release_gpu_slot(memory_mb=1000)
        
        assert tracker._active_requests == 0
        assert tracker._used_gpu_memory_mb == 0

    def test_max_concurrent_limit(self):
        """Test that max concurrent limit is respected."""
        tracker = GlobalGPUResourceTracker()
        
        # Reset
        tracker._active_requests = 0
        tracker._used_gpu_memory_mb = 0
        tracker._max_concurrent_requests = 1
        
        # Acquire first slot
        tracker.acquire_gpu_slot(estimated_memory_mb=1000, timeout_seconds=0.1)
        
        # Try to acquire second slot (should timeout)
        acquired = tracker.acquire_gpu_slot(estimated_memory_mb=1000, timeout_seconds=0.1)
        assert acquired is False


class TestConcurrentGPUAwareRateLimiter:
    """Test ConcurrentGPUAwareRateLimiter."""

    def test_initialization(self, mock_logger):
        """Test limiter initialization."""
        limiter = ConcurrentGPUAwareRateLimiter(
            logger=mock_logger,
        )
        
        assert limiter is not None
        assert limiter.gpu_aware is True

    def test_get_gpu_status(self, mock_logger):
        """Test getting GPU status."""
        limiter = ConcurrentGPUAwareRateLimiter(
            logger=mock_logger,
        )
        
        status = limiter.get_status()
        
        assert "gpu" in status
        assert "active_requests" in status["gpu"]

    def test_wait_if_needed(self, mock_logger):
        """Test rate limiting with wait_if_needed."""
        # Reset the tracker
        tracker = GlobalGPUResourceTracker()
        tracker._active_requests = 0
        tracker._used_gpu_memory_mb = 0

        limiter = ConcurrentGPUAwareRateLimiter(
            logger=mock_logger,
            requests_per_minute=60,
            tokens_per_minute=1000,
        )
        
        # Should not wait if under limits
        start = time.time()
        limiter.wait_if_needed(estimated_tokens=100, estimated_gpu_memory_mb=500)
        elapsed = time.time() - start
        
        # Should return quickly
        assert elapsed < 1.0


class TestSessionResourceManager:
    """Test SessionResourceManager."""

    def test_get_limiter(self, mock_logger):
        """Test getting a limiter for a session."""
        manager = SessionResourceManager()
        
        limiter1 = manager.get_or_create_limiter("session_1", mock_logger)
        limiter2 = manager.get_or_create_limiter("session_1", mock_logger)
        
        # Should return same limiter for same session
        assert limiter1 is limiter2

    def test_different_sessions(self, mock_logger):
        """Test that different sessions get different limiters."""
        manager = SessionResourceManager()
        
        limiter1 = manager.get_or_create_limiter("session_1", mock_logger)
        limiter2 = manager.get_or_create_limiter("session_2", mock_logger)
        
        # Should be different limiters
        assert limiter1 is not limiter2

    def test_cleanup_session(self, mock_logger):
        """Test cleaning up a session."""
        manager = SessionResourceManager()
        
        limiter = manager.get_or_create_limiter("session_cleanup", mock_logger)
        
        # Should exist before cleanup
        assert "session_cleanup" in manager._sessions
        
        # Cleanup
        manager.cleanup_session("session_cleanup")
        
        # Should be removed
        assert "session_cleanup" not in manager._sessions

    def test_thread_safety(self, mock_logger):
        """Test that session manager is thread-safe."""
        manager = SessionResourceManager()
        
        results = []
        
        def get_limiters(session_id):
            """Get multiple limiters for a session."""
            for _ in range(5):
                limiter = manager.get_or_create_limiter(session_id, mock_logger)
                results.append(limiter)
        
        threads = []
        for i in range(3):
            t = threading.Thread(target=get_limiters, args=(f"session_{i}",))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have created 3 sessions
        assert len(manager._sessions) == 3
        # Should have 15 results in total
        assert len(results) == 15
        # All limiters for a given session should be the same
        assert results[0] is results[1]
        assert results[5] is not results[0]
