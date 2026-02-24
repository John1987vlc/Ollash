import pytest
import sqlite3
from unittest.mock import MagicMock
from frontend.services.chat_session_manager import ChatSessionManager

@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path

def test_chat_session_manager_db_initialization(temp_db_path):
    """Verifica que el manager cree las tablas de persistencia al iniciarse."""
    manager = ChatSessionManager(temp_db_path, MagicMock())
    db_path = temp_db_path / ".ollash" / "logs.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_sessions'")
    assert cursor.fetchone() is not None
    conn.close()

def test_chat_session_creation_and_retrieval(temp_db_path):
    """Verifica la creación de sesiones y su recuperación desde memoria/DB."""
    manager = ChatSessionManager(temp_db_path, MagicMock())
    session_id = manager.create_session(agent_type="code")

    assert session_id is not None
    assert manager.get_session(session_id) is not None

    sessions = manager.list_sessions()
    assert any(s['id'] == session_id for s in sessions)
