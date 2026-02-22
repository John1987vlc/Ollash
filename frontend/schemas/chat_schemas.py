"""Request schemas for chat-related endpoints in common_views.py."""

from typing import Optional

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Body for POST /api/chat/message."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=32_000,
        description="User message text.",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Existing session ID. None creates a new session.",
    )


class ChatSessionCreate(BaseModel):
    """Body for POST /api/chat/session."""

    project_path: Optional[str] = Field(
        default=None,
        description="Absolute path to the project the agent will work on.",
    )
    agent_type: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Agent type identifier (e.g. 'code', 'default').",
    )
