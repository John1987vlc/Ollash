"""
SQLAlchemy 2.0 declarative base shared by all ORM models.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all Ollash ORM models."""

    pass
