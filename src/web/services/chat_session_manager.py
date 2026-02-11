import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from src.agents.default_agent import DefaultAgent
from src.web.services.chat_event_bridge import ChatEventBridge


@dataclass
class ChatSession:
    session_id: str
    agent: DefaultAgent
    bridge: ChatEventBridge
    thread: Optional[threading.Thread] = None


class ChatSessionManager:
    """Manages active DefaultAgent chat sessions for the web UI."""

    MAX_SESSIONS = 5

    def __init__(self, ollash_root_dir: Path, event_publisher):
        self.ollash_root_dir = ollash_root_dir
        self.sessions: Dict[str, ChatSession] = {}
        self._lock = threading.Lock()
        self.event_publisher = event_publisher

    def create_session(self, project_path: Optional[str] = None, agent_type: Optional[str] = None) -> str:
        """Create a new chat session with its own DefaultAgent instance."""
        with self._lock:
            # Clean up finished sessions
            self._cleanup_finished()

            if len(self.sessions) >= self.MAX_SESSIONS:
                raise RuntimeError(f"Maximum concurrent sessions ({self.MAX_SESSIONS}) reached.")

            session_id = uuid.uuid4().hex
            bridge = ChatEventBridge(self.event_publisher)
            agent = DefaultAgent(
                project_root=project_path,
                auto_confirm=True,
                base_path=self.ollash_root_dir,
                event_bridge=bridge,
            )
            # Pre-set agent type if requested (skips orchestrator default)
            if agent_type and agent_type in agent._agent_tool_name_mappings:
                agent.active_agent_type = agent_type
                agent.active_tool_names = agent._agent_tool_name_mappings[agent_type]

            self.sessions[session_id] = ChatSession(
                session_id=session_id,
                agent=agent,
                bridge=bridge,
            )
            return session_id

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self.sessions.get(session_id)

    def send_message(self, session_id: str, message: str):
        """Run agent.chat(message) in a background thread."""
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session '{session_id}' not found.")

        def _run():
            try:
                response = session.agent.chat(message)
                session.bridge.push_event("final_answer", {"content": response})
            except Exception as e:
                session.bridge.push_event("error", {"message": str(e)})
            finally:
                session.bridge.close()

        t = threading.Thread(target=_run, daemon=True)
        session.thread = t
        t.start()

    def delete_session(self, session_id: str):
        with self._lock:
            self.sessions.pop(session_id, None)

    def _cleanup_finished(self):
        """Remove sessions whose threads have completed."""
        finished = [
            sid for sid, s in self.sessions.items()
            if s.thread is not None and not s.thread.is_alive()
        ]
        for sid in finished:
            del self.sessions[sid]
