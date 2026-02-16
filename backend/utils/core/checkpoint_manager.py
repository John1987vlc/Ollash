"""
Checkpoint & Resume System for AutoAgent

Persists state at each phase boundary so AutoAgent can resume from any phase
after failures. Uses JSON per-project files + SQLite centralized index.
"""

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.agent_logger import AgentLogger


@dataclass
class Checkpoint:
    """Represents a saved checkpoint at a phase boundary."""

    project_name: str
    phase_name: str
    phase_index: int
    timestamp: str
    generated_files: Dict[str, str]
    structure: Dict[str, Any]
    file_paths: List[str]
    readme_content: str
    logic_plan: Dict[str, Any] = field(default_factory=dict)
    exec_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class CheckpointStore:
    """SQLite-backed centralized index for checkpoints."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    phase_name TEXT NOT NULL,
                    phase_index INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    json_path TEXT NOT NULL,
                    file_count INTEGER DEFAULT 0,
                    UNIQUE(project_name, phase_name)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoints_project
                ON checkpoints(project_name, phase_index)
            """)

    def index_checkpoint(self, checkpoint: Checkpoint, json_path: Path) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO checkpoints
                   (project_name, phase_name, phase_index, timestamp, json_path, file_count)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    checkpoint.project_name,
                    checkpoint.phase_name,
                    checkpoint.phase_index,
                    checkpoint.timestamp,
                    str(json_path),
                    len(checkpoint.generated_files),
                ),
            )

    def query(self, project_name: Optional[str] = None, phase_name: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM checkpoints WHERE 1=1"
        params = []
        if project_name:
            query += " AND project_name = ?"
            params.append(project_name)
        if phase_name:
            query += " AND phase_name = ?"
            params.append(phase_name)
        query += " ORDER BY phase_index ASC"

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_latest_phase_index(self, project_name: str) -> Optional[int]:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT MAX(phase_index) FROM checkpoints WHERE project_name = ?",
                (project_name,),
            ).fetchone()
            return row[0] if row and row[0] is not None else None

    def delete_project(self, project_name: str) -> int:
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("DELETE FROM checkpoints WHERE project_name = ?", (project_name,))
            return cursor.rowcount


class CheckpointManager:
    """
    Manages checkpoint persistence for AutoAgent phase resumption.

    Stores:
    - Per-project JSON files at {base_dir}/{project_name}/{phase_name}.json
    - Centralized SQLite index at {base_dir}/index.db
    """

    def __init__(self, base_dir: Path, logger: AgentLogger):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        self.store = CheckpointStore(self.base_dir / "index.db")

    def save(
        self,
        project_name: str,
        phase_name: str,
        phase_index: int,
        generated_files: Dict[str, str],
        structure: Dict[str, Any],
        file_paths: List[str],
        readme_content: str,
        logic_plan: Dict[str, Any] = None,
        exec_params: Dict[str, Any] = None,
    ) -> Path:
        """Save a checkpoint after a successful phase completion."""
        checkpoint = Checkpoint(
            project_name=project_name,
            phase_name=phase_name,
            phase_index=phase_index,
            timestamp=datetime.now().isoformat(),
            generated_files=generated_files,
            structure=structure,
            file_paths=file_paths,
            readme_content=readme_content,
            logic_plan=logic_plan or {},
            exec_params=exec_params or {},
        )

        # Save JSON file
        project_dir = self.base_dir / project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        json_path = project_dir / f"{phase_index:02d}_{phase_name}.json"

        json_path.write_text(json.dumps(checkpoint.to_dict(), indent=2), encoding="utf-8")

        # Update SQLite index
        self.store.index_checkpoint(checkpoint, json_path)

        self.logger.info(f"Checkpoint saved: {project_name}/{phase_name} (phase {phase_index})")
        return json_path

    def load_latest(self, project_name: str) -> Optional[Checkpoint]:
        """Load the most recent checkpoint for a project."""
        latest_index = self.store.get_latest_phase_index(project_name)
        if latest_index is None:
            return None

        rows = self.store.query(project_name=project_name)
        if not rows:
            return None

        latest_row = max(rows, key=lambda r: r["phase_index"])
        json_path = Path(latest_row["json_path"])

        if not json_path.exists():
            self.logger.warning(f"Checkpoint file missing: {json_path}")
            return None

        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.logger.info(
            f"Loaded checkpoint: {project_name}/{latest_row['phase_name']} (phase {latest_row['phase_index']})"
        )
        return Checkpoint.from_dict(data)

    def load_at_phase(self, project_name: str, phase_name: str) -> Optional[Checkpoint]:
        """Load checkpoint for a specific phase."""
        rows = self.store.query(project_name=project_name, phase_name=phase_name)
        if not rows:
            return None

        json_path = Path(rows[0]["json_path"])
        if not json_path.exists():
            return None

        data = json.loads(json_path.read_text(encoding="utf-8"))
        return Checkpoint.from_dict(data)

    def list_checkpoints(self, project_name: str) -> List[Dict[str, Any]]:
        """List all checkpoints for a project."""
        return self.store.query(project_name=project_name)

    def cleanup_old(self, max_age_days: int = 30) -> int:
        """Remove checkpoints older than max_age_days."""
        cutoff = datetime.now().timestamp() - (max_age_days * 86400)
        removed = 0

        for project_dir in self.base_dir.iterdir():
            if not project_dir.is_dir() or project_dir.name == "index.db":
                continue
            for json_file in project_dir.glob("*.json"):
                if json_file.stat().st_mtime < cutoff:
                    json_file.unlink()
                    removed += 1
            if not any(project_dir.iterdir()):
                project_dir.rmdir()

        self.logger.info(f"Cleaned up {removed} old checkpoint files")
        return removed
