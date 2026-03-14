import logging
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.agents.simple_chat_agent import SimpleChatAgent
from backend.services.chat_event_bridge import ChatEventBridge

_log = logging.getLogger("ollash")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXCLUDE_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".cache",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        "target",
        ".ollash",
    }
)
_SOURCE_EXTS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".go",
        ".rs",
        ".java",
        ".cpp",
        ".c",
        ".cs",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".json",
        ".yaml",
        ".yml",
        ".md",
        ".html",
        ".css",
        ".sh",
        ".toml",
        ".env.example",
    }
)


def _build_project_tree(project_path: str, max_files: int = 120) -> str:
    """Return a compact file-tree string for the given project directory.

    Only lists source files (up to *max_files*) so the context injection stays
    small (~100 tokens for a typical project).
    """
    root = Path(project_path)
    if not root.exists():
        return ""

    lines: List[str] = [f"# Project: {root.name}", ""]
    file_count = 0
    truncated = False

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _EXCLUDE_DIRS)
        rel_dir = Path(dirpath).relative_to(root)
        indent = "  " * len(rel_dir.parts)

        if rel_dir.parts:
            lines.append(f"{indent[:-2]}{rel_dir.parts[-1]}/")

        for fname in sorted(filenames):
            if Path(fname).suffix.lower() not in _SOURCE_EXTS:
                continue
            file_count += 1
            if file_count > max_files:
                truncated = True
                break
            lines.append(f"{indent}{fname}")

        if truncated:
            lines.append(f"{indent}... (truncated)")
            break

    return "\n".join(lines)


def _load_coding_system_prompt(project_path: str, prompts_base: Path) -> str:
    """Load the interactive_coding_agent system prompt and append project context."""
    prompt_text = ""
    try:
        from backend.utils.core.llm.prompt_loader import PromptLoader

        loader = PromptLoader(prompts_dir=prompts_base)
        data = loader.load_prompt_sync("roles/interactive_coding_agent.yaml")
        prompt_text = data.get("interactive_coding_agent", {}).get("system", "")
    except Exception as exc:
        _log.warning(f"Could not load interactive_coding_agent prompt: {exc}")

    if not prompt_text:
        prompt_text = (
            "You are an interactive coding assistant. "
            "Always read files before editing them. "
            "Run tests after making changes to verify correctness."
        )

    # Inject project tree
    tree = _build_project_tree(project_path)
    if tree:
        prompt_text += f"\n\n## Project file tree\n```\n{tree}\n```"

    # Inject OLLASH.md / CLAUDE.md project instructions if present
    for instr_file in ("OLLASH.md", "CLAUDE.md"):
        instr_path = Path(project_path) / instr_file
        if instr_path.exists():
            try:
                instructions = instr_path.read_text(encoding="utf-8", errors="replace")
                prompt_text += f"\n\n## Project instructions ({instr_file})\n{instructions}"
                break
            except Exception:
                pass

    return prompt_text


@dataclass
class ChatSession:
    session_id: str
    agent: Union[SimpleChatAgent, "DefaultAgent"]  # type: ignore[name-defined]  # noqa: F821
    bridge: ChatEventBridge
    thread: Optional[threading.Thread] = None


class ChatSessionManager:
    """Manages active DefaultAgent chat sessions for the web UI."""

    MAX_SESSIONS = 5
    MAX_MESSAGES_PER_SESSION = 200

    def __init__(self, ollash_root_dir: Path, event_publisher):
        self.ollash_root_dir = ollash_root_dir
        self._prompts_base = ollash_root_dir / "prompts"
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
        system_prompt_override: Optional[str] = None,
    ) -> str:
        """Create a new chat session.

        When *mode* is ``"coding"``, a full :class:`DefaultAgent` is used so the
        session has access to all tools, confirmation gates, and context summarization.
        Otherwise a lightweight :class:`SimpleChatAgent` is used.
        """
        with self._lock:
            self._cleanup_finished()

            if len(self.sessions) >= self.MAX_SESSIONS:
                raise RuntimeError(f"Maximum concurrent sessions ({self.MAX_SESSIONS}) reached.")

            session_id = uuid.uuid4().hex
            bridge = ChatEventBridge(self.event_publisher)

            resolved_root = project_path or str(self.ollash_root_dir)

            if mode == "coding":
                from backend.agents.default_agent import DefaultAgent
                from backend.services.project_index import ProjectIndex

                # Build system prompt: role description + project tree + OLLASH.md
                coding_prompt = system_prompt_override or _load_coding_system_prompt(resolved_root, self._prompts_base)
                agent = DefaultAgent(
                    project_root=resolved_root,
                    event_bridge=bridge,
                    auto_confirm=False,
                    system_prompt_override=coding_prompt,
                )

                # Build project index (background RAG) and inject into FileSystemTools
                project_idx = ProjectIndex(resolved_root)
                project_idx.start_background_index()
                self._inject_project_index(agent, project_idx)

                db_agent_type = "coding"
            else:
                agent = SimpleChatAgent(event_bridge=bridge, model=model)
                db_agent_type = "chat"

            # Save session to DB
            self.db.execute(
                "INSERT INTO chat_sessions (id, agent_type, project_path, title) VALUES (?, ?, ?, ?)",
                (session_id, db_agent_type, resolved_root, "New Chat"),
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

    @staticmethod
    def _inject_project_index(agent: Any, project_index: Any) -> None:
        """Inject a :class:`ProjectIndex` into the agent's FileSystemTools instance.

        ``DefaultAgent`` instantiates ``FileSystemTools`` via ``ToolRegistry``.
        We reach into the registry's tool mapping and set ``_project_index`` so
        ``search_codebase()`` can delegate to the session-scoped index.
        """
        try:
            from backend.utils.domains.code.file_system_tools import FileSystemTools

            registry = getattr(agent, "_tool_registry", None)
            if registry is None:
                return
            mapping = getattr(registry, "_all_tool_instances_mapping", None) or {}
            for tool_instance in mapping.values():
                if isinstance(tool_instance, FileSystemTools):
                    tool_instance._project_index = project_index
                    _log.debug("ProjectIndex injected into FileSystemTools")
                    return
        except Exception as exc:
            _log.warning(f"Could not inject ProjectIndex into agent tools: {exc}")
