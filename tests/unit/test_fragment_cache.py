"""
Unit tests for FragmentCache system (SQLite version).
"""

import json
from unittest.mock import Mock

import pytest

from backend.utils.core.fragment_cache import FragmentCache


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary DB path."""
    return tmp_path / "knowledge.db"


@pytest.fixture
def logger_mock():
    """Create a mock logger."""
    return Mock()


@pytest.fixture
def fragment_cache(temp_db_path, logger_mock):
    """Create a FragmentCache instance."""
    return FragmentCache(temp_db_path, logger_mock)


class TestFragmentCacheBasics:
    """Test basic cache operations."""

    def test_cache_set_and_get(self, fragment_cache):
        """Test setting and getting a fragment."""
        fragment_cache.set("license_header", "python", "# MIT License\nCopyright (c) 2026")

        result = fragment_cache.get("license_header", "python")
        assert result == "# MIT License\nCopyright (c) 2026"

    def test_cache_miss_returns_none(self, fragment_cache):
        """Test that missing fragments return None."""
        result = fragment_cache.get("nonexistent", "python")
        assert result is None

    def test_cache_hit_increments_counter(self, fragment_cache):
        """Test that cache hits are counted."""
        fragment_cache.set("test_type", "python", "test content")

        # First get
        fragment_cache.get("test_type", "python")
        fragment_cache.get("test_type", "python")
        fragment_cache.get("test_type", "python")

        # Check statistics
        stats = fragment_cache.stats()
        assert stats["total_hits"] >= 3

    def test_cache_key_generation(self, fragment_cache):
        """Test cache key generation."""
        key1 = fragment_cache._generate_cache_key("license", "python")
        key2 = fragment_cache._generate_cache_key("LICENSE", "PYTHON")

        # Should be case-insensitive
        assert key1 == key2

    def test_cache_with_context(self, fragment_cache):
        """Test caching with context hashing."""
        context = "project description"

        fragment_cache.set("class_template", "python", "class MyClass: pass", context=context)

        # With same context
        result = fragment_cache.get("class_template", "python", context=context)
        assert result == "class MyClass: pass"

        # With different context
        result = fragment_cache.get("class_template", "python", context="other context")
        assert result is None


class TestFragmentCacheValidation:
    """Test fragment validation."""

    def test_cache_validation_function(self, fragment_cache):
        """Test custom validation function."""

        def validate_syntax(content):
            return "class" in content

        fragment_cache.set("class_template", "python", "class MyClass: pass")

        # Valid fragment
        result = fragment_cache.get("class_template", "python", validate_fn=validate_syntax)
        assert result is not None

        # Invalid fragment
        fragment_cache.set("invalid", "python", "just some text")
        result = fragment_cache.get("invalid", "python", validate_fn=validate_syntax)
        assert result is None


class TestFragmentCachePersistence:
    """Test persistence to disk."""

    def test_cache_persistence_save(self, temp_db_path, logger_mock):
        """Test saving cache to disk."""
        cache1 = FragmentCache(temp_db_path, logger_mock)
        cache1.set("license", "python", "MIT License")

        # Create new cache instance (should load from DB)
        cache2 = FragmentCache(temp_db_path, logger_mock)
        result = cache2.get("license", "python")

        assert result == "MIT License"

    def test_cache_file_exists(self, fragment_cache, temp_db_path):
        """Test that cache file is created."""
        fragment_cache.set("fragment", "python", "content")

        assert temp_db_path.exists()


class TestFragmentCacheByPattern:
    """Test pattern-based retrieval."""

    def test_get_by_pattern(self, fragment_cache):
        """Test getting fragments by pattern."""
        fragment_cache.set("license_header", "python", "MIT")
        fragment_cache.set("license_header", "javascript", "Apache")

        results = fragment_cache.get_by_pattern("license_header", "python")
        assert len(results) > 0
        assert "MIT" in results

    def test_clear_cache(self, fragment_cache):
        """Test clearing cache."""
        fragment_cache.set("test", "python", "content")
        assert fragment_cache.stats()["total_fragments"] > 0

        fragment_cache.clear()
        # Verify cache is cleared and stats returns dict
        stats = fragment_cache.stats()
        assert stats["total_fragments"] == 0


class TestFragmentCacheStats:
    """Test statistics."""

    def test_stats_empty_cache(self, fragment_cache):
        """Test stats on empty cache."""
        stats = fragment_cache.stats()
        # Verify stats returns a dictionary
        assert isinstance(stats, dict)
        assert stats.get("total_fragments", 0) == 0

    def test_stats_populated_cache(self, fragment_cache):
        """Test stats on populated cache."""
        fragment_cache.set("license", "python", "MIT")
        fragment_cache.set("test_boilerplate", "python", "import pytest")
        fragment_cache.set("license", "javascript", "Apache")

        stats = fragment_cache.stats()
        assert stats["total_fragments"] == 3
        assert stats["fragment_types"] >= 1
        assert stats["languages"] >= 1
