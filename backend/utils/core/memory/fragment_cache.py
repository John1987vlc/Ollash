"""
Fragment Cache System for Auto-Generated Projects

Caches reusable code fragments (headers, boilerplate, standard structures)
to avoid redundant LLM calls and improve generation speed.
Backed by stdlib sqlite3 for zero-dependency synchronous access.
"""

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.utils.core.system.agent_logger import AgentLogger


class FragmentCache:
    """
    Caches common code fragments to reduce LLM calls using sqlite3 (sync).

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
        session_factory=None,  # kept for DI backward-compat; ignored
        **kwargs,
    ):
        if cache_dir and not db_path:
            db_path = cache_dir / "fragments.db"
        if not db_path:
            db_path = Path(".cache/fragments.db")

        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logger

        # Initialise schema immediately (sync, idempotent)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal sqlite3 helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _execute(self, query: str, params=()) -> None:
        with self._conn() as conn:
            conn.execute(query, params)

    def _fetch_all(self, query: str, params=()) -> List[Dict]:
        with self._conn() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def _fetch_one(self, query: str, params=()) -> Optional[Dict]:
        with self._conn() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def _upsert(self, table: str, data: Dict, unique_keys: List[str]) -> None:
        columns = ", ".join(data.keys())
        placeholders = ", ".join([f":{k}" for k in data.keys()])
        updates = ", ".join([f"{k}=excluded.{k}" for k in data.keys() if k not in unique_keys])
        query = (
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT({', '.join(unique_keys)}) DO UPDATE SET {updates}"
        )
        self._execute(query, data)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Initialise the fragments table (idempotent)."""
        self._execute("""
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
        self._execute("CREATE INDEX IF NOT EXISTS idx_fragments_type ON fragments(fragment_type, language)")

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def _generate_cache_key(self, fragment_type: str, language: str, context_hash: str = "") -> str:
        context_part = f":{context_hash}" if context_hash else ""
        return f"{fragment_type}:{language}{context_part}".lower()

    def _compute_context_hash(self, context: str) -> str:
        return hashlib.md5(context.encode()).hexdigest()[:8]

    # ------------------------------------------------------------------
    # Public API (sync)
    # ------------------------------------------------------------------

    def get(self, fragment_type: str, language: str, context: str = "", validate_fn=None) -> Optional[str]:
        """Retrieve a cached fragment."""
        context_hash = self._compute_context_hash(context) if context else ""
        cache_key = self._generate_cache_key(fragment_type, language, context_hash)

        row = self._fetch_one("SELECT * FROM fragments WHERE key = :key", {"key": cache_key})
        if row:
            content = row["content"]
            if validate_fn and not validate_fn(content):
                if self.logger:
                    self.logger.debug(f"Fragment validation failed for {cache_key}")
                return None
            if self.logger:
                self.logger.debug(f"Fragment cache HIT for {cache_key}")
            self._execute("UPDATE fragments SET hits = hits + 1 WHERE key = :key", {"key": cache_key})
            return content

        if self.logger:
            self.logger.debug(f"Fragment cache MISS for {cache_key}")
        return None

    def set(
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
        self._upsert("fragments", data, ["key"])
        if self.logger:
            self.logger.debug(f"Fragment cached: {cache_key}")

    def get_by_pattern(self, fragment_type: str, language: str) -> List[str]:
        """Get all cached fragments matching a type and language."""
        results = self._fetch_all(
            "SELECT content FROM fragments WHERE fragment_type = :fragment_type AND language = :language",
            {"fragment_type": fragment_type, "language": language},
        )
        return [r["content"] for r in results]

    def clear(self) -> None:
        """Clear all cached fragments."""
        self._execute("DELETE FROM fragments")
        if self.logger:
            self.logger.info("Fragment cache cleared")

    def stats(self) -> Dict:
        """Return cache statistics."""
        row = self._fetch_one("""
            SELECT
                COUNT(*) as total_fragments,
                SUM(hits) as total_hits,
                COUNT(DISTINCT fragment_type) as fragment_types,
                COUNT(DISTINCT language) as languages
            FROM fragments
        """)
        result = dict(row) if row else {}
        total = result.get("total_fragments", 0)
        result["avg_hits_per_fragment"] = (result.get("total_hits", 0) / total) if total > 0 else 0
        return result

    def preload_common_fragments(self, language: str) -> None:
        """Preload common fragments for a language."""
        common_fragments = self._get_common_fragments_for_language(language)
        for fragment_type, content, metadata in common_fragments:
            if self.get(fragment_type, language) is None:
                self.set(fragment_type, language, content, metadata=metadata)
        if self.logger:
            self.logger.info(f"Preloaded common fragments for {language}")

    @staticmethod
    def _get_common_fragments_for_language(language: str) -> List[tuple]:
        fragments = {
            "python": [
                (
                    "license_header",
                    '"""\nMIT License\n\nCopyright (c) 2026\n\nPermission is hereby granted...\n"""\n',
                    {"license": "MIT", "language": "python"},
                ),
                (
                    "test_boilerplate",
                    (
                        "import pytest\nfrom unittest.mock import Mock, patch\n\n\n"
                        "class Test{{ClassName}}:\n    def setup_method(self):\n        pass\n"
                    ),
                    {"test_framework": "pytest"},
                ),
            ],
        }
        return fragments.get(language, [])

    def list_all(self) -> List[Dict]:
        """List all fragments ordered by hits descending."""
        rows = self._fetch_all("SELECT * FROM fragments ORDER BY hits DESC")
        result = []
        for row in rows:
            try:
                row["metadata"] = json.loads(row["metadata"])
            except Exception:
                row["metadata"] = {}
            result.append(row)
        return result

    def set_favorite(self, key: str, is_favorite: bool) -> None:
        self._execute(
            "UPDATE fragments SET is_favorite = :is_favorite WHERE key = :key",
            {"key": key, "is_favorite": is_favorite},
        )

    # ------------------------------------------------------------------
    # Feature: Few-Shot Dynamic Store
    # ------------------------------------------------------------------

    def store_example(self, language: str, purpose: str, code: str) -> None:
        """Store a validated (purpose, code) pair as a few-shot example."""
        if not purpose or not code:
            return
        self.set(
            fragment_type="successful_task_example",
            language=language,
            content=code,
            context=purpose,
            metadata={"purpose": purpose},
        )

    def get_similar_examples(
        self,
        language: str,
        purpose: str,
        max_examples: int = 2,
    ) -> List[Tuple[str, str]]:
        """Retrieve up to *max_examples* few-shot examples by keyword overlap."""
        rows = self._fetch_all(
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
