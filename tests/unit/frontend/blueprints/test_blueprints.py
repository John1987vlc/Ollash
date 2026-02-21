import pytest
from pathlib import Path


@pytest.fixture
def app():
    from frontend.app import create_app

    # Use absolute root path
    root = Path(__file__).parent.parent.parent.parent.parent
    app = create_app(ollash_root_dir=root)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestCommonBlueprint:
    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Ollash" in resp.data

    def test_index_has_agent_cards(self, client):
        resp = client.get("/")
        assert b"agent-card" in resp.data
        assert b"orchestrator" in resp.data


class TestChatBlueprint:
    def test_chat_requires_message(self, client):
        resp = client.get("/chat")
        assert resp.status_code == 200
        assert b"chat-view" in resp.data
