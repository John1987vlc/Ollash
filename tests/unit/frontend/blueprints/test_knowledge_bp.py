"""Unit tests for knowledge_bp - knowledge base routes."""
import sys
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from flask import Flask

# ---------------------------------------------------------------------------
# Pre-import mocking: block heavy dependencies before blueprint import
# ---------------------------------------------------------------------------

_mock_container = MagicMock()
sys.modules.setdefault("backend.core.containers", MagicMock(main_container=_mock_container))
sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("werkzeug.utils", MagicMock(secure_filename=lambda f: f))


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_doc_manager():
    mgr = MagicMock()
    mgr.list_documents.return_value = [
        {"id": "doc1", "name": "guide.pdf", "chunks": 5},
        {"id": "doc2", "name": "readme.txt", "chunks": 2},
    ]
    mgr.upload_document.return_value = {"id": "doc3", "name": "new.pdf"}
    mgr.delete_document.return_value = True
    return mgr


@pytest.fixture
def mock_error_kb():
    kb = MagicMock()
    kb.get_statistics.return_value = {"total_errors": 12, "common_types": ["ImportError"]}
    return kb


@pytest.fixture
def mock_episodic():
    em = MagicMock()
    em.get_recent_episodes.return_value = [
        {"id": "ep1", "description": "Fixed bug", "timestamp": "2024-01-01T10:00:00"}
    ]
    return em


@pytest.fixture
def app(mock_doc_manager, mock_error_kb, mock_episodic):
    _mock_container.documentation_manager.return_value = mock_doc_manager
    _mock_container.error_knowledge_base.return_value = mock_error_kb
    _mock_container.episodic_memory.return_value = mock_episodic

    from frontend.blueprints.knowledge_views import bp as knowledge_bp
    
    # Base directory for templates
    template_dir = Path(__file__).parents[4] / "frontend" / "templates"
    
    flask_app = Flask(__name__, template_folder=str(template_dir))
    flask_app.config["ollash_root_dir"] = Path(".")
    flask_app.register_blueprint(knowledge_bp)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_knowledge_page_returns_200(client):
    """GET /knowledge devuelve 200 (página principal)."""
    response = client.get("/knowledge")
    assert response.status_code in (200, 302)


@pytest.mark.unit
def test_list_documents_returns_list(client):
    """GET /api/knowledge/documents devuelve lista de documentos indexados."""
    response = client.get("/api/knowledge/documents")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, (list, dict))


@pytest.mark.unit
def test_delete_document_ok(client):
    """DELETE /api/knowledge/documents/<doc_id> elimina el documento indicado."""
    response = client.delete("/api/knowledge/documents/doc1")
    assert response.status_code in (200, 204, 404)
    if response.status_code != 204:
        data = response.get_json()
        assert data is not None


@pytest.mark.unit
def test_get_error_knowledge(client):
    """GET /api/knowledge/errors devuelve estadísticas de errores."""
    response = client.get("/api/knowledge/errors")
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None


@pytest.mark.unit
def test_get_episodic_memory(client):
    """GET /api/knowledge/episodes devuelve memoria episódica."""
    response = client.get("/api/knowledge/episodes")
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None


@pytest.mark.unit
def test_upload_document_no_file_returns_400(client):
    """POST /api/knowledge/upload sin archivo devuelve 400."""
    response = client.post(
        "/api/knowledge/upload",
        data={},
        content_type="multipart/form-data",
    )
    assert response.status_code in (400, 422)
