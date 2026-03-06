"""
DecisionBlackboard — Lightweight SQLite-backed key-value store for design decisions.

Stores architectural design decisions made during project generation so they can be
retrieved and injected into future LLM prompts, enabling consistency across phases
even when using small models (≤4B) that lack long-range attention.

Storage: .ollash/decisions.db (SQLite, single table, thread-safe via connection-per-call).
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class DecisionBlackboard:
    """Stores and retrieves architectural design decisions across pipeline phases.

    Decisions are stored as key-value pairs with optional context in a local SQLite
    database. Using a connection-per-call pattern makes it safe to use from multiple
    threads (e.g., parallel DeveloperAgent pool).

    Args:
        db_path: Absolute path to the SQLite database file.
                 Parent directory is created automatically if it does not exist.

    Example::

        board = DecisionBlackboard(Path(".ollash/decisions.db"))
        board.record_decision("database", "SQLite", "Chosen for simplicity")
        board.record_decision("auth_strategy", "JWT")
        print(board.format_for_prompt())
        # ## ESTABLISHED DESIGN DECISIONS
        # - database: SQLite (Chosen for simplicity)
        # - auth_strategy: JWT
    """

    _TABLE_DDL: str = (
        "CREATE TABLE IF NOT EXISTS decisions ("
        "    key          TEXT PRIMARY KEY, "
        "    value        TEXT NOT NULL, "
        "    context      TEXT DEFAULT '', "
        "    recorded_at  TEXT NOT NULL"
        ")"
    )

    _TASKS_TABLE_DDL: str = (
        "CREATE TABLE IF NOT EXISTS tasks ("
        "    id           TEXT PRIMARY KEY, "
        "    title        TEXT NOT NULL, "
        "    description  TEXT, "
        "    file_path    TEXT, "
        "    task_type    TEXT, "
        "    dependencies TEXT, "
        "    status       TEXT DEFAULT 'todo', "
        "    recorded_at  TEXT NOT NULL"
        ")"
    )

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent read performance
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(self._TABLE_DDL)
            conn.execute(self._TASKS_TABLE_DDL)

    # ------------------------------------------------------------------
    # Public API - Decisions
    # ------------------------------------------------------------------

    def record_decision(self, key: str, value: str, context: str = "") -> None:
        """Insert or update a design decision."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO decisions (key, value, context, recorded_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET "
                "    value=excluded.value, "
                "    context=excluded.context, "
                "    recorded_at=excluded.recorded_at",
                (key, value, context, now),
            )

    # Alias for record_decision if needed
    def store(self, key: str, value: str, context: str = "") -> None:
        self.record_decision(key, value, context)

    def get_decision(self, key: str) -> Optional[str]:
        """Return the value for a specific key, or *None* if not found."""
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM decisions WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    # ------------------------------------------------------------------
    # Public API - Tasks (Deterministic Tasking)
    # ------------------------------------------------------------------

    def record_task(
        self,
        task_id: str,
        title: str,
        description: str = "",
        file_path: str = "",
        task_type: str = "create_file",
        dependencies: List[str] = None,
        status: str = "todo",
    ) -> None:
        """Record a single task in the blackboard. Used to ensure all files are tracked."""
        import json

        now = datetime.utcnow().isoformat()
        deps_json = json.dumps(dependencies or [])
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tasks (id, title, description, file_path, task_type, dependencies, status, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "    title=excluded.title, "
                "    description=excluded.description, "
                "    file_path=excluded.file_path, "
                "    task_type=excluded.task_type, "
                "    dependencies=excluded.dependencies, "
                "    status=excluded.status, "
                "    recorded_at=excluded.recorded_at",
                (task_id, title, description, file_path, task_type, deps_json, status, now),
            )

    def get_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve tasks, optionally filtered by status."""
        import json

        query = "SELECT * FROM tasks"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY recorded_at"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        result = []
        for row in rows:
            d = dict(row)
            try:
                d["dependencies"] = json.loads(d["dependencies"])
            except Exception:
                d["dependencies"] = []
            result.append(d)
        return result

    def get_all_decisions(self) -> List[Dict[str, Any]]:
        """Return all recorded decisions ordered by insertion time.

        Returns:
            List of dicts with keys: ``key``, ``value``, ``context``, ``recorded_at``.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, value, context, recorded_at FROM decisions ORDER BY recorded_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def format_for_prompt(self) -> str:
        """Format all decisions as a compact string for LLM prompt injection.

        Returns an empty string if no decisions have been recorded yet, so callers
        can safely concatenate the result without conditional checks.

        Returns:
            Multi-line string suitable for inclusion in a system prompt, or ``""``.

        Example output::

            ## ESTABLISHED DESIGN DECISIONS
            - database_choice: SQLite (Chosen for simplicity)
            - auth_strategy: JWT (Stateless, no session state needed)
        """
        decisions = self.get_all_decisions()
        if not decisions:
            return ""
        lines = ["## ESTABLISHED DESIGN DECISIONS"]
        for d in decisions:
            ctx_part = f" ({d['context']})" if d.get("context") else ""
            lines.append(f"- {d['key']}: {d['value']}{ctx_part}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Delete all stored decisions (mainly for testing)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM decisions")
