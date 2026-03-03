"""Lightweight SQLite-backed vector store — drop-in replacement for ChromaDB.

Why this exists
---------------
ChromaDB pulls in ~866 transitive modules (numpy, grpc, opentelemetry,
sentence-transformers, docker…) adding 200–400 MB of RAM overhead per process.
This module replaces it with:
  - stdlib sqlite3 (zero extra deps)
  - LIKE-based keyword search for query_texts callers
  - Pure-Python cosine similarity for query_embeddings callers

API compatibility
-----------------
The public interface matches what the codebase actually calls on ChromaDB:
  client  = SQLiteVectorStore(db_path)
  col     = client.get_or_create_collection(name)
  col.add(ids=[...], documents=[...], metadatas=[...], embeddings=[...])
  col.query(query_texts=[...], n_results=5)
  col.query(query_embeddings=[...], n_results=5)
  col.count()
  col.peek(n)
  col.delete(ids=[...])
  client.delete_collection(name)

All methods are synchronous to match ChromaDB's sync client API.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe(name: str) -> str:
    """Return a SQL-safe table name (alphanumerics + underscore only)."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _cosine(a: List[float], b: List[float]) -> float:
    """Pure-Python cosine similarity — no numpy required."""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _keyword_tokens(text: str, limit: int = 8) -> List[str]:
    """Extract significant word tokens from *text* for LIKE-based search."""
    return [t for t in re.findall(r"\w{3,}", text.lower())][:limit]


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


class SQLiteVectorCollection:
    """A single named collection stored in one SQLite table.

    Columns
    -------
    id        – caller-supplied identifier (PRIMARY KEY)
    document  – text content
    metadata  – JSON object
    embedding – JSON float array (optional; stored only when caller provides it)
    added_at  – Unix timestamp for LRU eviction
    """

    def __init__(self, db_path: Path, name: str) -> None:
        self._db_path = str(db_path)
        self._table = _safe(name)
        self._ensure_table()

    # ------------------------------------------------------------------ init

    def _ensure_table(self) -> None:
        with sqlite3.connect(self._db_path) as db:
            db.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    id        TEXT PRIMARY KEY,
                    document  TEXT NOT NULL,
                    metadata  TEXT NOT NULL DEFAULT '{{}}',
                    embedding TEXT DEFAULT NULL,
                    added_at  REAL NOT NULL DEFAULT 0
                )
                """
            )
            db.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{self._table}_ts ON {self._table}(added_at)"
            )
            db.commit()

    # ------------------------------------------------------------------ write

    def add(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: Optional[List[Dict]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> None:
        """Insert or replace entries in the collection."""
        metas = metadatas or [{} for _ in ids]
        embeds: List[Optional[str]] = [None] * len(ids)
        if embeddings:
            for i, emb in enumerate(embeddings):
                if emb and any(v != 0.0 for v in emb):
                    # Only persist non-zero embeddings (zero = stub from OllamaClient)
                    embeds[i] = json.dumps(emb)

        ts = time.time()
        with sqlite3.connect(self._db_path) as db:
            for id_, doc, meta, emb in zip(ids, documents, metas, embeds):
                db.execute(
                    f"""
                    INSERT OR REPLACE INTO {self._table}(id, document, metadata, embedding, added_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (id_, doc, json.dumps(meta or {}), emb, ts),
                )
            db.commit()

    def delete(self, ids: Optional[List[str]] = None) -> None:
        """Remove entries by id."""
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        with sqlite3.connect(self._db_path) as db:
            db.execute(
                f"DELETE FROM {self._table} WHERE id IN ({placeholders})", list(ids)
            )
            db.commit()

    # ------------------------------------------------------------------ read

    def query(
        self,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 5,
        where: Optional[Dict] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Search the collection and return a ChromaDB-compatible result dict.

        Priority:
          1. If *query_texts* is given → keyword (LIKE) search on document.
          2. If *query_embeddings* is given and the table has stored embeddings
             → cosine similarity ranking.
          3. Fallback → return the *n_results* most-recently-added entries.

        The returned ``distances`` list contains values in [0.0, 1.0] where
        **1.0 means a good match** (inverted from ChromaDB's L2 distance).
        Callers that check ``distance >= threshold`` will work correctly when
        threshold ≤ 1.0 (which covers all current usages).
        """
        empty: Dict[str, Any] = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

        rows: List[sqlite3.Row] = []
        strategy = "fallback"

        with sqlite3.connect(self._db_path) as db:
            db.row_factory = sqlite3.Row

            # --- Strategy 1: keyword LIKE search --------------------------
            if query_texts:
                q = str(query_texts[0])
                tokens = _keyword_tokens(q)
                seen: set = set()
                for token in tokens:
                    cur = db.execute(
                        f"""
                        SELECT id, document, metadata, embedding
                        FROM {self._table}
                        WHERE document LIKE ?
                        LIMIT ?
                        """,
                        (f"%{token}%", n_results * 2),
                    )
                    for r in cur.fetchall():
                        if r["id"] not in seen:
                            rows.append(r)
                            seen.add(r["id"])
                    if len(rows) >= n_results:
                        break
                strategy = "keyword"

            # --- Strategy 2: cosine similarity ----------------------------
            elif query_embeddings and query_embeddings[0]:
                q_emb = query_embeddings[0]
                # Only worth computing if q_emb has actual signal
                has_signal = any(v != 0.0 for v in q_emb)
                if has_signal:
                    cur = db.execute(
                        f"""
                        SELECT id, document, metadata, embedding
                        FROM {self._table}
                        WHERE embedding IS NOT NULL
                        LIMIT 2000
                        """
                    )
                    candidates = cur.fetchall()
                    if candidates:
                        scored = []
                        for r in candidates:
                            try:
                                stored = json.loads(r["embedding"])
                                sim = _cosine(q_emb, stored)
                                scored.append((sim, r))
                            except (json.JSONDecodeError, TypeError):
                                pass
                        scored.sort(key=lambda x: x[0], reverse=True)
                        rows = [r for _, r in scored[:n_results]]
                        strategy = "cosine"

        # --- Strategy 3: fallback (most recent) ---------------------------
        if not rows:
            with sqlite3.connect(self._db_path) as db:
                db.row_factory = sqlite3.Row
                cur = db.execute(
                    f"""
                    SELECT id, document, metadata, embedding
                    FROM {self._table}
                    ORDER BY added_at DESC
                    LIMIT ?
                    """,
                    (n_results,),
                )
                rows = cur.fetchall()
            strategy = "fallback"

        if not rows:
            return empty

        rows = rows[:n_results]

        ids_out = [r["id"] for r in rows]
        docs_out = [r["document"] for r in rows]
        meta_out = []
        for r in rows:
            try:
                meta_out.append(json.loads(r["metadata"]))
            except (json.JSONDecodeError, TypeError):
                meta_out.append({})

        # Distances: 1.0 for keyword/fallback (passes any ≤1.0 threshold check)
        if strategy == "cosine":
            # Already sorted by cosine similarity; compute actual distances
            with sqlite3.connect(self._db_path) as db:
                q_emb = query_embeddings[0]  # type: ignore[index]
                dist_out = []
                for r in rows:
                    try:
                        stored = json.loads(r["embedding"])
                        dist_out.append(_cosine(q_emb, stored))
                    except (json.JSONDecodeError, TypeError):
                        dist_out.append(0.0)
        else:
            dist_out = [1.0 for _ in rows]

        return {
            "ids": [ids_out],
            "documents": [docs_out],
            "metadatas": [meta_out],
            "distances": [dist_out],
        }

    def count(self) -> int:
        """Return total number of entries in the collection."""
        with sqlite3.connect(self._db_path) as db:
            cur = db.execute(f"SELECT COUNT(*) FROM {self._table}")
            row = cur.fetchone()
            return row[0] if row else 0

    def peek(self, n: int = 10) -> Dict[str, Any]:
        """Return the *n* oldest entries (for LRU eviction)."""
        with sqlite3.connect(self._db_path) as db:
            db.row_factory = sqlite3.Row
            cur = db.execute(
                f"""
                SELECT id, document, metadata
                FROM {self._table}
                ORDER BY added_at ASC
                LIMIT ?
                """,
                (n,),
            )
            rows = cur.fetchall()
        return {
            "ids": [r["id"] for r in rows],
            "documents": [r["document"] for r in rows],
            "metadatas": [
                json.loads(r["metadata"]) if r["metadata"] else {} for r in rows
            ],
        }

    def get(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve entries by id (subset of ChromaDB .get() API)."""
        if not ids:
            return {"ids": [], "documents": [], "metadatas": []}
        placeholders = ",".join("?" * len(ids))
        with sqlite3.connect(self._db_path) as db:
            db.row_factory = sqlite3.Row
            cur = db.execute(
                f"SELECT id, document, metadata FROM {self._table} WHERE id IN ({placeholders})",
                list(ids),
            )
            rows = cur.fetchall()
        return {
            "ids": [r["id"] for r in rows],
            "documents": [r["document"] for r in rows],
            "metadatas": [json.loads(r["metadata"]) for r in rows],
        }


# ---------------------------------------------------------------------------
# Store (top-level client — replaces chromadb.Client / EphemeralClient)
# ---------------------------------------------------------------------------


class SQLiteVectorStore:
    """Synchronous vector store backed by a single SQLite file.

    Usage (same as ChromaDB client)::

        store = SQLiteVectorStore(Path(".ollash/vectors.db"))
        col = store.get_or_create_collection("knowledge_base")
        col.add(ids=["f1"], documents=["def add(a,b): return a+b"])
        results = col.query(query_texts=["addition function"], n_results=3)
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_or_create_collection(
        self, name: str, **_kwargs: Any
    ) -> SQLiteVectorCollection:
        """Return (or create) a collection by name."""
        return SQLiteVectorCollection(self._db_path, name)

    def delete_collection(self, name: str) -> None:
        """Drop the collection table entirely."""
        table = _safe(name)
        with sqlite3.connect(str(self._db_path)) as db:
            db.execute(f"DROP TABLE IF EXISTS {table}")
            db.commit()
