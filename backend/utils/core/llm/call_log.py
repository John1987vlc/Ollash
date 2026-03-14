"""
backend/utils/core/llm/call_log.py
In-memory ring-buffer of recent LLM calls — accessible by the audit router.
Thread-safe, no external deps.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Any

_MAX_ENTRIES = 500


class LLMCallLog:
    """Singleton ring-buffer storing the last N LLM calls."""

    _instance: "LLMCallLog | None" = None
    _lock: Lock = Lock()

    def __new__(cls) -> "LLMCallLog":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = object.__new__(cls)
                    inst._entries: deque[dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)
                    inst._write_lock = Lock()
                    cls._instance = inst
        return cls._instance

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        success: bool,
        error: str | None = None,
    ) -> None:
        entry = {
            "ts": time.time(),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "latency_ms": round(latency_ms, 1),
            "success": success,
            "error": error,
        }
        with self._write_lock:
            self._entries.append(entry)

    def get_recent(self, limit: int = 100) -> list[dict]:
        with self._write_lock:
            entries = list(self._entries)
        return entries[-limit:]

    def stats(self) -> dict:
        with self._write_lock:
            entries = list(self._entries)
        if not entries:
            return {"total_calls": 0, "total_tokens": 0, "avg_latency_ms": 0, "error_rate": 0.0}
        total_tokens = sum(e["total_tokens"] for e in entries)
        avg_latency = sum(e["latency_ms"] for e in entries) / len(entries)
        errors = sum(1 for e in entries if not e["success"])
        return {
            "total_calls": len(entries),
            "total_tokens": total_tokens,
            "avg_latency_ms": round(avg_latency, 1),
            "error_rate": round(errors / len(entries), 3),
        }

    def clear(self) -> None:
        with self._write_lock:
            self._entries.clear()


# Module-level singleton
llm_call_log = LLMCallLog()
