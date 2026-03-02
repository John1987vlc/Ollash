"""
SQLAlchemy ORM model for the prompt history database.

Maps to the existing 'prompts' table schema without schema changes.
"""

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.utils.core.system.db.base_model import Base


class PromptModel(Base):
    """ORM model for the 'prompts' table in prompt_history.db."""

    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_role: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, default=0)
