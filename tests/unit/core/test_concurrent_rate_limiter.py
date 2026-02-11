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

    def test_singleton_instance(self, mock_logger):
        """Test that tracker is a singleton."""
        tracker1 = GlobalGPUResourceTracker.get_instance(
            gpu_memory_mb=8000,
            logger=mock_logger,
        )
        tracker2 = GlobalGPUResourceTracker.get_instance(
            gpu_memory_mb=8000,
            logger=mock_logger,
        )
        
        assert tracker1 is tracker2

    def test_acquire_gpu_slot(self, mock_logger):
        """Test acquiring GPU slot."""
        tracker = GlobalGPUResourceTracker.get_instance(
            gpu_memory_mb=8000,
            max_concurrent=2,
            logger=mock_logger,
        )
        
        # Reset tracker
        tracker.active_slots.clear()
        
        # Should acquire slot
        acquired = tracker.acquire_gpu_slot(timeout=1.0)
        assert acquired is True
        assert len(tracker.active_slots) == 1

    def test_release_gpu_resources(self, mock_logger):
        """Test releasing GPU resources."""
        tracker = GlobalGPUResourceTracker.get_instance(
            gpu_memory_mb=8000,
            logger=mock_logger,
        )
        
        # Reset
        tracker.active_slots.clear()
        
        # Acquire and release
        tracker.acquire_gpu_slot(timeout=1.0)
        initial_slots = len(tracker.active_slots)
        
        tracker.release_gpu_resources()
        final_slots = len(tracker.active_slots)
        
        assert final_slots < initial_slots

    def test_max_concurrent_limit(self, mock_logger):
        """Test that max concurrent limit is respected."""
        tracker = GlobalGPUResourceTracker.get_instance(
            gpu_memory_mb=8000,
            max_concurrent=1,
            logger=mock_logger,
        )
        
        # Reset
        tracker.active_slots.clear()
        
        # Acquire first slot
        tracker.acquire_gpu_slot(timeout=0.1)
        
        # Try to acquire second slot (should timeout)
        acquired = tracker.acquire_gpu_slot(timeout=0.1)
        assert acquired is False  # Would timeout or fail


class TestConcurrentGPUAwareRateLimiter:
    """Test ConcurrentGPUAwareRateLimiter."""

    def test_initialization(self, mock_logger):
        """Test limiter initialization."""
        limiter = ConcurrentGPUAwareRateLimiter(
            logger=mock_logger,
            gpu_memory_mb=8000,
            max_concurrent_requests=3,
        )
        
        assert limiter is not None
        assert limiter.max_concurrent_requests == 3

    def test_get_gpu_status(self, mock_logger):
        """Test getting GPU status."""
        limiter = ConcurrentGPUAwareRateLimiter(
            logger=mock_logger,
            gpu_memory_mb=8000,
            max_concurrent_requests=3,
        )
        
        status = limiter.get_gpu_status()
        
        assert "available_concurrent_slots" in status
        assert "total_gpu_memory_mb" in status
        assert status["total_gpu_memory_mb"] == 8000

    def test_wait_if_needed(self, mock_logger):
        """Test rate limiting with wait_if_needed."""
        limiter = ConcurrentGPUAwareRateLimiter(
            logger=mock_logger,
            gpu_memory_mb=8000,
            max_concurrent_requests=10,
            tokens_per_minute=1000,
            requests_per_minute=60,
        )
        
        # Should not wait if under limits
        start = time.time()
        limiter.wait_if_needed(tokens=100)
        elapsed = time.time() - start
        
        # Should return quickly
        assert elapsed < 1.0


class TestSessionResourceManager:
    """Test SessionResourceManager."""

    def test_get_limiter(self, mock_logger):
        """Test getting a limiter for a session."""
        manager = SessionResourceManager(
            logger=mock_logger,
            rate_limiter_config={
                "gpu_memory_mb": 8000,
                "max_concurrent_requests": 3,
            },
        )
        
        limiter1 = manager.get_limiter("session_1")
        limiter2 = manager.get_limiter("session_1")
        
        # Should return same limiter for same session
        assert limiter1 is limiter2

    def test_different_sessions(self, mock_logger):
        """Test that different sessions get different limiters."""
        manager = SessionResourceManager(
            logger=mock_logger,
            rate_limiter_config={
                "gpu_memory_mb": 8000,
                "max_concurrent_requests": 3,
            },
        )
        
        limiter1 = manager.get_limiter("session_1")
        limiter2 = manager.get_limiter("session_2")
        
        # Should be different limiters
        assert limiter1 is not limiter2

    def test_cleanup_session(self, mock_logger):
        """Test cleaning up a session."""
        manager = SessionResourceManager(
            logger=mock_logger,
            rate_limiter_config={
                "gpu_memory_mb": 8000,
                "max_concurrent_requests": 3,
            },
        )
        
        limiter = manager.get_limiter("session_cleanup")
        
        # Should exist before cleanup
        assert "session_cleanup" in manager.limiters
        
        # Cleanup
        manager.cleanup_session("session_cleanup")
        
        # Should be removed
        assert "session_cleanup" not in manager.limiters

    def test_thread_safety(self, mock_logger):
        """Test that session manager is thread-safe."""
        manager = SessionResourceManager(
            logger=mock_logger,
            rate_limiter_config={
                "gpu_memory_mb": 8000,
                "max_concurrent_requests": 3,
            },
        )
        
        results = []
        
        def get_limiters(session_id):
            """Get multiple limiters for a session."""
            for _ in range(5):
                limiter = manager.get_limiter(session_id)
                results.append(limiter)
        
        threads = []
        for i in range(3):
            t = threading.Thread(target=get_limiters, args=(f"session_{i}",))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have created 3 sessions with 5 limiters each
        assert len(results) == 15
        
        # Should have 3 unique sessions
        assert len(manager.limiters) == 3
