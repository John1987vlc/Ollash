"""
Pair Programming Session Manager

Manages live collaboration sessions where users can watch
agents write code in real-time and intervene with suggestions.
"""

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.event_publisher import EventPublisher


@dataclass
class CodeEdit:
    """A single code edit in a pair programming session."""

    edit_id: str
    file_path: str
    content: str
    cursor_position: int
    source: str  # "agent" or "user"
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edit_id": self.edit_id,
            "file_path": self.file_path,
            "content_length": len(self.content),
            "cursor_position": self.cursor_position,
            "source": self.source,
            "timestamp": self.timestamp,
        }


class PairProgrammingSession:
    """Manages a live pair programming session between agent and user.

    Features:
    - Real-time code updates via EventPublisher (SSE)
    - User can pause/resume agent generation
    - User can intervene with edits that override agent output
    - Session history for replay
    """

    def __init__(
        self,
        session_id: str,
        event_publisher: EventPublisher,
        logger: AgentLogger,
    ):
        self.session_id = session_id
        self.event_publisher = event_publisher
        self.logger = logger
        self.is_paused = False
        self.is_active = True
        self.current_file: Optional[str] = None
        self.current_content: str = ""
        self.history: List[CodeEdit] = []

    def start_file(self, file_path: str) -> None:
        """Signal that the agent is starting to generate a file."""
        self.current_file = file_path
        self.current_content = ""
        self.event_publisher.publish(
            "pair_programming_file_start",
            session_id=self.session_id,
            file_path=file_path,
        )
        self.logger.info(f"Pair programming: started file {file_path}")

    def update_content(self, content: str, cursor_pos: int = -1) -> None:
        """Push a content update from the agent."""
        if self.is_paused:
            return

        self.current_content = content
        edit = CodeEdit(
            edit_id=str(uuid.uuid4())[:8],
            file_path=self.current_file or "",
            content=content,
            cursor_position=cursor_pos if cursor_pos >= 0 else len(content),
            source="agent",
            timestamp=time.time(),
        )
        self.history.append(edit)

        self.event_publisher.publish(
            "pair_programming_update",
            session_id=self.session_id,
            file_path=self.current_file,
            content=content,
            cursor_position=edit.cursor_position,
            source="agent",
        )

    def user_intervention(self, content: str, cursor_pos: int = -1) -> None:
        """Record and broadcast a user edit intervention."""
        self.current_content = content
        edit = CodeEdit(
            edit_id=str(uuid.uuid4())[:8],
            file_path=self.current_file or "",
            content=content,
            cursor_position=cursor_pos if cursor_pos >= 0 else len(content),
            source="user",
            timestamp=time.time(),
        )
        self.history.append(edit)

        self.event_publisher.publish(
            "pair_programming_intervention",
            session_id=self.session_id,
            file_path=self.current_file,
            content=content,
            source="user",
        )
        self.logger.info(f"Pair programming: user intervention on {self.current_file}")

    def complete_file(self, final_content: str) -> None:
        """Signal that a file generation is complete."""
        self.event_publisher.publish(
            "pair_programming_file_complete",
            session_id=self.session_id,
            file_path=self.current_file,
            content=final_content,
        )

    def pause(self) -> None:
        """Pause agent generation."""
        self.is_paused = True
        self.event_publisher.publish(
            "pair_programming_paused",
            session_id=self.session_id,
        )
        self.logger.info("Pair programming: paused")

    def resume(self) -> None:
        """Resume agent generation."""
        self.is_paused = False
        self.event_publisher.publish(
            "pair_programming_resumed",
            session_id=self.session_id,
        )
        self.logger.info("Pair programming: resumed")

    def end_session(self) -> None:
        """End the pair programming session."""
        self.is_active = False
        self.event_publisher.publish(
            "pair_programming_ended",
            session_id=self.session_id,
            total_edits=len(self.history),
        )
        self.logger.info(f"Pair programming session ended: {len(self.history)} total edits")

    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics for the current session."""
        agent_edits = sum(1 for e in self.history if e.source == "agent")
        user_edits = sum(1 for e in self.history if e.source == "user")
        return {
            "session_id": self.session_id,
            "is_active": self.is_active,
            "is_paused": self.is_paused,
            "current_file": self.current_file,
            "total_edits": len(self.history),
            "agent_edits": agent_edits,
            "user_edits": user_edits,
        }
