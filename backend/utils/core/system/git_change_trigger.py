"""
Git Change Trigger — Polls for external git changes and fires a callback.

Detects when a developer manually pushes commits or makes changes outside of
the AutoAgent pipeline. When a significant change is detected the trigger
fires an ``on_change_callback`` so AutomationManager can reschedule the next
hourly run to execute immediately.

Runs as a daemon background thread; does not block the main event loop.
"""

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from backend.utils.core.io.git_manager import GitManager
from backend.utils.core.system.agent_logger import AgentLogger


class GitChangeTrigger:
    """Polls git diff-numstat to detect external repository changes.

    When the number of changed lines exceeds ``min_changed_lines`` relative to
    the last known state, ``on_change_callback`` is invoked so the caller can
    react (e.g. reschedule the next automation run to "now").

    Thread safety: all state mutations happen on the daemon thread; the
    callback is invoked from the daemon thread. Callers must ensure their
    callback is thread-safe.

    Example::

        trigger = GitChangeTrigger(
            repo_path=Path("myproject"),
            on_change_callback=lambda: print("changes detected!"),
            logger=my_logger,
        )
        trigger.start()
        # ... later ...
        trigger.stop()
    """

    def __init__(
        self,
        repo_path: Path,
        on_change_callback: Callable[[], None],
        logger: AgentLogger,
        poll_interval_seconds: int = 30,
        min_changed_lines: int = 5,
    ):
        """Initialise the trigger.

        Args:
            repo_path: Path to the git repository root.
            on_change_callback: Zero-argument callable invoked when changes are detected.
            logger: AgentLogger instance for structured logging.
            poll_interval_seconds: How often (in seconds) to poll git.
            min_changed_lines: Minimum line-delta before the callback fires.
        """
        self.git = GitManager(repo_path=str(repo_path))
        self.callback = on_change_callback
        self.logger = logger
        self.poll_interval = poll_interval_seconds
        self.min_changed_lines = min_changed_lines

        self._last_known_total: int = 0
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background polling thread (daemon)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="GitChangeTrigger",
        )
        self._thread.start()
        self.logger.info(
            f"GitChangeTrigger started (poll={self.poll_interval}s, "
            f"threshold={self.min_changed_lines} lines)"
        )

    def stop(self) -> None:
        """Signal the polling thread to stop at its next wake-up."""
        self._running = False
        self.logger.info("GitChangeTrigger stop requested")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        """Daemon loop: poll git, detect changes, fire callback."""
        while self._running:
            try:
                result = self.git.diff_numstat()
                if result.get("success"):
                    total: int = result.get("total", 0)
                    delta = total - self._last_known_total
                    if delta > self.min_changed_lines:
                        self.logger.info(
                            f"GitChangeTrigger: {delta} new lines changed "
                            f"(total={total}), firing callback"
                        )
                        self._last_known_total = total
                        try:
                            self.callback()
                        except Exception as callback_exc:
                            self.logger.error(
                                f"GitChangeTrigger: callback raised an exception: {callback_exc}"
                            )
            except Exception as poll_exc:
                # Swallow errors silently to keep the daemon alive
                self.logger.warning(f"GitChangeTrigger: poll error (non-fatal): {poll_exc}")

            time.sleep(self.poll_interval)
