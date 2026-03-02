"""
Checkpoint & Resume System for AutoAgent

Persists state at each phase boundary so AutoAgent can resume from any phase
after failures. Uses JSON per-project files + SQLite centralized index.
"""

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.db.engine import make_async_engine, make_session_factory
from backend.utils.core.system.db.sqlite_manager import AsyncDatabaseManager


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
    """SQLAlchemy async-backed centralized index for checkpoints."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
    ):
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            if not db_path:
                db_path = Path(".ollash/checkpoints/index.db")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            engine = make_async_engine(db_path)
            self._session_factory = make_session_factory(engine)

        self.db = AsyncDatabaseManager(self._session_factory)

    async def _init_db(self) -> None:
        """Initialize checkpoints table (idempotent, call once at startup)."""
        await self.db.execute("""
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
        await self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_checkpoints_project ON checkpoints(project_name, phase_index)"
        )

    async def index_checkpoint(self, checkpoint: "Checkpoint", json_path: Path) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO checkpoints "
            "(project_name, phase_name, phase_index, timestamp, json_path, file_count) "
            "VALUES (:p0, :p1, :p2, :p3, :p4, :p5)",
            (
                checkpoint.project_name,
                checkpoint.phase_name,
                checkpoint.phase_index,
                checkpoint.timestamp,
                str(json_path),
                len(checkpoint.generated_files),
            ),
        )

    async def query(
        self,
        project_name: Optional[str] = None,
        phase_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM checkpoints WHERE 1=1"
        params: Dict[str, Any] = {}
        if project_name:
            query += " AND project_name = :project_name"
            params["project_name"] = project_name
        if phase_name:
            query += " AND phase_name = :phase_name"
            params["phase_name"] = phase_name
        query += " ORDER BY phase_index ASC"
        return await self.db.fetch_all(query, params)

    async def get_latest_phase_index(self, project_name: str) -> Optional[int]:
        row = await self.db.fetch_one(
            "SELECT MAX(phase_index) as max_idx FROM checkpoints WHERE project_name = :p0",
            (project_name,),
        )
        return row["max_idx"] if row and row["max_idx"] is not None else None

    async def delete_project(self, project_name: str) -> None:
        await self.db.execute("DELETE FROM checkpoints WHERE project_name = :p0", (project_name,))


class CheckpointManager:
    """
    Manages checkpoint persistence for AutoAgent phase resumption.

    Stores:
    - Per-project JSON files at {base_dir}/{project_name}/{phase_name}.json
    - Centralized async SQLite index via CheckpointStore
    """

    def __init__(
        self,
        base_dir: Path,
        logger: AgentLogger,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
    ):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        self.store = CheckpointStore(
            db_path=self.base_dir / "index.db",
            session_factory=session_factory,
        )

    async def save(
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

        project_dir = self.base_dir / project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        json_path = project_dir / f"{phase_index:02d}_{phase_name}.json"

        json_path.write_text(json.dumps(checkpoint.to_dict(), indent=2), encoding="utf-8")

        await self.store.index_checkpoint(checkpoint, json_path)

        self.logger.info(f"Checkpoint saved: {project_name}/{phase_name} (phase {phase_index})")
        return json_path

    async def load_latest(self, project_name: str) -> Optional[Checkpoint]:
        """Load the most recent checkpoint for a project."""
        latest_index = await self.store.get_latest_phase_index(project_name)
        if latest_index is None:
            return None

        rows = await self.store.query(project_name=project_name)
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

    async def load_at_phase(self, project_name: str, phase_name: str) -> Optional[Checkpoint]:
        """Load checkpoint for a specific phase."""
        rows = await self.store.query(project_name=project_name, phase_name=phase_name)
        if not rows:
            return None

        json_path = Path(rows[0]["json_path"])
        if not json_path.exists():
            return None

        data = json.loads(json_path.read_text(encoding="utf-8"))
        return Checkpoint.from_dict(data)

    async def list_checkpoints(self, project_name: str) -> List[Dict[str, Any]]:
        """List all checkpoints for a project."""
        return await self.store.query(project_name=project_name)

    # ------------------------------------------------------------------
    # DAG checkpoint methods (Point 2 — Resilience)
    # ------------------------------------------------------------------

    async def save_dag(
        self,
        project_name: str,
        dag_dict: Dict[str, Any],
        blackboard_dict: Dict[str, Any],
    ) -> Path:
        """Serialise a live TaskDAG + Blackboard snapshot to disk (non-blocking).

        Written to ``.ollash/checkpoints/{project_name}/dag_latest.json``.
        The file is overwritten on every call so it always reflects the
        most recent consistent state.

        Args:
            project_name:    Short project identifier.
            dag_dict:        Result of ``TaskDAG.to_dict()``.
            blackboard_dict: Result of ``Blackboard.snapshot_serializable()``.

        Returns:
            Path to the written JSON file.
        """
        payload = {
            "project_name": project_name,
            "timestamp": datetime.now().isoformat(),
            "dag": dag_dict,
            "blackboard": blackboard_dict,
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False)

        def _write() -> Path:
            project_dir = self.base_dir / project_name
            project_dir.mkdir(parents=True, exist_ok=True)
            dag_path = project_dir / "dag_latest.json"
            dag_path.write_text(text, encoding="utf-8")
            return dag_path

        dag_path = await asyncio.to_thread(_write)
        self.logger.debug(f"[CheckpointManager] DAG checkpoint saved: {dag_path}")
        return dag_path

    async def load_dag(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Load the latest DAG checkpoint for *project_name* (non-blocking).

        Returns:
            The parsed JSON dict with keys ``dag`` and ``blackboard``,
            or None if no checkpoint exists.
        """
        dag_path = self.base_dir / project_name / "dag_latest.json"

        def _read() -> Optional[str]:
            return dag_path.read_text(encoding="utf-8") if dag_path.exists() else None

        raw = await asyncio.to_thread(_read)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            self.logger.info(
                f"[CheckpointManager] DAG checkpoint loaded: {project_name} "
                f"(saved at {data.get('timestamp', 'unknown')})"
            )
            return data
        except Exception as exc:
            self.logger.warning(f"[CheckpointManager] Failed to load DAG checkpoint: {exc}")
            return None

    async def cleanup_old(self, max_age_days: int = 30) -> int:
        """Remove checkpoints older than max_age_days (non-blocking)."""

        def _cleanup() -> int:
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
            return removed

        removed = await asyncio.to_thread(_cleanup)
        self.logger.info(f"Cleaned up {removed} old checkpoint files")
        return removed
