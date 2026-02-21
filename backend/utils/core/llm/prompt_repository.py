import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class PromptRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_role TEXT NOT NULL,
                    prompt_text TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def migrate_from_json(self, prompts_dir: Path):
        """Migra los prompts existentes de archivos JSON a SQLite."""
        for json_file in prompts_dir.glob("**/*.json"):
            try:
                role = json_file.stem
                with open(json_file, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    text = content.get("system_prompt") or content.get("prompt", "")
                    if text:
                        self.save_prompt(role, text, is_active=True)
            except Exception as e:
                logger.error(f"Error migrando {json_file}: {e}")

    def save_prompt(self, role: str, text: str, is_active: bool = False) -> int:
        with sqlite3.connect(self.db_path) as conn:
            # Obtener última versión
            cursor = conn.execute("SELECT MAX(version) FROM prompts WHERE agent_role = ?", (role,))
            row = cursor.fetchone()
            next_version = (row[0] or 0) + 1

            if is_active:
                conn.execute("UPDATE prompts SET is_active = 0 WHERE agent_role = ?", (role,))

            cursor = conn.execute(
                "INSERT INTO prompts (agent_role, prompt_text, version, created_at, is_active) VALUES (?, ?, ?, ?, ?)",
                (role, text, next_version, datetime.now().isoformat(), 1 if is_active else 0),
            )
            return cursor.lastrowid

    def get_active_prompt(self, role: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT prompt_text FROM prompts WHERE agent_role = ? AND is_active = 1", (role,))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_history(self, role: str) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT id, version, created_at, is_active, prompt_text FROM prompts WHERE agent_role = ? ORDER BY version DESC",
                (role,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def rollback(self, prompt_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT agent_role FROM prompts WHERE id = ?", (prompt_id,))
            role = cursor.fetchone()[0]
            conn.execute("UPDATE prompts SET is_active = 0 WHERE agent_role = ?", (role,))
            conn.execute("UPDATE prompts SET is_active = 1 WHERE id = ?", (prompt_id,))
            conn.commit()
