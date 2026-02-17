"""Local hash-based LRU cache for embedding vectors.

Avoids redundant /api/embed calls for identical text inputs.
Uses SHA-256 of the input text as the cache key with TTL expiration.

Supports batch operations, memory monitoring, and SQLite persistence backend.
"""

import hashlib
import json
import sqlite3
import sys
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple


class EmbeddingCache:
    """Hash-based LRU cache for embedding vectors.

    Uses SHA-256 of the input text as the cache key. Supports both
    in-memory and optional disk persistence (JSON or SQLite backend).
    """

    def __init__(
        self,
        max_size: int = 10000,
        ttl_seconds: int = 3600,
        persist_path: Optional[Path] = None,
        persist_backend: Literal["json", "sqlite"] = "json",
        max_memory_mb: Optional[int] = None,
        logger: object = None,
    ):
        self._cache: OrderedDict[str, Tuple[List[float], float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._persist_path = persist_path
        self._persist_backend = persist_backend
        self._max_memory_mb = max_memory_mb
        self._logger = logger
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

        if persist_path:
            if persist_backend == "sqlite" and persist_path.with_suffix(".db").exists():
                self._load_from_disk()
            elif persist_path.exists():
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

            # Auto-evict if memory limit exceeded
            if self._max_memory_mb:
                self._auto_evict_on_memory_limit()

    def get_batch(self, texts: List[str]) -> Dict[str, Optional[List[float]]]:
        """Batch retrieval of embeddings. Returns {text: embedding_or_None}."""
        results: Dict[str, Optional[List[float]]] = {}
        with self._lock:
            for text in texts:
                key = self._hash_text(text)
                if key not in self._cache:
                    self._misses += 1
                    results[text] = None
                    continue

                embedding, timestamp = self._cache[key]
                if time.time() - timestamp > self._ttl:
                    del self._cache[key]
                    self._misses += 1
                    results[text] = None
                    continue

                self._cache.move_to_end(key)
                self._hits += 1
                results[text] = embedding
        return results

    def put_batch(self, items: Dict[str, List[float]]) -> None:
        """Batch insertion of embeddings. {text: embedding_vector}."""
        now = time.time()
        with self._lock:
            for text, embedding in items.items():
                key = self._hash_text(text)
                if key in self._cache:
                    self._cache.move_to_end(key)
                    self._cache[key] = (embedding, now)
                    continue

                if len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)
                self._cache[key] = (embedding, now)

            if self._max_memory_mb:
                self._auto_evict_on_memory_limit()

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

    def get_memory_usage_bytes(self) -> int:
        """Estimate memory usage of cached embeddings in bytes."""
        total = sys.getsizeof(self._cache)
        for key, (embedding, _) in self._cache.items():
            total += sys.getsizeof(key)
            total += sys.getsizeof(embedding) + len(embedding) * 8  # float64
        return total

    def _auto_evict_on_memory_limit(self) -> int:
        """Evict oldest entries until memory usage is under the limit. Must hold lock."""
        if not self._max_memory_mb:
            return 0
        max_bytes = self._max_memory_mb * 1024 * 1024
        evicted = 0
        while self._cache and self.get_memory_usage_bytes() > max_bytes:
            self._cache.popitem(last=False)
            evicted += 1
        return evicted

    def get_stats(self) -> Dict[str, object]:
        """Returns cache statistics including memory usage."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "max_size": self._max_size,
            "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
            "memory_bytes": self.get_memory_usage_bytes(),
            "backend": self._persist_backend,
        }

    def save_to_disk(self) -> None:
        """Persist cache to disk using configured backend."""
        if not self._persist_path:
            return
        if self._persist_backend == "sqlite":
            self._save_to_sqlite()
        else:
            self._save_to_json()

    def _save_to_json(self) -> None:
        """Persist cache to JSON file."""
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

    def _save_to_sqlite(self) -> None:
        """Persist cache to SQLite database."""
        db_path = self._persist_path.with_suffix(".db")
        try:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                entries = list(self._cache.items())
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS embeddings (
                        key TEXT PRIMARY KEY,
                        embedding BLOB,
                        timestamp REAL
                    )
                """)
                conn.execute("DELETE FROM embeddings")
                for key, (emb, ts) in entries:
                    emb_bytes = json.dumps(emb).encode("utf-8")
                    conn.execute("INSERT INTO embeddings VALUES (?, ?, ?)", (key, emb_bytes, ts))
                conn.commit()
            finally:
                conn.close()
            if self._logger:
                self._logger.debug(f"Embedding cache persisted to SQLite ({len(entries)} entries)")
        except Exception as e:
            if self._logger:
                self._logger.warning(f"Failed to persist embedding cache to SQLite: {e}")

    def _load_from_disk(self) -> None:
        """Load cache from disk using configured backend."""
        if not self._persist_path:
            return
        if self._persist_backend == "sqlite":
            self._load_from_sqlite()
        else:
            self._load_from_json()

    def _load_from_json(self) -> None:
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

    def _load_from_sqlite(self) -> None:
        """Load cache from SQLite database."""
        db_path = self._persist_path.with_suffix(".db")
        if not db_path.exists():
            return
        try:
            conn = sqlite3.connect(str(db_path))
            try:
                now = time.time()
                loaded = 0
                for row in conn.execute("SELECT key, embedding, timestamp FROM embeddings ORDER BY timestamp DESC"):
                    key, emb_bytes, ts = row
                    if now - ts <= self._ttl:
                        embedding = json.loads(emb_bytes.decode("utf-8"))
                        self._cache[key] = (embedding, ts)
                        loaded += 1
                        if loaded >= self._max_size:
                            break
            finally:
                conn.close()
            if self._logger:
                self._logger.debug(f"Loaded {loaded} embeddings from SQLite cache")
        except Exception as e:
            if self._logger:
                self._logger.warning(f"Failed to load embedding cache from SQLite: {e}")

    def clear(self) -> None:
        """Clears all cached embeddings."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
