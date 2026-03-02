"""
Async SQLAlchemy engine factory for SQLite databases.

Usage:
    from backend.utils.core.system.db.engine import make_async_engine, make_session_factory

    engine = make_async_engine("/path/to/db.sqlite")
    SessionFactory = make_session_factory(engine)

    async with SessionFactory() as session:
        result = await session.execute(select(MyModel))
"""

from pathlib import Path
from typing import Union

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def make_async_engine(db_path: Union[str, Path]) -> AsyncEngine:
    """
    Create an async SQLAlchemy engine for a SQLite database.

    WAL mode and foreign keys are enabled automatically on each new connection.

    Args:
        db_path: Path to the SQLite file (created if it does not exist).

    Returns:
        Configured AsyncEngine instance.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragmas(dbapi_conn, _connection_record) -> None:
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """
    Create a session factory bound to *engine*.

    Returns:
        async_sessionmaker that produces AsyncSession instances with
        expire_on_commit=False (safe for async usage).
    """
    return async_sessionmaker(engine, expire_on_commit=False)
