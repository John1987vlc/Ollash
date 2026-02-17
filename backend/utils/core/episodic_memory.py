"""
Long-Term Episodic Memory

Cross-project memory store that remembers solutions to specific errors
encountered in past projects, optimizing the Exhaustive Review & Repair phase.

Enhanced with:
- Session tracking for multi-day persistence
- Decision recording for cross-session recall
- Semantic similarity search via embedding vectors
- Async query support
"""

import asyncio
import json
import sqlite3
import uuid
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

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodicEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DecisionRecord:
    """A recorded agent decision for cross-session recall."""

    session_id: str
    decision_type: str
    context: str
    choice: str
    reasoning: str
    outcome: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionRecord":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class EpisodicMemory:
    """Cross-project episodic memory for error solutions.

    Persists to:
    - JSON files per project at {memory_dir}/{project_name}/episodes.json
    - SQLite index at {memory_dir}/episodic_index.db for cross-project queries

    Enhanced with session tracking and decision recording for
    multi-day agent memory persistence.
    """

    def __init__(self, memory_dir: Path, logger: AgentLogger):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        self._db_path = self.memory_dir / "episodic_index.db"
        self._init_db()

    def _init_db(self) -> None:
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

            # Session tracking tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    project_name TEXT DEFAULT '',
                    summary TEXT DEFAULT ''
                )
            """)

            # Decision recording table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    context TEXT NOT NULL,
                    choice TEXT NOT NULL,
                    reasoning TEXT DEFAULT '',
                    outcome TEXT DEFAULT '',
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_decisions_type
                ON decisions(decision_type, outcome)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_decisions_session
                ON decisions(session_id)
            """)

            # Embedding vectors table for semantic search
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episode_embeddings (
                    episode_id INTEGER PRIMARY KEY,
                    embedding_json TEXT NOT NULL,
                    FOREIGN KEY (episode_id) REFERENCES episodes(id)
                )
            """)

    # --------------- Session Management ---------------

    def start_session(self, project_name: str = "") -> str:
        """Start a new session and return its ID."""
        session_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, started_at, project_name) VALUES (?, ?, ?)",
                (session_id, now, project_name),
            )
        self.logger.info(f"Session started: {session_id}")
        return session_id

    def end_session(self, session_id: str, summary: str = "") -> None:
        """End a session."""
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "UPDATE sessions SET ended_at = ?, summary = ? WHERE session_id = ?",
                (now, summary, session_id),
            )
        self.logger.info(f"Session ended: {session_id}")

    # --------------- Decision Recording ---------------

    def record_decision(self, decision: DecisionRecord) -> None:
        """Record an agent decision for cross-session recall."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                """INSERT INTO decisions
                   (session_id, decision_type, context, choice, reasoning, outcome, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision.session_id,
                    decision.decision_type,
                    decision.context,
                    decision.choice,
                    decision.reasoning,
                    decision.outcome,
                    decision.timestamp,
                ),
            )
        self.logger.info(f"Decision recorded: {decision.decision_type} -> {decision.choice}")

    def recall_decisions(
        self,
        decision_type: Optional[str] = None,
        context_keyword: Optional[str] = None,
        max_results: int = 10,
    ) -> List[DecisionRecord]:
        """Recall past decisions, optionally filtered by type or context keyword."""
        query = "SELECT * FROM decisions WHERE 1=1"
        params: list = []

        if decision_type:
            query += " AND decision_type = ?"
            params.append(decision_type)
        if context_keyword:
            query += " AND context LIKE ?"
            params.append(f"%{context_keyword}%")

        query += " ORDER BY timestamp DESC"
        query += f" LIMIT {max_results}"

        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        return [
            DecisionRecord(
                session_id=row["session_id"],
                decision_type=row["decision_type"],
                context=row["context"],
                choice=row["choice"],
                reasoning=row["reasoning"],
                outcome=row["outcome"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]

    # --------------- Episode Recording ---------------

    def record_episode(self, entry: EpisodicEntry) -> None:
        """Record a new episodic memory entry."""
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

    def record_episode_with_embedding(
        self, entry: EpisodicEntry, embedding: List[float]
    ) -> None:
        """Record an episode and store its embedding for semantic search."""
        self.record_episode(entry)

        # Get the last inserted episode ID and store embedding
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute("SELECT MAX(id) FROM episodes").fetchone()
            if row and row[0]:
                conn.execute(
                    "INSERT OR REPLACE INTO episode_embeddings (episode_id, embedding_json) VALUES (?, ?)",
                    (row[0], json.dumps(embedding)),
                )

    # --------------- Querying ---------------

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

        return [self._row_to_entry(row) for row in rows]

    def query_similar_solutions(
        self,
        error_description: str,
        embedding_cache: Any,
        threshold: float = 0.7,
        max_results: int = 5,
    ) -> List[EpisodicEntry]:
        """Find solutions using semantic similarity on error descriptions.

        Uses cosine similarity between the query embedding and stored embeddings.
        Requires an EmbeddingCache instance with access to the embedding model.
        """
        # Get embedding for the query
        query_embedding = embedding_cache.get(error_description)
        if query_embedding is None:
            # Fall back to string matching
            return self.query_solutions(error_description.split(":")[0] if ":" in error_description else error_description)

        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT e.*, ee.embedding_json
                FROM episodes e
                JOIN episode_embeddings ee ON e.id = ee.episode_id
                WHERE e.outcome IN ('success', 'partial')
            """).fetchall()

        # Compute cosine similarities
        scored = []
        for row in rows:
            stored_embedding = json.loads(row["embedding_json"])
            similarity = self._cosine_similarity(query_embedding, stored_embedding)
            if similarity >= threshold:
                scored.append((similarity, row))

        # Sort by similarity descending
        scored.sort(key=lambda x: x[0], reverse=True)

        return [self._row_to_entry(row) for _, row in scored[:max_results]]

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

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
        return self._row_to_entry(row)

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
            total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            total_decisions = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]

        return {
            "total_episodes": total,
            "successful_solutions": successes,
            "success_rate": successes / max(1, total),
            "unique_error_patterns": unique_errors,
            "projects_tracked": unique_projects,
            "total_sessions": total_sessions,
            "total_decisions": total_decisions,
        }

    # --------------- Async Wrappers ---------------

    async def async_query_solutions(
        self, error_type: str, language: str = "", max_results: int = 5
    ) -> List[EpisodicEntry]:
        """Async wrapper for query_solutions using executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.query_solutions, error_type, language, max_results)

    async def async_record_episode(self, entry: EpisodicEntry) -> None:
        """Async wrapper for record_episode using executor."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.record_episode, entry)

    async def async_record_decision(self, decision: DecisionRecord) -> None:
        """Async wrapper for record_decision using executor."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.record_decision, decision)

    # --------------- Helpers ---------------

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> EpisodicEntry:
        """Convert a SQLite Row to an EpisodicEntry."""
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
