"""Concurrent GPU-aware rate limiter with global state management.

Ensures safe resource sharing when multiple agents or chat sessions
compete for GPU/Ollama resources simultaneously.

Design: Singleton pattern with threading locks for global state.
Benefit: Prevents OOM errors and resource contention across agents.
"""

import time
import threading
from collections import deque
from typing import Optional
from pathlib import Path

from backend.utils.core.agent_logger import AgentLogger


class GlobalGPUResourceTracker:
    """Singleton tracking GPU memory and inference queue globally."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._state_lock = threading.RLock()
        
        # GPU state
        self._estimated_gpu_memory_mb = 8000  # Default for typical GPUs
        self._used_gpu_memory_mb = 0
        self._max_concurrent_requests = 3  # Max parallel inferences
        self._active_requests = 0
        self._request_queue = deque()
        
        # Token tracking across all agents
        self._tokens_per_minute_global = 0
        self._tokens_check_timestamp = time.time()
        self._max_tokens_per_minute = 100000

    def acquire_gpu_slot(
        self,
        estimated_memory_mb: int,
        timeout_seconds: float = 30.0,
    ) -> bool:
        """Attempt to acquire a GPU inference slot.
        
        Args:
            estimated_memory_mb: Estimated memory for this inference
            timeout_seconds: Max time to wait for availability
            
        Returns:
            True if slot acquired, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            with self._state_lock:
                if (
                    self._active_requests < self._max_concurrent_requests
                    and self._used_gpu_memory_mb + estimated_memory_mb
                    <= self._estimated_gpu_memory_mb
                ):
                    self._active_requests += 1
                    self._used_gpu_memory_mb += estimated_memory_mb
                    return True
            
            # Wait before retrying
            time.sleep(0.5)
        
        return False  # Timeout

    def release_gpu_slot(self, memory_mb: int):
        """Release GPU slot and memory."""
        with self._state_lock:
            if self._active_requests > 0:
                self._active_requests -= 1
            self._used_gpu_memory_mb = max(0, self._used_gpu_memory_mb - memory_mb)

    def get_gpu_status(self) -> dict:
        """Get current GPU resource status."""
        with self._state_lock:
            return {
                "active_requests": self._active_requests,
                "max_concurrent": self._max_concurrent_requests,
                "used_memory_mb": self._used_gpu_memory_mb,
                "total_memory_mb": self._estimated_gpu_memory_mb,
                "memory_utilization_percent": (
                    100 * self._used_gpu_memory_mb / self._estimated_gpu_memory_mb
                ),
            }

    def record_token_usage(self, tokens: int):
        """Record token usage for rate limiting."""
        with self._state_lock:
            now = time.time()
            if now - self._tokens_check_timestamp > 60:
                self._tokens_per_minute_global = 0
                self._tokens_check_timestamp = now
            self._tokens_per_minute_global += tokens

    def can_process_tokens(self, tokens: int) -> bool:
        """Check if adding tokens would exceed RPM limit."""
        with self._state_lock:
            return (
                self._tokens_per_minute_global + tokens
                <= self._max_tokens_per_minute
            )


class ConcurrentGPUAwareRateLimiter:
    """Thread-safe rate limiter with GPU awareness."""

    def __init__(
        self,
        logger: AgentLogger,
        requests_per_minute: int = 60,
        tokens_per_minute: int = 100000,
        gpu_aware: bool = True,
    ):
        self.logger = logger
        self.rpm = requests_per_minute
        self.tpm = tokens_per_minute
        self.gpu_aware = gpu_aware
        
        self._lock = threading.RLock()
        self._request_timestamps = deque()
        self._token_usage = deque()
        
        # Global GPU tracker (shared across all rate limiters)
        self._gpu_tracker = GlobalGPUResourceTracker() if gpu_aware else None

    def wait_if_needed(
        self,
        estimated_tokens: int = 100,
        estimated_gpu_memory_mb: int = 500,
    ) -> bool:
        """Block until request is allowed under rate limits.
        
        Args:
            estimated_tokens: Estimated tokens for this request
            estimated_gpu_memory_mb: Estimated GPU memory needed
            
        Returns:
            True if wait succeeded, False if resource not available
        """
        with self._lock:
            now = time.time()

            # Check request rate limit
            while self._request_timestamps and now - self._request_timestamps[0] > 60:
                self._request_timestamps.popleft()

            if len(self._request_timestamps) >= self.rpm:
                sleep_time = 60 - (now - self._request_timestamps[0])
                if sleep_time > 0:
                    self.logger.debug(f"Rate limit: sleeping {sleep_time:.1f}s")
                    time.sleep(sleep_time)
                    now = time.time()

            # Check token rate limit
            while self._token_usage and now - self._token_usage[0][0] > 60:
                self._token_usage.popleft()

            current_tokens = sum(tokens for _, tokens in self._token_usage)
            if current_tokens + estimated_tokens > self.tpm:
                self.logger.warning(
                    f"Token rate limit exceeded: {current_tokens}/{self.tpm} tokens/min"
                )
                return False

            # GPU awareness
            if self.gpu_aware and self._gpu_tracker:
                if not self._gpu_tracker.acquire_gpu_slot(
                    estimated_gpu_memory_mb, timeout_seconds=10.0
                ):
                    self.logger.warning(
                        f"GPU resources unavailable: {estimated_gpu_memory_mb}MB requested"
                    )
                    return False
                
                # Record for later release
                self._last_gpu_memory = estimated_gpu_memory_mb

            self._request_timestamps.append(now)
            self._token_usage.append((now, estimated_tokens))
            
            if self.gpu_aware and self._gpu_tracker:
                status = self._gpu_tracker.get_gpu_status()
                self.logger.debug(f"GPU status after request: {status}")

            return True

    def release_gpu_resources(self):
        """Release GPU resources after inference completes."""
        if self.gpu_aware and self._gpu_tracker and hasattr(self, "_last_gpu_memory"):
            self._gpu_tracker.release_gpu_slot(self._last_gpu_memory)

    def get_status(self) -> dict:
        """Get rate limiter status."""
        with self._lock:
            now = time.time()
            active_requests = sum(1 for ts in self._request_timestamps if now - ts < 60)
            active_tokens = sum(tokens for ts, tokens in self._token_usage if now - ts < 60)
            
            status = {
                "requests_per_minute": active_requests,
                "max_rpm": self.rpm,
                "tokens_per_minute": active_tokens,
                "max_tpm": self.tpm,
                "rpm_utilization_percent": 100 * active_requests / self.rpm,
                "tpm_utilization_percent": 100 * active_tokens / self.tpm,
            }
            
            if self.gpu_aware and self._gpu_tracker:
                status["gpu"] = self._gpu_tracker.get_gpu_status()
            
            return status


class SessionResourceManager:
    """Manages resource allocation per chat session/agent."""

    _sessions = {}  # Map session_id -> limiter
    _sessions_lock = threading.Lock()

    @classmethod
    def get_or_create_limiter(
        cls,
        session_id: str,
        logger: AgentLogger,
    ) -> ConcurrentGPUAwareRateLimiter:
        """Get or create a rate limiter for a session."""
        with cls._sessions_lock:
            if session_id not in cls._sessions:
                cls._sessions[session_id] = ConcurrentGPUAwareRateLimiter(
                    logger=logger, gpu_aware=True
                )
            return cls._sessions[session_id]

    @classmethod
    def cleanup_session(cls, session_id: str):
        """Clean up resources for a session."""
        with cls._sessions_lock:
            if session_id in cls._sessions:
                limiter = cls._sessions[session_id]
                limiter.release_gpu_resources()
                del cls._sessions[session_id]

    @classmethod
    def get_all_sessions_status(cls) -> dict:
        """Get status of all active sessions."""
        with cls._sessions_lock:
            return {
                sid: limiter.get_status()
                for sid, limiter in cls._sessions.items()
            }
