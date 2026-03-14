"""Pipeline store — SQLite-backed pipeline definitions and run history.

Schema
------
pipelines : id, name, description, phases (JSON list), created_at, updated_at
runs      : id, pipeline_id FK, project_path, status, started_at, finished_at,
            log (JSON list of events)
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class PipelineStore:
    """Sync SQLite store for pipeline definitions and execution runs."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = str(db_path)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS pipelines (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    phases      TEXT NOT NULL DEFAULT '[]',
                    builtin     INTEGER NOT NULL DEFAULT 0,
                    created_at  REAL NOT NULL,
                    updated_at  REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    pipeline_id  INTEGER NOT NULL REFERENCES pipelines(id) ON DELETE CASCADE,
                    project_path TEXT NOT NULL DEFAULT '',
                    status       TEXT NOT NULL DEFAULT 'pending',
                    started_at   REAL,
                    finished_at  REAL,
                    log          TEXT NOT NULL DEFAULT '[]'
                );
            """)

    # ------------------------------------------------------------------
    # Pipelines CRUD
    # ------------------------------------------------------------------

    def create_pipeline(
        self,
        name: str,
        phases: list[str],
        description: str = "",
        builtin: bool = False,
    ) -> dict[str, Any]:
        now = time.time()
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "INSERT INTO pipelines (name, description, phases, builtin, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (name, description, json.dumps(phases), int(builtin), now, now),
            )
            new_id = cur.lastrowid
        return self.get_pipeline(new_id)  # type: ignore[arg-type]

    def get_pipeline(self, pipeline_id: int) -> dict[str, Any] | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM pipelines WHERE id = ?", (pipeline_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_pipeline(dict(row))

    def list_pipelines(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM pipelines ORDER BY builtin DESC, created_at ASC").fetchall()
        return [self._row_to_pipeline(dict(r)) for r in rows]

    def update_pipeline(
        self,
        pipeline_id: int,
        name: str | None = None,
        phases: list[str] | None = None,
        description: str | None = None,
    ) -> dict[str, Any] | None:
        pipeline = self.get_pipeline(pipeline_id)
        if pipeline is None:
            return None
        now = time.time()
        new_name = name if name is not None else pipeline["name"]
        new_desc = description if description is not None else pipeline["description"]
        new_phases = phases if phases is not None else pipeline["phases"]
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE pipelines SET name=?, description=?, phases=?, updated_at=? WHERE id=?",
                (new_name, new_desc, json.dumps(new_phases), now, pipeline_id),
            )
        return self.get_pipeline(pipeline_id)

    def delete_pipeline(self, pipeline_id: int) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute("DELETE FROM pipelines WHERE id = ? AND builtin = 0", (pipeline_id,))
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def create_run(self, pipeline_id: int, project_path: str = "") -> dict[str, Any]:
        now = time.time()
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "INSERT INTO runs (pipeline_id, project_path, status, started_at, log)"
                " VALUES (?, ?, 'running', ?, '[]')",
                (pipeline_id, project_path, now),
            )
            run_id = cur.lastrowid
        return self.get_run(run_id)  # type: ignore[arg-type]

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_run(dict(row))

    def append_log(self, run_id: int, event: dict[str, Any]) -> None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT log FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                return
            events: list = json.loads(row[0])
            events.append(event)
            conn.execute(
                "UPDATE runs SET log = ? WHERE id = ?",
                (json.dumps(events), run_id),
            )

    def finish_run(self, run_id: int, status: str = "completed") -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE runs SET status = ?, finished_at = ? WHERE id = ?",
                (status, time.time(), run_id),
            )

    def list_runs(self, pipeline_id: int, limit: int = 20) -> list[dict[str, Any]]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM runs WHERE pipeline_id = ? ORDER BY started_at DESC LIMIT ?",
                (pipeline_id, limit),
            ).fetchall()
        return [self._row_to_run(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Seed built-in pipelines
    # ------------------------------------------------------------------

    def seed_builtins(self) -> None:
        """Insert predefined pipelines once if the table is empty."""
        with sqlite3.connect(self._db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM pipelines WHERE builtin=1").fetchone()[0]
        if count > 0:
            return
        builtins = [
            {
                "name": "Quick Review",
                "description": "Security scan + senior code review. Fast quality gate.",
                "phases": ["SecurityScanPhase", "SeniorReviewPhase"],
            },
            {
                "name": "Refactor",
                "description": "Re-plan logic, refine files, then exhaustive repair pass.",
                "phases": ["LogicPlanningPhase", "FileRefinementPhase", "ExhaustiveReviewRepairPhase"],
            },
            {
                "name": "Full Test Suite",
                "description": "Generate test plan, run tests, verify coverage.",
                "phases": ["TestPlanningPhase", "GenerationExecutionPhase", "VerificationPhase"],
            },
            {
                "name": "Full Pipeline",
                "description": "Complete AutoAgent pipeline — all phases.",
                "phases": [
                    "ReadmeGenerationPhase",
                    "StructureGenerationPhase",
                    "LogicPlanningPhase",
                    "StructurePreReviewPhase",
                    "EmptyFileScaffoldingPhase",
                    "FileContentGenerationPhase",
                    "FileRefinementPhase",
                    "JavaScriptOptimizationPhase",
                    "VerificationPhase",
                    "CodeQuarantinePhase",
                    "SecurityScanPhase",
                    "DependencyReconciliationPhase",
                    "GenerationExecutionPhase",
                    "InfrastructureGenerationPhase",
                    "FinalReviewPhase",
                    "SeniorReviewPhase",
                ],
            },
        ]
        for b in builtins:
            self.create_pipeline(b["name"], b["phases"], b["description"], builtin=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_pipeline(row: dict) -> dict[str, Any]:
        row["phases"] = json.loads(row.get("phases") or "[]")
        row["builtin"] = bool(row.get("builtin", 0))
        return row

    @staticmethod
    def _row_to_run(row: dict) -> dict[str, Any]:
        row["log"] = json.loads(row.get("log") or "[]")
        return row
