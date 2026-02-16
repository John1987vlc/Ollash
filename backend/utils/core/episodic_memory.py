"""
Long-Term Episodic Memory

Cross-project memory store that remembers solutions to specific errors
encountered in past projects, optimizing the Exhaustive Review & Repair phase.
"""

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.agent_logger import AgentLogger


@dataclass
class EpisodicEntry:
    """A single episodic memory entry linking an error to its solution."""

    project_name: str
    phase_name: str
    error_type: str
    error_pattern_id: str
    error_description: str
    solution_applied: str
    outcome: str  # "success", "partial", "failure"
    language: str = "unknown"
    file_path: str = ""
    timestamp: str = ""
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodicEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class EpisodicMemory:
    """Cross-project episodic memory for error solutions.

    Persists to:
    - JSON files per project at {memory_dir}/{project_name}/episodes.json
    - SQLite index at {memory_dir}/episodic_index.db for cross-project queries
    """

    def __init__(self, memory_dir: Path, logger: AgentLogger):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        self._db_path = self.memory_dir / "episodic_index.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    phase_name TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    error_pattern_id TEXT NOT NULL,
                    error_description TEXT,
                    solution_applied TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    language TEXT DEFAULT 'unknown',
                    file_path TEXT DEFAULT '',
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_error
                ON episodes(error_type, language, outcome)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_pattern
                ON episodes(error_pattern_id, outcome)
            """)

    def record_episode(self, entry: EpisodicEntry) -> None:
        """Record a new episodic memory entry."""
        # Save to SQLite index
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                """INSERT INTO episodes
                   (project_name, phase_name, error_type, error_pattern_id,
                    error_description, solution_applied, outcome, language,
                    file_path, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.project_name,
                    entry.phase_name,
                    entry.error_type,
                    entry.error_pattern_id,
                    entry.error_description,
                    entry.solution_applied,
                    entry.outcome,
                    entry.language,
                    entry.file_path,
                    entry.timestamp,
                ),
            )

        # Save to per-project JSON
        project_dir = self.memory_dir / entry.project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        episodes_file = project_dir / "episodes.json"

        episodes = []
        if episodes_file.exists():
            episodes = json.loads(episodes_file.read_text(encoding="utf-8"))
        episodes.append(entry.to_dict())
        episodes_file.write_text(json.dumps(episodes, indent=2), encoding="utf-8")

        self.logger.info(
            f"Recorded episode: {entry.error_type} in {entry.project_name}/{entry.phase_name} -> {entry.outcome}"
        )

    def query_solutions(
        self,
        error_type: str,
        language: str = "",
        max_results: int = 5,
    ) -> List[EpisodicEntry]:
        """Query for successful solutions to a given error type."""
        query = """
            SELECT * FROM episodes
            WHERE error_type = ? AND outcome IN ('success', 'partial')
        """
        params: list = [error_type]

        if language:
            query += " AND language = ?"
            params.append(language)

        query += " ORDER BY CASE outcome WHEN 'success' THEN 0 ELSE 1 END, timestamp DESC"
        query += f" LIMIT {max_results}"

        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        entries = []
        for row in rows:
            entries.append(
                EpisodicEntry(
                    project_name=row["project_name"],
                    phase_name=row["phase_name"],
                    error_type=row["error_type"],
                    error_pattern_id=row["error_pattern_id"],
                    error_description=row["error_description"] or "",
                    solution_applied=row["solution_applied"],
                    outcome=row["outcome"],
                    language=row["language"],
                    file_path=row["file_path"],
                    timestamp=row["timestamp"],
                )
            )

        return entries

    def get_best_solution(self, error_pattern_id: str) -> Optional[EpisodicEntry]:
        """Get the best known solution for a specific error pattern."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT * FROM episodes
                   WHERE error_pattern_id = ? AND outcome = 'success'
                   ORDER BY timestamp DESC LIMIT 1""",
                (error_pattern_id,),
            ).fetchone()

        if not row:
            return None

        return EpisodicEntry(
            project_name=row["project_name"],
            phase_name=row["phase_name"],
            error_type=row["error_type"],
            error_pattern_id=row["error_pattern_id"],
            error_description=row["error_description"] or "",
            solution_applied=row["solution_applied"],
            outcome=row["outcome"],
            language=row["language"],
            file_path=row["file_path"],
            timestamp=row["timestamp"],
        )

    def get_success_rate(self, error_pattern_id: str) -> float:
        """Get the success rate for solutions to a specific error pattern."""
        with sqlite3.connect(str(self._db_path)) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM episodes WHERE error_pattern_id = ?",
                (error_pattern_id,),
            ).fetchone()[0]

            if total == 0:
                return 0.0

            successes = conn.execute(
                "SELECT COUNT(*) FROM episodes WHERE error_pattern_id = ? AND outcome = 'success'",
                (error_pattern_id,),
            ).fetchone()[0]

            return successes / total

    def get_statistics(self) -> Dict[str, Any]:
        """Get overall episodic memory statistics."""
        with sqlite3.connect(str(self._db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            successes = conn.execute("SELECT COUNT(*) FROM episodes WHERE outcome = 'success'").fetchone()[0]
            unique_errors = conn.execute("SELECT COUNT(DISTINCT error_pattern_id) FROM episodes").fetchone()[0]
            unique_projects = conn.execute("SELECT COUNT(DISTINCT project_name) FROM episodes").fetchone()[0]

        return {
            "total_episodes": total,
            "successful_solutions": successes,
            "success_rate": successes / max(1, total),
            "unique_error_patterns": unique_errors,
            "projects_tracked": unique_projects,
        }
