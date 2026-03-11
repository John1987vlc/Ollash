"""Unit tests for ChatSessionManager — focused on delete_all_sessions / delete_session."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.services.chat_session_manager import ChatSessionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager(tmp_path: Path) -> ChatSessionManager:
    """Return a ChatSessionManager backed by a real (temporary) SQLite DB."""
    event_publisher = MagicMock()
    # subscribe() is called many times by ChatEventBridge — suppress the noise
    event_publisher.subscribe = MagicMock()
    return ChatSessionManager(tmp_path, event_publisher)


def _seed_session(mgr: ChatSessionManager, session_id: str, message: str = "Hola") -> None:
    """Insert a session + one message directly into the DB (no Ollama needed)."""
    mgr.db.execute(
        "INSERT INTO chat_sessions (id, agent_type, project_path, title) VALUES (?, ?, ?, ?)",
        (session_id, "chat", ".", "Test Session"),
    )
    mgr.db.execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, "user", message),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeleteAllSessions:
    def test_empty_db_is_safe(self, tmp_path):
        """Calling delete_all_sessions on an empty DB must not raise."""
        mgr = _make_manager(tmp_path)
        mgr.delete_all_sessions()  # should not raise

        rows = mgr.db.fetch_all("SELECT id FROM chat_sessions")
        assert rows == []

    def test_removes_all_sessions_from_db(self, tmp_path):
        mgr = _make_manager(tmp_path)
        _seed_session(mgr, "aaa111")
        _seed_session(mgr, "bbb222")

        rows_before = mgr.db.fetch_all("SELECT id FROM chat_sessions")
        assert len(rows_before) == 2

        mgr.delete_all_sessions()

        rows_after = mgr.db.fetch_all("SELECT id FROM chat_sessions")
        assert rows_after == []

    def test_removes_all_messages_from_db(self, tmp_path):
        mgr = _make_manager(tmp_path)
        _seed_session(mgr, "aaa111", message="Hola")
        _seed_session(mgr, "bbb222", message="Adios")

        msgs_before = mgr.db.fetch_all("SELECT id FROM chat_messages")
        assert len(msgs_before) == 2

        mgr.delete_all_sessions()

        msgs_after = mgr.db.fetch_all("SELECT id FROM chat_messages")
        assert msgs_after == []

    def test_clears_in_memory_sessions(self, tmp_path):
        """In-memory session dict must be cleared so MAX_SESSIONS limit resets."""
        mgr = _make_manager(tmp_path)

        # Inject a fake in-memory session without calling create_session
        # (which would try to start a real SimpleChatAgent)
        fake_session = MagicMock()
        fake_session.thread = None
        mgr.sessions["fake123"] = fake_session

        assert len(mgr.sessions) == 1
        mgr.delete_all_sessions()
        assert len(mgr.sessions) == 0


@pytest.mark.unit
class TestDeleteSingleSession:
    def test_removes_target_session_only(self, tmp_path):
        mgr = _make_manager(tmp_path)
        _seed_session(mgr, "keep111")
        _seed_session(mgr, "remove222")

        mgr.delete_session("remove222")

        remaining = [row["id"] for row in mgr.db.fetch_all("SELECT id FROM chat_sessions")]
        assert "remove222" not in remaining
        assert "keep111" in remaining

    def test_delete_nonexistent_session_is_safe(self, tmp_path):
        mgr = _make_manager(tmp_path)
        mgr.delete_session("ghost999")  # must not raise


@pytest.mark.unit
class TestListSessions:
    def test_list_sessions_returns_db_rows(self, tmp_path):
        mgr = _make_manager(tmp_path)
        _seed_session(mgr, "sess001")
        _seed_session(mgr, "sess002")

        sessions = mgr.list_sessions()
        ids = [row["id"] for row in sessions]
        assert "sess001" in ids
        assert "sess002" in ids

    def test_empty_db_returns_empty_list(self, tmp_path):
        mgr = _make_manager(tmp_path)
        sessions = mgr.list_sessions()
        assert sessions == []


@pytest.mark.unit
class TestDeleteAllSessionsEndpoint:
    """Integration-style test against the FastAPI route (Starlette TestClient)."""

    def test_delete_all_sessions_returns_200(self, fastapi_app):
        """DELETE /api/chat/sessions must return 200 with status='deleted_all'."""
        from starlette.testclient import TestClient

        with TestClient(fastapi_app, raise_server_exceptions=True) as c:
            response = c.delete("/api/chat/sessions")
            assert response.status_code == 200
            data = response.json()
            assert data.get("status") == "deleted_all"

    def test_delete_all_then_list_is_empty(self, fastapi_app):
        """After DELETE /api/chat/sessions, GET /api/chat/sessions must return empty list."""
        from starlette.testclient import TestClient

        with TestClient(fastapi_app, raise_server_exceptions=True) as c:
            c.delete("/api/chat/sessions")
            response = c.get("/api/chat/sessions")
            assert response.status_code == 200
            assert response.json()["sessions"] == []
