"""SQLite store for external MCP server configurations.

Schema
------
mcp_servers : id, name (UNIQUE), transport, command (JSON list),
              url, env (JSON dict), enabled, created_at
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class MCPServerStore:
    """Sync SQLite store for external MCP server configurations."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = str(db_path)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS mcp_servers (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT NOT NULL UNIQUE,
                    transport  TEXT NOT NULL DEFAULT 'stdio',
                    command    TEXT NOT NULL DEFAULT '[]',
                    url        TEXT NOT NULL DEFAULT '',
                    env        TEXT NOT NULL DEFAULT '{}',
                    enabled    INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL
                );
            """)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(
        self,
        name: str,
        transport: str = "stdio",
        command: list[str] | None = None,
        url: str = "",
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "INSERT OR REPLACE INTO mcp_servers"
                " (name, transport, command, url, env, enabled, created_at)"
                " VALUES (?, ?, ?, ?, ?, 1, ?)",
                (name, transport, json.dumps(command or []), url, json.dumps(env or {}), now),
            )
        return self.get(cur.lastrowid)  # type: ignore[arg-type]

    def get(self, server_id: int) -> dict[str, Any] | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM mcp_servers WHERE id = ?", (server_id,)).fetchone()
        return self._row(dict(row)) if row else None

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM mcp_servers WHERE name = ?", (name,)).fetchone()
        return self._row(dict(row)) if row else None

    def list_all(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM mcp_servers ORDER BY created_at ASC").fetchall()
        return [self._row(dict(r)) for r in rows]

    def list_enabled(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM mcp_servers WHERE enabled=1 ORDER BY created_at ASC").fetchall()
        return [self._row(dict(r)) for r in rows]

    def set_enabled(self, name: str, enabled: bool) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute("UPDATE mcp_servers SET enabled=? WHERE name=?", (int(enabled), name))
        return cur.rowcount > 0

    def delete(self, name: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute("DELETE FROM mcp_servers WHERE name=?", (name,))
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row(row: dict) -> dict[str, Any]:
        row["command"] = json.loads(row.get("command") or "[]")
        row["env"] = json.loads(row.get("env") or "{}")
        row["enabled"] = bool(row.get("enabled", 1))
        return row
