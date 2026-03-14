"""Network call monitor — logs every outbound HTTP request made by Ollash.

Provides a module-level singleton that records outbound calls into a
ring buffer and classifies them as local (whitelist) or external.

Usage
-----
    from backend.utils.core.system.network_monitor import network_monitor

    network_monitor.record("http://localhost:11434/api/chat", "POST", 200)
    summary = network_monitor.summary()
    log     = network_monitor.get_log()

The whitelist is driven by the OLLASH_ALLOWED_HOSTS environment variable
(comma-separated hostnames/IPs).  Default: localhost, 127.0.0.1, ::1.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Any
from urllib.parse import urlparse


class NetworkMonitor:
    """Thread-safe ring buffer for outbound HTTP call logging."""

    _MAX_ENTRIES = 500

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._log: deque[dict[str, Any]] = deque(maxlen=self._MAX_ENTRIES)
        self._allowed_hosts: set[str] = self._load_allowed_hosts()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @staticmethod
    def _load_allowed_hosts() -> set[str]:
        env = os.environ.get("OLLASH_ALLOWED_HOSTS", "localhost,127.0.0.1,::1")
        return {h.strip().lower() for h in env.split(",") if h.strip()}

    def get_allowed_hosts(self) -> list[str]:
        return sorted(self._allowed_hosts)

    def add_allowed_host(self, host: str) -> None:
        with self._lock:
            self._allowed_hosts.add(host.lower())

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, url: str, method: str = "GET", status_code: int = 0) -> None:
        """Record an outbound HTTP call.  Never raises — best-effort only."""
        try:
            host = urlparse(url).hostname or ""
            is_external = host.lower() not in self._allowed_hosts

            entry: dict[str, Any] = {
                "ts": time.time(),
                "url": url,
                "host": host,
                "method": method.upper(),
                "status_code": status_code,
                "is_external": is_external,
            }
            with self._lock:
                self._log.append(entry)
        except Exception:
            pass  # monitor must never interrupt the main call

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_log(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return the *limit* most recent entries, newest first."""
        with self._lock:
            entries = list(self._log)
        entries.reverse()
        return entries[:limit]

    def summary(self) -> dict[str, Any]:
        """Return aggregate statistics for the current session."""
        with self._lock:
            entries = list(self._log)

        total = len(entries)
        external = [e for e in entries if e["is_external"]]
        local = [e for e in entries if not e["is_external"]]

        host_counts: dict[str, int] = {}
        for e in entries:
            host_counts[e["host"]] = host_counts.get(e["host"], 0) + 1

        return {
            "total_calls": total,
            "local_calls": len(local),
            "external_calls": len(external),
            "is_clean": len(external) == 0,
            "allowed_hosts": self.get_allowed_hosts(),
            "top_hosts": sorted(host_counts.items(), key=lambda x: -x[1])[:10],
            "external_urls": [e["url"] for e in external[-20:]],
        }

    def clear(self) -> None:
        with self._lock:
            self._log.clear()


# Module-level singleton — import and use directly.
network_monitor = NetworkMonitor()
