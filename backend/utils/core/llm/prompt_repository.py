import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.utils.core.system.db.engine import make_async_engine, make_session_factory
from backend.utils.core.system.db.sqlite_manager import AsyncDatabaseManager

logger = logging.getLogger(__name__)


class PromptRepository:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
    ):
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            if not db_path:
                db_path = Path(".ollash/prompt_history.db")
            engine = make_async_engine(db_path)
            self._session_factory = make_session_factory(engine)

        self.db = AsyncDatabaseManager(self._session_factory)

    async def _init_db(self) -> None:
        """Initialize the prompts table (idempotent, call once at startup)."""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_role TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 0
            )
        """)

    async def migrate_from_json(self, prompts_dir: Path) -> None:
        """Migrate existing prompts from JSON files to the database."""
        for json_file in prompts_dir.glob("**/*.json"):
            try:
                role = json_file.stem
                with open(json_file, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    text = content.get("system_prompt") or content.get("prompt", "")
                    if text:
                        await self.save_prompt(role, text, is_active=True)
            except Exception as e:
                logger.error(f"Error migrating {json_file}: {e}")

    async def save_prompt(self, role: str, text: str, is_active: bool = False) -> Optional[int]:
        row = await self.db.fetch_one(
            "SELECT MAX(version) as max_ver FROM prompts WHERE agent_role = :agent_role",
            {"agent_role": role},
        )
        next_version = (row["max_ver"] or 0) + 1 if row else 1

        if is_active:
            await self.db.execute(
                "UPDATE prompts SET is_active = 0 WHERE agent_role = :agent_role",
                {"agent_role": role},
            )

        await self.db.execute(
            "INSERT INTO prompts (agent_role, prompt_text, version, created_at, is_active) "
            "VALUES (:agent_role, :prompt_text, :version, :created_at, :is_active)",
            {
                "agent_role": role,
                "prompt_text": text,
                "version": next_version,
                "created_at": datetime.now().isoformat(),
                "is_active": 1 if is_active else 0,
            },
        )
        result = await self.db.fetch_one(
            "SELECT id FROM prompts WHERE agent_role = :agent_role AND version = :version",
            {"agent_role": role, "version": next_version},
        )
        return result["id"] if result else None

    async def get_active_prompt(self, role: str) -> Optional[str]:
        row = await self.db.fetch_one(
            "SELECT prompt_text FROM prompts WHERE agent_role = :agent_role AND is_active = 1",
            {"agent_role": role},
        )
        return row["prompt_text"] if row else None

    async def get_history(self, role: str) -> List[Dict]:
        return await self.db.fetch_all(
            "SELECT id, version, created_at, is_active, prompt_text "
            "FROM prompts WHERE agent_role = :agent_role ORDER BY version DESC",
            {"agent_role": role},
        )

    async def rollback(self, prompt_id: int) -> None:
        row = await self.db.fetch_one(
            "SELECT agent_role FROM prompts WHERE id = :prompt_id",
            {"prompt_id": prompt_id},
        )
        if not row:
            return
        role = row["agent_role"]
        await self.db.execute(
            "UPDATE prompts SET is_active = 0 WHERE agent_role = :agent_role",
            {"agent_role": role},
        )
        await self.db.execute(
            "UPDATE prompts SET is_active = 1 WHERE id = :prompt_id",
            {"prompt_id": prompt_id},
        )
