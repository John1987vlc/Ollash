import sqlite3
import logging
from pathlib import Path
from typing import Any, List, Dict, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Base class for SQLite database management using WAL mode.
    Handles connections, basic migrations, and thread-safe access.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_connection()

    def _init_connection(self):
        """Initialize database with WAL mode for better concurrency."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute("PRAGMA foreign_keys=ON;")
        except Exception as e:
            logger.error(f"Failed to initialize DB at {self.db_path}: {e}")

    @contextmanager
    def get_connection(self):
        """Yields a connection object."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error in {self.db_path.name}: {e}")
            raise
        finally:
            conn.close()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query and return the cursor."""
        with self.get_connection() as conn:
            return conn.execute(query, params)

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all results as dictionaries."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch a single result as a dictionary."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def upsert(self, table: str, data: Dict[str, Any], unique_keys: List[str]):
        """Generic upsert helper (SQLite 3.24+ style)."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        updates = ", ".join([f"{k}=excluded.{k}" for k in data.keys() if k not in unique_keys])

        query = f"""
            INSERT INTO {table} ({columns}) VALUES ({placeholders})
            ON CONFLICT({", ".join(unique_keys)}) DO UPDATE SET {updates}
        """
        self.execute(query, tuple(data.values()))
