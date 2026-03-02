import pytest
import sqlite3
from unittest.mock import MagicMock

from backend.utils.core.memory.fragment_cache import FragmentCache

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
async def fragment_cache(tmp_path, mock_logger):
    db_path = tmp_path / "fragments.db"
    cache = FragmentCache(db_path=db_path, logger=mock_logger)
    await cache._init_db()
    return cache


class TestFragmentCache:
    """Test suite for Fragment Cache system."""

    async def test_init_db(self, fragment_cache, tmp_path):
        db_path = tmp_path / "fragments.db"
        assert db_path.exists()

        with sqlite3.connect(str(db_path)) as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            assert "fragments" in [t[0] for t in tables]

    async def test_set_get_fragment(self, fragment_cache):
        await fragment_cache.set(
            fragment_type="license_header", language="python", content="MIT License Content", context="my project"
        )

        # Test hit
        content = await fragment_cache.get("license_header", "python", context="my project")
        assert content == "MIT License Content"

        # Test miss (different context)
        assert await fragment_cache.get("license_header", "python", context="other") is None

        # Test miss (different type)
        assert await fragment_cache.get("class_template", "python") is None

    async def test_get_hits_increment(self, fragment_cache):
        await fragment_cache.set("t1", "l1", "content")

        await fragment_cache.get("t1", "l1")  # Hit 1
        await fragment_cache.get("t1", "l1")  # Hit 2

        stats = await fragment_cache.stats()
        assert stats["total_hits"] == 2

    async def test_get_by_pattern(self, fragment_cache):
        await fragment_cache.set("code", "py", "print(1)", context="c1")
        await fragment_cache.set("code", "py", "print(2)", context="c2")
        await fragment_cache.set("code", "js", "console.log(1)")

        results = await fragment_cache.get_by_pattern("code", "py")
        assert len(results) == 2
        assert "print(1)" in results
        assert "print(2)" in results

    async def test_clear(self, fragment_cache):
        await fragment_cache.set("t", "l", "c")
        await fragment_cache.clear()
        assert await fragment_cache.get("t", "l") is None
        assert (await fragment_cache.stats())["total_fragments"] == 0

    async def test_preload_common_fragments(self, fragment_cache):
        await fragment_cache.preload_common_fragments("python")

        content = await fragment_cache.get("license_header", "python")
        assert content is not None
        assert "MIT License" in content

    async def test_set_favorite(self, fragment_cache):
        await fragment_cache.set("t", "l", "content")
        key = fragment_cache._generate_cache_key("t", "l")

        await fragment_cache.set_favorite(key, True)

        all_fragments = await fragment_cache.list_all()
        assert all_fragments[0]["is_favorite"] == 1

    async def test_validate_fn(self, fragment_cache):
        await fragment_cache.set("t", "l", "short")

        # Validation fails
        content = await fragment_cache.get("t", "l", validate_fn=lambda x: len(x) > 10)
        assert content is None

        # Validation passes
        content = await fragment_cache.get("t", "l", validate_fn=lambda x: len(x) > 2)
        assert content == "short"
