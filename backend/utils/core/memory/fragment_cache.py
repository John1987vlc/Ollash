"""
Fragment Cache System for Auto-Generated Projects

Caches reusable code fragments (headers, boilerplate, standard structures)
to avoid redundant LLM calls and improve generation speed.
Backed by SQLAlchemy 2.0 async SQLite for improved performance and concurrency.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.db.engine import make_async_engine, make_session_factory
from backend.utils.core.system.db.sqlite_manager import AsyncDatabaseManager


class FragmentCache:
    """
    Caches common code fragments to reduce LLM calls using SQLAlchemy async SQLite.

    Fragments are indexed by:
    - Fragment type (license_header, class_boilerplate, etc.)
    - Language
    - Context hash
    """

    FRAGMENT_TYPES = {
        "license_header": "License headers (Apache, MIT, GPL, etc.)",
        "test_boilerplate": "Test file structure and imports",
        "class_template": "Standard class definition template",
        "async_pattern": "Async/await pattern implementations",
        "error_handling": "Exception handling patterns",
        "logging_setup": "Logging initialization patterns",
        "dependency_declaration": "Package/library declarations",
        "config_template": "Configuration file templates",
        "successful_task_example": "Validated generated file paired with its generation purpose",
    }

    def __init__(
        self,
        db_path: Optional[Path] = None,
        logger: Optional[AgentLogger] = None,
        cache_dir: Optional[Path] = None,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
        **kwargs,
    ):
        """
        Initialize the fragment cache with SQLAlchemy async SQLite.

        Args:
            db_path: Path to the SQLite database file.
            logger: Logger instance.
            cache_dir: Optional directory for cache (for DI compatibility).
            session_factory: Pre-built async_sessionmaker (injected via DI).
            **kwargs: Catch-all for extra configuration from containers.
        """
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            if cache_dir and not db_path:
                db_path = cache_dir / "fragments.db"
            if not db_path:
                db_path = Path(".cache/fragments.db")
            engine = make_async_engine(db_path)
            self._session_factory = make_session_factory(engine)

        self.db = AsyncDatabaseManager(self._session_factory)
        self.logger = logger

    async def _init_db(self) -> None:
        """Initialize the fragments table (idempotent, call once at startup)."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS fragments (
                key TEXT PRIMARY KEY,
                fragment_type TEXT NOT NULL,
                language TEXT NOT NULL,
                content TEXT NOT NULL,
                context_hash TEXT,
                hits INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                is_favorite BOOLEAN DEFAULT 0
            )
        """)
        await self.db.execute("CREATE INDEX IF NOT EXISTS idx_fragments_type ON fragments(fragment_type, language)")

    def _generate_cache_key(self, fragment_type: str, language: str, context_hash: str = "") -> str:
        """Generate a unique cache key."""
        context_part = f":{context_hash}" if context_hash else ""
        return f"{fragment_type}:{language}{context_part}".lower()

    def _compute_context_hash(self, context: str) -> str:
        """Compute MD5 hash of context."""
        return hashlib.md5(context.encode()).hexdigest()[:8]

    async def get(self, fragment_type: str, language: str, context: str = "", validate_fn=None) -> Optional[str]:
        """Retrieve a cached fragment."""
        context_hash = self._compute_context_hash(context) if context else ""
        cache_key = self._generate_cache_key(fragment_type, language, context_hash)

        row = await self.db.fetch_one("SELECT * FROM fragments WHERE key = :key", {"key": cache_key})

        if row:
            content = row["content"]
            if validate_fn and not validate_fn(content):
                if self.logger:
                    self.logger.debug(f"Fragment validation failed for {cache_key}")
                return None
            if self.logger:
                self.logger.debug(f"Fragment cache HIT for {cache_key}")
            await self.db.execute("UPDATE fragments SET hits = hits + 1 WHERE key = :key", {"key": cache_key})
            return content

        if self.logger:
            self.logger.debug(f"Fragment cache MISS for {cache_key}")
        return None

    async def set(
        self,
        fragment_type: str,
        language: str,
        content: str,
        context: str = "",
        metadata: Dict = None,
    ) -> None:
        """Store a fragment in the cache."""
        if not content:
            return

        context_hash = self._compute_context_hash(context) if context else ""
        cache_key = self._generate_cache_key(fragment_type, language, context_hash)

        data = {
            "key": cache_key,
            "fragment_type": fragment_type,
            "language": language,
            "content": content,
            "context_hash": context_hash,
            "created_at": datetime.now().isoformat(),
            "metadata": json.dumps(metadata or {}),
            "hits": 0,
        }

        await self.db.upsert("fragments", data, ["key"])
        if self.logger:
            self.logger.debug(f"Fragment cached: {cache_key}")

    async def get_by_pattern(self, fragment_type: str, language: str) -> List[str]:
        """Get all cached fragments matching a type and language."""
        results = await self.db.fetch_all(
            "SELECT content FROM fragments WHERE fragment_type = :fragment_type AND language = :language",
            {"fragment_type": fragment_type, "language": language},
        )
        return [r["content"] for r in results]

    async def clear(self) -> None:
        """Clear all cached fragments."""
        await self.db.execute("DELETE FROM fragments")
        if self.logger:
            self.logger.info("Fragment cache cleared")

    async def stats(self) -> Dict:
        """Return cache statistics."""
        row = await self.db.fetch_one("""
            SELECT
                COUNT(*) as total_fragments,
                SUM(hits) as total_hits,
                COUNT(DISTINCT fragment_type) as fragment_types,
                COUNT(DISTINCT language) as languages
            FROM fragments
        """)

        stats = dict(row) if row else {}
        total = stats.get("total_fragments", 0)
        stats["avg_hits_per_fragment"] = (stats.get("total_hits", 0) / total) if total > 0 else 0
        return stats

    async def preload_common_fragments(self, language: str) -> None:
        """Preload common fragments for a language."""
        common_fragments = self._get_common_fragments_for_language(language)
        for fragment_type, content, metadata in common_fragments:
            if await self.get(fragment_type, language) is None:
                await self.set(fragment_type, language, content, metadata=metadata)
        if self.logger:
            self.logger.info(f"Preloaded common fragments for {language}")

    @staticmethod
    def _get_common_fragments_for_language(language: str) -> List[tuple]:
        """Return a list of (fragment_type, content, metadata) for common language patterns."""
        fragments = {
            "python": [
                (
                    "license_header",
                    '"""\\nMIT License\\n\\nCopyright (c) 2026\\n\\nPermission is hereby granted...\\n"""\\n',
                    {"license": "MIT", "language": "python"},
                ),
                (
                    "test_boilerplate",
                    (
                        "import pytest\\nfrom unittest.mock import Mock, patch\\n\\n\\n"
                        "class Test{{ClassName}}:\\n    def setup_method(self):\\n        pass\\n"
                    ),
                    {"test_framework": "pytest"},
                ),
            ],
        }
        return fragments.get(language, [])

    async def list_all(self) -> List[Dict]:
        """List all fragments ordered by hits descending."""
        rows = await self.db.fetch_all("SELECT * FROM fragments ORDER BY hits DESC")
        result = []
        for row in rows:
            data = dict(row)
            try:
                data["metadata"] = json.loads(data["metadata"])
            except Exception:
                data["metadata"] = {}
            result.append(data)
        return result

    async def set_favorite(self, key: str, is_favorite: bool) -> None:
        await self.db.execute(
            "UPDATE fragments SET is_favorite = :is_favorite WHERE key = :key",
            {"key": key, "is_favorite": is_favorite},
        )

    # ------------------------------------------------------------------
    # Feature: Few-Shot Dynamic Store
    # ------------------------------------------------------------------

    async def store_example(self, language: str, purpose: str, code: str) -> None:
        """Store a validated (purpose, code) pair as a few-shot example."""
        if not purpose or not code:
            return
        await self.set(
            fragment_type="successful_task_example",
            language=language,
            content=code,
            context=purpose,
            metadata={"purpose": purpose},
        )

    async def get_similar_examples(
        self,
        language: str,
        purpose: str,
        max_examples: int = 2,
    ) -> List[Tuple[str, str]]:
        """Retrieve up to *max_examples* few-shot examples by keyword overlap."""
        rows = await self.db.fetch_all(
            "SELECT content, metadata FROM fragments "
            "WHERE fragment_type = :fragment_type AND language = :language "
            "ORDER BY hits DESC LIMIT 50",
            {"fragment_type": "successful_task_example", "language": language},
        )
        scored: List[Tuple[int, str, str]] = []
        purpose_words = set(purpose.lower().split())
        for row in rows:
            try:
                meta = json.loads(row["metadata"])
                stored_purpose: str = meta.get("purpose", "")
                overlap = len(purpose_words & set(stored_purpose.lower().split()))
                if overlap > 0:
                    scored.append((overlap, stored_purpose, row["content"]))
            except Exception:
                continue
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(p, c) for _, p, c in scored[:max_examples]]
