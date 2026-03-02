"""
SQLAlchemy ORM model for the fragment cache database.

Maps to the existing 'fragments' table schema without schema changes.
"""

from sqlalchemy import Boolean, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.utils.core.system.db.base_model import Base


class FragmentModel(Base):
    """ORM model for the 'fragments' table in fragment_cache.db."""

    __tablename__ = "fragments"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    fragment_type: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    metadata: Mapped[str] = mapped_column(Text, default="{}")
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("idx_fragments_type", "fragment_type", "language"),
    )
