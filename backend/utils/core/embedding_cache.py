"""Local hash-based LRU cache for embedding vectors.

Avoids redundant /api/embed calls for identical text inputs.
Uses SHA-256 of the input text as the cache key with TTL expiration.
"""

import hashlib
import json
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class EmbeddingCache:
    """Hash-based LRU cache for embedding vectors.

    Uses SHA-256 of the input text as the cache key. Supports both
    in-memory and optional disk persistence.
    """

    def __init__(
        self,
        max_size: int = 10000,
        ttl_seconds: int = 3600,
        persist_path: Optional[Path] = None,
        logger=None,
    ):
        self._cache: OrderedDict[str, Tuple[List[float], float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._persist_path = persist_path
        self._logger = logger
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        if persist_path and persist_path.exists():
            self._load_from_disk()

    @staticmethod
    def _hash_text(text: str) -> str:
        """Generates a SHA-256 hash of the input text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[List[float]]:
        """Returns cached embedding or None if not found/expired."""
        key = self._hash_text(text)
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            embedding, timestamp = self._cache[key]
            if time.time() - timestamp > self._ttl:
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return embedding

    def put(self, text: str, embedding: List[float]) -> None:
        """Stores an embedding, evicting oldest entry if at capacity."""
        key = self._hash_text(text)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = (embedding, time.time())
                return

            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            self._cache[key] = (embedding, time.time())

    def _evict_expired(self) -> int:
        """Remove entries past TTL. Returns number of evicted entries."""
        now = time.time()
        evicted = 0
        with self._lock:
            expired_keys = [k for k, (_, ts) in self._cache.items() if now - ts > self._ttl]
            for k in expired_keys:
                del self._cache[k]
                evicted += 1
        return evicted

    def get_stats(self) -> Dict[str, object]:
        """Returns cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "max_size": self._max_size,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
        }

    def save_to_disk(self) -> None:
        """Persist cache to JSON file."""
        if not self._persist_path:
            return
        try:
            with self._lock:
                data = {k: {"embedding": emb, "timestamp": ts} for k, (emb, ts) in self._cache.items()}
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            if self._logger:
                self._logger.debug(f"Embedding cache persisted ({len(data)} entries)")
        except Exception as e:
            if self._logger:
                self._logger.warning(f"Failed to persist embedding cache: {e}")

    def _load_from_disk(self) -> None:
        """Load cache from JSON file."""
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            with open(self._persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            now = time.time()
            loaded = 0
            for k, v in data.items():
                ts = v.get("timestamp", 0)
                if now - ts <= self._ttl:
                    self._cache[k] = (v["embedding"], ts)
                    loaded += 1
                    if loaded >= self._max_size:
                        break
            if self._logger:
                self._logger.debug(f"Loaded {loaded} embeddings from cache")
        except Exception as e:
            if self._logger:
                self._logger.warning(f"Failed to load embedding cache: {e}")

    def clear(self) -> None:
        """Clears all cached embeddings."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
