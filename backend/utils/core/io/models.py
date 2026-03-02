"""
SQLAlchemy ORM model for the checkpoint index database.

Maps to the existing 'checkpoints' table schema without schema changes.
"""

from sqlalchemy import Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.utils.core.system.db.base_model import Base


class CheckpointModel(Base):
    """ORM model for the 'checkpoints' table in checkpoints/index.db."""

    __tablename__ = "checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(Text, nullable=False)
    phase_name: Mapped[str] = mapped_column(Text, nullable=False)
    phase_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    json_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("project_name", "phase_name", name="uq_checkpoint_project_phase"),
        Index("idx_checkpoints_project", "project_name", "phase_index"),
    )
