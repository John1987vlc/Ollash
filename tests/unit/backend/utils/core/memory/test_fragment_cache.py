import pytest
import sqlite3
from unittest.mock import MagicMock

from backend.utils.core.memory.fragment_cache import FragmentCache


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def fragment_cache(tmp_path, mock_logger):
    db_path = tmp_path / "fragments.db"
    return FragmentCache(db_path=db_path, logger=mock_logger)


class TestFragmentCache:
    """Test suite for Fragment Cache system."""

    def test_init_db(self, fragment_cache, tmp_path):
        db_path = tmp_path / "fragments.db"
        assert db_path.exists()

        with sqlite3.connect(str(db_path)) as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            assert "fragments" in [t[0] for t in tables]

    def test_set_get_fragment(self, fragment_cache):
        fragment_cache.set(
            fragment_type="license_header", language="python", content="MIT License Content", context="my project"
        )

        # Test hit
        content = fragment_cache.get("license_header", "python", context="my project")
        assert content == "MIT License Content"

        # Test miss (different context)
        assert fragment_cache.get("license_header", "python", context="other") is None

        # Test miss (different type)
        assert fragment_cache.get("class_template", "python") is None

    def test_get_hits_increment(self, fragment_cache):
        fragment_cache.set("t1", "l1", "content")

        # Initial hits should be 0 (stored in set as 0)
        # But set() uses upsert, hits starts at 0.

        fragment_cache.get("t1", "l1")  # Hit 1
        fragment_cache.get("t1", "l1")  # Hit 2

        stats = fragment_cache.stats()
        assert stats["total_hits"] == 2

    def test_get_by_pattern(self, fragment_cache):
        fragment_cache.set("code", "py", "print(1)", context="c1")
        fragment_cache.set("code", "py", "print(2)", context="c2")
        fragment_cache.set("code", "js", "console.log(1)")

        results = fragment_cache.get_by_pattern("code", "py")
        assert len(results) == 2
        assert "print(1)" in results
        assert "print(2)" in results

    def test_clear(self, fragment_cache):
        fragment_cache.set("t", "l", "c")
        fragment_cache.clear()
        assert fragment_cache.get("t", "l") is None
        assert fragment_cache.stats()["total_fragments"] == 0

    def test_preload_common_fragments(self, fragment_cache):
        fragment_cache.preload_common_fragments("python")

        # Verify some common fragments are loaded
        content = fragment_cache.get("license_header", "python")
        assert content is not None
        assert "MIT License" in content

    def test_set_favorite(self, fragment_cache):
        fragment_cache.set("t", "l", "content")
        key = fragment_cache._generate_cache_key("t", "l")

        fragment_cache.set_favorite(key, True)

        all_fragments = fragment_cache.list_all()
        assert all_fragments[0]["is_favorite"] == 1

    def test_validate_fn(self, fragment_cache):
        fragment_cache.set("t", "l", "short")

        # Validation fails
        content = fragment_cache.get("t", "l", validate_fn=lambda x: len(x) > 10)
        assert content is None

        # Validation passes
        content = fragment_cache.get("t", "l", validate_fn=lambda x: len(x) > 2)
        assert content == "short"
