"""FastAPI application fixtures — TestClient, app instance.

Replaces flask_fixtures.py for tests that previously used Flask's test_client().
The starlette TestClient has the same sync HTTP interface so most test code
needs minimal changes beyond removing `with app.app_context():` blocks.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from backend.api.app import create_app


@pytest.fixture
def fastapi_app(project_root):
    """Creates a FastAPI app instance configured for testing.

    Services that make real network calls (Ollama, EventPublisher) are
    replaced with MagicMocks via app.state overrides after creation.
    """
    test_root = project_root / "test_root_fastapi"
    test_root.mkdir(parents=True, exist_ok=True)
    os.environ["OLLASH_ROOT_DIR"] = str(test_root)

    _app = create_app()

    # Override services with mocks so tests don't require a running server
    _app.state.event_publisher = MagicMock()
    _app.state.alert_manager = MagicMock()
    _app.state.automation_manager = MagicMock()
    _app.state.notification_manager = MagicMock()
    _app.state.chat_event_bridge = MagicMock()
    _app.state.ollash_root_dir = test_root

    yield _app


@pytest.fixture
def client(fastapi_app):
    """Starlette TestClient — same sync HTTP interface as Flask's test_client().

    Usage in tests:
        response = client.get("/api/health/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    Note: Remove all `with app.app_context():` blocks — not needed in FastAPI.
    """
    with TestClient(fastapi_app, raise_server_exceptions=True) as c:
        yield c
