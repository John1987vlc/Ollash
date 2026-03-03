"""Vector store client manager — returns a SQLiteVectorStore.

Previously returned a ChromaDB client.  All callers keep the same
``ChromaClientManager.get_client(settings, project_root)`` interface
and now receive a :class:`SQLiteVectorStore` which is API-compatible
with the ChromaDB collections they were using.

Replacing ChromaDB eliminates ~866 transitive modules (numpy, grpc,
opentelemetry, sentence-transformers) from the process import tree and
reduces per-process RAM by ~200-400 MB.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.utils.core.memory.sqlite_vector_store import SQLiteVectorStore

logger = logging.getLogger(__name__)


class ChromaClientManager:
    """Singleton factory for the project-scoped SQLiteVectorStore.

    The class name is kept for backward compatibility with all existing
    ``from backend.utils.core.memory.chroma_manager import ChromaClientManager``
    imports — no changes needed in callers.
    """

    _instance: SQLiteVectorStore | None = None
    _db_path: Path | None = None

    @classmethod
    def get_client(cls, settings_manager: dict, project_root: Path) -> SQLiteVectorStore:
        """Return the shared SQLiteVectorStore for *project_root*.

        A new instance is created whenever *project_root* changes (e.g. between
        separate project generations in the same process).
        """
        db_path = Path(project_root) / ".ollash" / "vectors.db"
        if cls._instance is None or cls._db_path != db_path:
            cls._db_path = db_path
            cls._instance = SQLiteVectorStore(db_path)
            logger.info(f"SQLiteVectorStore initialized at {db_path}")
        return cls._instance
