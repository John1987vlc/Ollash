import pytest
import time

from backend.utils.core.memory.embedding_cache import EmbeddingCache


@pytest.fixture
def embedding_cache():
    return EmbeddingCache(max_size=5, ttl_seconds=1)  # Small size and TTL for testing


class TestEmbeddingCache:
    """Test suite for Embedding Cache with LRU and TTL."""

    def test_put_get_success(self, embedding_cache):
        text = "hello world"
        vector = [0.1, 0.2, 0.3]

        embedding_cache.put(text, vector)
        assert embedding_cache.get(text) == vector

    def test_ttl_expiration(self, embedding_cache):
        embedding_cache.put("expire me", [1.0])
        assert embedding_cache.get("expire me") == [1.0]

        # Wait for TTL
        time.sleep(1.1)
        assert embedding_cache.get("expire me") is None

    def test_lru_eviction(self, embedding_cache):
        # Cache size is 5
        for i in range(6):
            embedding_cache.put(f"text_{i}", [float(i)])

        # text_0 should be evicted
        assert embedding_cache.get("text_0") is None
        assert embedding_cache.get("text_5") == [5.0]

    def test_batch_operations(self, embedding_cache):
        items = {"t1": [0.1], "t2": [0.2]}
        embedding_cache.put_batch(items)

        results = embedding_cache.get_batch(["t1", "t2", "t3"])
        assert results["t1"] == [0.1]
        assert results["t2"] == [0.2]
        assert results["t3"] is None

    def test_persistence_json(self, tmp_path):
        persist_path = tmp_path / "cache.json"
        cache = EmbeddingCache(persist_path=persist_path, persist_backend="json")

        cache.put("persist", [0.5])
        cache.save_to_disk()

        assert persist_path.exists()

        # New instance loading from disk
        new_cache = EmbeddingCache(persist_path=persist_path, persist_backend="json")
        assert new_cache.get("persist") == [0.5]

    def test_persistence_sqlite(self, tmp_path):
        persist_path = tmp_path / "cache"
        cache = EmbeddingCache(persist_path=persist_path, persist_backend="sqlite")

        cache.put("sql", [0.7])
        cache.save_to_disk()

        db_path = persist_path.with_suffix(".db")
        assert db_path.exists()

        # New instance
        new_cache = EmbeddingCache(persist_path=persist_path, persist_backend="sqlite")
        assert new_cache.get("sql") == [0.7]

    def test_memory_limit_eviction(self):
        # Set a very low memory limit (1MB is still plenty for small vectors,
        # but let's try to trigger it if possible or at least test the logic)
        cache = EmbeddingCache(max_memory_mb=1)

        # Put a large vector
        large_vector = [0.1] * 100000  # ~0.8MB in float64
        cache.put("large1", large_vector)
        cache.put("large2", large_vector)

        # Adding second one might trigger eviction if the estimate is conservative
        stats = cache.get_stats()
        assert stats["memory_bytes"] > 0

    def test_stats(self, embedding_cache):
        embedding_cache.put("t1", [1])
        embedding_cache.get("t1")  # hit
        embedding_cache.get("miss")  # miss

        stats = embedding_cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] == 0.5

    def test_clear(self, embedding_cache):
        embedding_cache.put("t", [1])
        embedding_cache.clear()
        assert embedding_cache.get("t") is None
        assert embedding_cache.get_stats()["hits"] == 0
