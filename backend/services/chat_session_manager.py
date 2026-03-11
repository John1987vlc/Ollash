import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from backend.agents.simple_chat_agent import SimpleChatAgent
from backend.services.chat_event_bridge import ChatEventBridge


@dataclass
class ChatSession:
    session_id: str
    agent: SimpleChatAgent
    bridge: ChatEventBridge
    thread: Optional[threading.Thread] = None


class ChatSessionManager:
    """Manages active DefaultAgent chat sessions for the web UI."""

    MAX_SESSIONS = 5
    MAX_MESSAGES_PER_SESSION = 200

    def __init__(self, ollash_root_dir: Path, event_publisher):
        self.ollash_root_dir = ollash_root_dir
        self.sessions: Dict[str, ChatSession] = {}
        self._lock = threading.Lock()
        self.event_publisher = event_publisher
        self._init_db()

    def _init_db(self):
        """Initialize chat persistence tables."""
        from backend.utils.core.system.db.sqlite_manager import DatabaseManager

        db_path = self.ollash_root_dir / ".ollash" / "logs.db"
        self.db = DatabaseManager(db_path)
        with self.db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    agent_type TEXT,
                    project_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    title TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                )
            """)

    def create_session(
        self,
        project_path: Optional[str] = None,
        agent_type: Optional[str] = None,
        model: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> str:
        """Create a new lightweight chat session backed by SimpleChatAgent."""
        with self._lock:
            self._cleanup_finished()

            if len(self.sessions) >= self.MAX_SESSIONS:
                raise RuntimeError(f"Maximum concurrent sessions ({self.MAX_SESSIONS}) reached.")

            session_id = uuid.uuid4().hex
            bridge = ChatEventBridge(self.event_publisher)

            agent = SimpleChatAgent(event_bridge=bridge, model=model)

            # Save session to DB
            self.db.execute(
                "INSERT INTO chat_sessions (id, agent_type, project_path, title) VALUES (?, ?, ?, ?)",
                (session_id, "chat", str(self.ollash_root_dir), "New Chat"),
            )

            self.sessions[session_id] = ChatSession(
                session_id=session_id,
                agent=agent,
                bridge=bridge,
            )
            return session_id

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self.sessions.get(session_id)

    def list_sessions(self, limit: int = 20):
        """Returns a list of recent chat sessions from DB."""
        return self.db.fetch_all(
            "SELECT id, agent_type, created_at, title FROM chat_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        )

    def get_session_history(self, session_id: str):
        """Returns all messages for a given session."""
        return self.db.fetch_all(
            "SELECT role, content, timestamp FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        )

    def send_message(self, session_id: str, message: str):
        """Run agent.chat(message) in a background thread and persist to DB."""
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session '{session_id}' not found.")

        # Persist user message
        self.db.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, "user", message)
        )

        # Update session title based on first message if it's default
        self.db.execute(
            "UPDATE chat_sessions SET title = ? WHERE id = ? AND title LIKE 'New %'", (message[:30] + "...", session_id)
        )

        # Create a fresh bridge for each message turn (the previous one is closed after each reply)
        fresh_bridge = ChatEventBridge(self.event_publisher)
        session.bridge = fresh_bridge
        session.agent.event_bridge = fresh_bridge

        def _run():
            import asyncio

            try:
                # Robust event loop management for background thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Use the thread-local loop to run the async chat
                result = loop.run_until_complete(session.agent.chat(message))

                import logging

                logger = logging.getLogger("ollash")
                logger.info(f"DEBUG: chat_session_manager result type: {type(result)}")
                if isinstance(result, dict):
                    logger.info(f"DEBUG: chat_session_manager result keys: {result.keys()}")

                content = ""
                metrics = {}
                if isinstance(result, dict):
                    content = result.get("text", "")
                    metrics = result.get("metrics", {})
                else:
                    content = str(result)

                logger.info(f"DEBUG: chat_session_manager final content length: {len(content)}")

                # Persist assistant response
                self.db.execute(
                    "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
                    (session_id, "assistant", content),
                )

                # Trim oldest messages to stay within per-session history limit
                self.db.execute(
                    """DELETE FROM chat_messages WHERE session_id = ? AND id NOT IN (
                        SELECT id FROM chat_messages WHERE session_id = ?
                        ORDER BY id DESC LIMIT ?
                    )""",
                    (session_id, session_id, ChatSessionManager.MAX_MESSAGES_PER_SESSION),
                )

                session.bridge.push_event("final_answer", {"content": content, "metrics": metrics})
            except Exception as e:
                session.bridge.push_event("error", {"message": str(e)})
            finally:
                session.bridge.close()

        t = threading.Thread(target=_run, daemon=True)
        session.thread = t
        t.start()

    def delete_empty_sessions(self):
        """Deletes sessions that have no messages."""
        self.db.execute("""
            DELETE FROM chat_sessions
            WHERE id NOT IN (SELECT DISTINCT session_id FROM chat_messages)
        """)

    def delete_session(self, session_id: str):
        with self._lock:
            self.sessions.pop(session_id, None)
        self.db.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))

    def delete_all_sessions(self):
        """Delete all sessions from DB and clear in-memory sessions."""
        with self._lock:
            self.sessions.clear()
        self.db.execute("DELETE FROM chat_messages")
        self.db.execute("DELETE FROM chat_sessions")

    def _cleanup_finished(self):
        """Remove sessions whose threads have completed."""
        finished = [sid for sid, s in self.sessions.items() if s.thread is not None and not s.thread.is_alive()]
        for sid in finished:
            del self.sessions[sid]
