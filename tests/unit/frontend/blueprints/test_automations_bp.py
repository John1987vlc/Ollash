import pytest
from unittest.mock import MagicMock, patch
import sys
from flask import Flask

# Import the blueprint object
from frontend.blueprints.automations_bp import automations_bp, init_app


@pytest.fixture
def mock_scheduler():
    return MagicMock()


@pytest.fixture
def mock_executor():
    return MagicMock()


@pytest.fixture
def app(tmp_path, mock_scheduler, mock_executor, monkeypatch):
    """Create app and forcefully inject mocks into the blueprint module namespace."""
    app = Flask(__name__)
    app.config.update({"TESTING": True, "ollash_root_dir": tmp_path, "SECRET_KEY": "test_secret"})

    # Access the module directly to bypass Blueprint object name shadowing
    target_module = sys.modules["frontend.blueprints.automations_bp"]

    # Inject mocks directly into the module's globals
    monkeypatch.setattr(target_module, "get_scheduler", lambda: mock_scheduler)
    monkeypatch.setattr(target_module, "get_task_executor", lambda *args: mock_executor)
    monkeypatch.setattr(target_module, "_scheduler", mock_scheduler)
    monkeypatch.setattr(target_module, "_executor", mock_executor)
    monkeypatch.setattr(target_module, "_scheduled_tasks", {})
    monkeypatch.setattr(target_module, "render_template", MagicMock(return_value="<html></html>"))

    # Ensure init_app uses our mocks
    init_app(app, MagicMock())

    app.register_blueprint(automations_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def bp_module():
    return sys.modules["frontend.blueprints.automations_bp"]


class TestAutomationsBlueprint:
    """Test suite for task automation scheduling endpoints with total module-level isolation."""

    def test_automations_page_renders(self, client):
        response = client.get("/automations")
        assert response.status_code == 200

    def test_get_automations_empty(self, client):
        response = client.get("/api/automations")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_create_automation_success(self, client, mock_scheduler):
        payload = {"name": "Test Task", "agent": "code", "prompt": "Optimize this", "schedule": "daily"}
        response = client.post("/api/automations", json=payload)
        assert response.status_code == 201
        mock_scheduler.schedule_task.assert_called_once()

    def test_create_automation_missing_fields(self, client):
        response = client.post("/api/automations", json={"name": "incomplete"})
        assert response.status_code == 400

    def test_delete_automation_success(self, client, mock_scheduler, bp_module):
        task_id = "task_del"
        bp_module._scheduled_tasks[task_id] = {"name": "Del"}
        response = client.delete(f"/api/automations/{task_id}")
        assert response.status_code == 200
        assert task_id not in bp_module._scheduled_tasks
        mock_scheduler.unschedule_task.assert_called_with(task_id)

    def test_toggle_automation_active_to_inactive(self, client, mock_scheduler, bp_module):
        task_id = "task_toggle"
        bp_module._scheduled_tasks[task_id] = {"name": "Toggle", "status": "active"}
        response = client.put(f"/api/automations/{task_id}/toggle")
        assert response.status_code == 200
        assert bp_module._scheduled_tasks[task_id]["status"] == "inactive"
        mock_scheduler.pause_task.assert_called_with(task_id)

    def test_run_automation_now_success(self, client, bp_module):
        task_id = "task_run"
        bp_module._scheduled_tasks[task_id] = {"name": "Run"}
        with patch("threading.Thread") as mock_thread:
            response = client.post(f"/api/automations/{task_id}/run")
            assert response.status_code == 200
            assert mock_thread.called
            assert "lastRun" in bp_module._scheduled_tasks[task_id]

    def test_get_automations_populated(self, client, bp_module):
        bp_module._scheduled_tasks["t1"] = {"name": "T1", "status": "active"}
        response = client.get("/api/automations")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]["id"] == "t1"
