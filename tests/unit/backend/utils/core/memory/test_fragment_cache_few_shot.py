"""Unit tests for FragmentCache few-shot store — Feature 2."""

import tempfile
from pathlib import Path

import pytest

from backend.utils.core.memory.fragment_cache import FragmentCache


def _make_cache():
    tmp = tempfile.mkdtemp()
    mock_logger = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    return FragmentCache(db_path=Path(tmp) / "test.db", logger=mock_logger)


@pytest.mark.unit
class TestFragmentCacheFewShot:
    def test_store_and_retrieve_by_keyword(self):
        cache = _make_cache()
        cache.store_example("python", "generate REST API endpoint", "def api(): pass")
        results = cache.get_similar_examples("python", "REST API handler", max_examples=2)
        assert len(results) == 1
        assert results[0][1] == "def api(): pass"

    def test_get_similar_sorted_by_overlap(self):
        cache = _make_cache()
        # Both examples share words with the query, but second shares more
        cache.store_example("python", "REST API simple handler", "def api_simple(): pass")
        cache.store_example("python", "complex REST API endpoint with auth", "def api_auth(): pass")
        # Query: "REST API endpoint" — more overlap with second example (3 shared: REST, API, endpoint)
        results = cache.get_similar_examples("python", "REST API endpoint", max_examples=2)
        assert len(results) == 2
        # Best match first: "complex REST API endpoint with auth" shares REST+API+endpoint (3 words)
        assert "api_auth" in results[0][1]

    def test_no_keyword_overlap_returns_empty(self):
        cache = _make_cache()
        cache.store_example("python", "database connection pool", "def connect(): pass")
        results = cache.get_similar_examples("python", "unrelated xyz abc", max_examples=2)
        assert results == []

    def test_empty_purpose_is_noop(self):
        cache = _make_cache()
        cache.store_example("python", "", "def foo(): pass")
        results = cache.get_similar_examples("python", "foo", max_examples=2)
        assert results == []

    def test_empty_code_is_noop(self):
        cache = _make_cache()
        cache.store_example("python", "some purpose", "")
        results = cache.get_similar_examples("python", "some purpose", max_examples=2)
        assert results == []

    def test_max_examples_limits_results(self):
        cache = _make_cache()
        for i in range(5):
            cache.store_example("python", f"generate api endpoint number {i}", f"def api{i}(): pass")
        results = cache.get_similar_examples("python", "generate api endpoint", max_examples=2)
        assert len(results) <= 2

    def test_different_language_not_returned(self):
        cache = _make_cache()
        cache.store_example("javascript", "generate REST API", "function api() {}")
        results = cache.get_similar_examples("python", "generate REST API", max_examples=2)
        assert results == []
