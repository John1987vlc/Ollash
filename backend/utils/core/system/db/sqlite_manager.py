import sqlite3
import logging
from pathlib import Path
from typing import Any, List, Dict, Optional
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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


class AsyncDatabaseManager:
    """
    SQLAlchemy 2.0 async wrapper for database access.

    Provides the same public interface as DatabaseManager (execute, fetch_all,
    fetch_one, upsert) but using an async_sessionmaker from SQLAlchemy so
    callers can await queries without blocking the event loop.

    Usage:
        db = AsyncDatabaseManager(session_factory)
        rows = await db.fetch_all("SELECT * FROM fragments WHERE language = :lang",
                                  {"lang": "python"})
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def execute(self, query: str, params: Dict[str, Any] | tuple = ()) -> None:
        """Execute a DML statement (INSERT / UPDATE / DELETE)."""
        named = self._to_named(params)
        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(text(query), named)

    async def fetch_all(self, query: str, params: Dict[str, Any] | tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows as dicts using named or positional params."""
        named = self._to_named(params)
        async with self._session_factory() as session:
            result = await session.execute(text(query), named)
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]

    async def fetch_one(self, query: str, params: Dict[str, Any] | tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch a single row as a dict, or None if no results."""
        named = self._to_named(params)
        async with self._session_factory() as session:
            result = await session.execute(text(query), named)
            columns = result.keys()
            row = result.fetchone()
            return dict(zip(columns, row)) if row else None

    async def upsert(self, table: str, data: Dict[str, Any], unique_keys: List[str]) -> None:
        """Generic async upsert (SQLite 3.24+ ON CONFLICT syntax)."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join([f":{k}" for k in data.keys()])
        updates = ", ".join([f"{k}=excluded.{k}" for k in data.keys() if k not in unique_keys])
        query = (
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT({', '.join(unique_keys)}) DO UPDATE SET {updates}"
        )
        await self.execute(query, data)

    @staticmethod
    def _to_named(params: Dict[str, Any] | tuple) -> Dict[str, Any]:
        """Convert positional tuple params to named dict for SQLAlchemy text()."""
        if isinstance(params, dict):
            return params
        return {f"p{i}": v for i, v in enumerate(params)}
