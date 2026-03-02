"""Unit tests for FragmentCache few-shot store — Feature 2."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.utils.core.memory.fragment_cache import FragmentCache

pytestmark = pytest.mark.unit


async def _make_cache():
    tmp = tempfile.mkdtemp()
    cache = FragmentCache(db_path=Path(tmp) / "test.db", logger=MagicMock())
    await cache._init_db()
    return cache


@pytest.mark.unit
class TestFragmentCacheFewShot:
    async def test_store_and_retrieve_by_keyword(self):
        cache = await _make_cache()
        await cache.store_example("python", "generate REST API endpoint", "def api(): pass")
        results = await cache.get_similar_examples("python", "REST API handler", max_examples=2)
        assert len(results) == 1
        assert results[0][1] == "def api(): pass"

    async def test_get_similar_sorted_by_overlap(self):
        cache = await _make_cache()
        await cache.store_example("python", "REST API simple handler", "def api_simple(): pass")
        await cache.store_example("python", "complex REST API endpoint with auth", "def api_auth(): pass")
        results = await cache.get_similar_examples("python", "REST API endpoint", max_examples=2)
        assert len(results) == 2
        assert "api_auth" in results[0][1]

    async def test_no_keyword_overlap_returns_empty(self):
        cache = await _make_cache()
        await cache.store_example("python", "database connection pool", "def connect(): pass")
        results = await cache.get_similar_examples("python", "unrelated xyz abc", max_examples=2)
        assert results == []

    async def test_empty_purpose_is_noop(self):
        cache = await _make_cache()
        await cache.store_example("python", "", "def foo(): pass")
        results = await cache.get_similar_examples("python", "foo", max_examples=2)
        assert results == []

    async def test_empty_code_is_noop(self):
        cache = await _make_cache()
        await cache.store_example("python", "some purpose", "")
        results = await cache.get_similar_examples("python", "some purpose", max_examples=2)
        assert results == []

    async def test_max_examples_limits_results(self):
        cache = await _make_cache()
        for i in range(5):
            await cache.store_example("python", f"generate api endpoint number {i}", f"def api{i}(): pass")
        results = await cache.get_similar_examples("python", "generate api endpoint", max_examples=2)
        assert len(results) <= 2

    async def test_different_language_not_returned(self):
        cache = await _make_cache()
        await cache.store_example("javascript", "generate REST API", "function api() {}")
        results = await cache.get_similar_examples("python", "generate REST API", max_examples=2)
        assert results == []
