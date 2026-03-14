"""Local user store — SQLite-backed users and API keys.

Uses stdlib sqlite3 (sync) consistent with other in-process stores
(SQLiteVectorStore, FragmentCache, EpisodicMemory).

Schema
------
users     : id, username (UNIQUE), hashed_password, created_at
api_keys  : id, user_id FK→users, key_hash (UNIQUE), name, created_at, last_used
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class UserStore:
    """Sync SQLite-backed user and API key repository."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = str(db_path)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        with sqlite3.connect(self._db_path) as db:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    username         TEXT    UNIQUE NOT NULL,
                    hashed_password  TEXT    NOT NULL,
                    created_at       REAL    NOT NULL DEFAULT 0
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id     INTEGER NOT NULL,
                    key_hash    TEXT    UNIQUE NOT NULL,
                    name        TEXT    NOT NULL DEFAULT 'default',
                    created_at  REAL    NOT NULL DEFAULT 0,
                    last_used   REAL    DEFAULT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            db.commit()

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def create_user(self, username: str, hashed_password: str) -> int:
        """Insert a new user and return the auto-generated id."""
        with sqlite3.connect(self._db_path) as db:
            cur = db.execute(
                "INSERT INTO users(username, hashed_password, created_at) VALUES (?, ?, ?)",
                (username, hashed_password, time.time()),
            )
            db.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def get_user_by_username(self, username: str) -> dict | None:
        with sqlite3.connect(self._db_path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT id, username, hashed_password, created_at FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict | None:
        with sqlite3.connect(self._db_path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT id, username, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def count_users(self) -> int:
        with sqlite3.connect(self._db_path) as db:
            return db.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    # ------------------------------------------------------------------
    # API keys
    # ------------------------------------------------------------------

    def create_api_key(self, user_id: int, key_hash: str, name: str = "default") -> int:
        """Store a hashed API key and return the key id."""
        with sqlite3.connect(self._db_path) as db:
            cur = db.execute(
                "INSERT INTO api_keys(user_id, key_hash, name, created_at) VALUES (?, ?, ?, ?)",
                (user_id, key_hash, name, time.time()),
            )
            db.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def list_api_keys(self, user_id: int) -> list[dict]:
        with sqlite3.connect(self._db_path) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT id, name, created_at, last_used FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_api_key(self, key_id: int, user_id: int) -> bool:
        """Delete a key by id, scoped to *user_id* so users can't delete others' keys."""
        with sqlite3.connect(self._db_path) as db:
            cur = db.execute(
                "DELETE FROM api_keys WHERE id = ? AND user_id = ?",
                (key_id, user_id),
            )
            db.commit()
            return cur.rowcount > 0

    def verify_api_key(self, key_hash: str) -> dict | None:
        """Look up a key by its hash, update last_used, return {user_id, username} or None."""
        with sqlite3.connect(self._db_path) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                """
                SELECT ak.user_id, u.username
                FROM api_keys ak
                JOIN users u ON ak.user_id = u.id
                WHERE ak.key_hash = ?
                """,
                (key_hash,),
            ).fetchone()
            if row:
                db.execute(
                    "UPDATE api_keys SET last_used = ? WHERE key_hash = ?",
                    (time.time(), key_hash),
                )
                db.commit()
                return dict(row)
            return None
