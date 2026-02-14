"""GPU-aware adaptive rate limiter for Ollama API requests.

Tracks response times and automatically reduces effective RPM
when GPU is overloaded (slow responses), recovering when performance improves.
"""

import threading
import time
from collections import deque
from typing import Optional


class GPUAwareRateLimiter:
    """Adaptive rate limiter that tracks Ollama response times.

    When response times degrade beyond a threshold, automatically
    reduces effective RPM to reduce GPU contention. Uses exponential
    moving average (EMA) of response times for smooth adjustments.
    """

    def __init__(
        self,
        base_rpm: int = 60,
        tokens_per_minute: int = 100000,
        response_time_window: int = 10,
        degradation_threshold_ms: float = 5000.0,
        recovery_threshold_ms: float = 2000.0,
        min_rpm: int = 5,
        ema_alpha: float = 0.3,
        logger=None,
    ):
        self.base_rpm = base_rpm
        self.effective_rpm = base_rpm
        self.tpm = tokens_per_minute
        self.min_rpm = min_rpm
        self.degradation_threshold = degradation_threshold_ms
        self.recovery_threshold = recovery_threshold_ms
        self.ema_alpha = ema_alpha
        self.logger = logger

        self._request_timestamps: deque = deque()
        self._token_usage: deque = deque()
        self._response_times: deque = deque(maxlen=response_time_window)
        self._ema_response_time: float = 0.0
        self._lock = threading.Lock()

    def wait_if_needed(self) -> None:
        """Blocks until a request is allowed, using effective_rpm."""
        with self._lock:
            now = time.monotonic()
            while self._request_timestamps and now - self._request_timestamps[0] > 60:
                self._request_timestamps.popleft()
            if len(self._request_timestamps) >= self.effective_rpm:
                sleep_time = 60 - (now - self._request_timestamps[0])
                if sleep_time > 0:
                    if self.logger:
                        self.logger.debug(
                            f"Rate limiter: sleeping {sleep_time:.1f}s "
                            f"(effective_rpm={self.effective_rpm})"
                        )
                    self._lock.release()
                    time.sleep(sleep_time)
                    self._lock.acquire()
            self._request_timestamps.append(time.monotonic())

    def record_response_time(self, elapsed_ms: float) -> None:
        """Records a response time and adjusts effective RPM."""
        with self._lock:
            self._response_times.append(elapsed_ms)

            if self._ema_response_time == 0.0:
                self._ema_response_time = elapsed_ms
            else:
                self._ema_response_time = (
                    self.ema_alpha * elapsed_ms
                    + (1 - self.ema_alpha) * self._ema_response_time
                )

            self._adjust_rpm()

    def record_tokens(self, token_count: int) -> None:
        """Records token usage for rate tracking."""
        now = time.monotonic()
        with self._lock:
            while self._token_usage and now - self._token_usage[0][0] > 60:
                self._token_usage.popleft()
            self._token_usage.append((now, token_count))

    def _adjust_rpm(self) -> None:
        """Adjusts effective_rpm based on EMA of response times.

        Called with self._lock already held.
        """
        old_rpm = self.effective_rpm

        if self._ema_response_time > self.degradation_threshold:
            # Reduce RPM by 25% (floor at min_rpm)
            self.effective_rpm = max(
                self.min_rpm,
                int(self.effective_rpm * 0.75),
            )
        elif self._ema_response_time < self.recovery_threshold:
            # Recover RPM by 10% (cap at base_rpm)
            self.effective_rpm = min(
                self.base_rpm,
                int(self.effective_rpm * 1.10) + 1,
            )

        if old_rpm != self.effective_rpm and self.logger:
            self.logger.info(
                f"GPU-aware rate limiter adjusted: {old_rpm} → {self.effective_rpm} RPM "
                f"(EMA response time: {self._ema_response_time:.0f}ms)"
            )

    def get_health_metrics(self) -> dict:
        """Returns current health metrics for monitoring."""
        with self._lock:
            status = "normal"
            if self.effective_rpm < self.base_rpm * 0.5:
                status = "degraded"
            elif self.effective_rpm < self.base_rpm:
                status = "throttled"

            return {
                "effective_rpm": self.effective_rpm,
                "base_rpm": self.base_rpm,
                "ema_response_time_ms": round(self._ema_response_time, 1),
                "recent_response_times": list(self._response_times),
                "status": status,
            }
