"""Centralised exponential-backoff retry utility.

Replaces scattered ad-hoc retry loops across the auto-generation pipeline.
Both synchronous and asynchronous variants are provided.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Tuple, Type

from backend.utils.core.constants import (
    DEFAULT_RETRY_ATTEMPTS,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_RETRY_BASE_DELAY,
    DEFAULT_RETRY_MAX_DELAY,
)


@dataclass
class RetryPolicy:
    """Exponential-backoff retry policy for sync and async callables.

    Parameters
    ----------
    max_attempts:
        Maximum number of total attempts (1 = no retries).
    base_delay:
        Initial wait time in seconds before the first retry.
    max_delay:
        Upper cap on the computed delay.
    backoff_factor:
        Multiplier applied to *base_delay* on each subsequent attempt.
    exceptions:
        Exception types that trigger a retry. Any other exception propagates
        immediately without retrying.

    Examples
    --------
    >>> policy = RetryPolicy(max_attempts=3, base_delay=0.5)
    >>> result = policy.execute(some_function, arg1, kwarg=value)

    >>> result = await policy.aexecute(some_async_function, arg1)
    """

    max_attempts: int = DEFAULT_RETRY_ATTEMPTS
    base_delay: float = DEFAULT_RETRY_BASE_DELAY
    max_delay: float = DEFAULT_RETRY_MAX_DELAY
    backoff_factor: float = DEFAULT_RETRY_BACKOFF
    exceptions: Tuple[Type[BaseException], ...] = field(default_factory=lambda: (Exception,))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _delay_for(self, attempt: int) -> float:
        """Return the sleep duration for a given (0-based) attempt index."""
        return min(self.base_delay * (self.backoff_factor ** attempt), self.max_delay)

    # ------------------------------------------------------------------
    # Synchronous execution
    # ------------------------------------------------------------------

    def execute(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Run *fn* with retry on *exceptions*.

        Parameters
        ----------
        fn:
            Callable to invoke.
        *args / **kwargs:
            Forwarded to *fn* on every attempt.

        Returns
        -------
        The return value of the first successful call.

        Raises
        ------
        The last caught exception once all attempts are exhausted.
        """
        last_exc: BaseException | None = None
        for attempt in range(self.max_attempts):
            try:
                return fn(*args, **kwargs)
            except self.exceptions as exc:  # type: ignore[misc]
                last_exc = exc
                if attempt < self.max_attempts - 1:
                    time.sleep(self._delay_for(attempt))
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Asynchronous execution
    # ------------------------------------------------------------------

    async def aexecute(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Async version of :meth:`execute`.

        Parameters
        ----------
        fn:
            Async callable (coroutine function) to invoke.
        *args / **kwargs:
            Forwarded to *fn* on every attempt.

        Returns
        -------
        The return value of the first successful coroutine call.

        Raises
        ------
        The last caught exception once all attempts are exhausted.
        """
        last_exc: BaseException | None = None
        for attempt in range(self.max_attempts):
            try:
                return await fn(*args, **kwargs)
            except self.exceptions as exc:  # type: ignore[misc]
                last_exc = exc
                if attempt < self.max_attempts - 1:
                    await asyncio.sleep(self._delay_for(attempt))
        raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Convenience factory instances
# ---------------------------------------------------------------------------

#: Default policy matching legacy 3-attempt behaviour (no delay in tests).
DEFAULT_POLICY = RetryPolicy()

#: Aggressive policy for network-bound calls (longer delays).
NETWORK_POLICY = RetryPolicy(
    max_attempts=4,
    base_delay=2.0,
    max_delay=60.0,
    backoff_factor=3.0,
)
