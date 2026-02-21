import json
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from flask import Flask

# Dynamically import the module to avoid Blueprint naming conflicts
aabp_module = importlib.import_module("frontend.blueprints.auto_agent_bp")
auto_agent_bp = aabp_module.auto_agent_bp
init_app = aabp_module.init_app

@pytest.fixture
def app(tmp_path):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["ollash_root_dir"] = tmp_path
    
    mock_event_publisher = MagicMock()
    mock_chat_event_bridge = MagicMock()
    
    init_app(app, mock_event_publisher, mock_chat_event_bridge)
    app.register_blueprint(auto_agent_bp)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_git_status_no_project(client):
    resp = client.get("/api/projects/non_existent/git_status")
    assert resp.status_code == 404

def test_git_status_no_git(client, tmp_path):
    project_name = "test_no_git"
    project_dir = tmp_path / "generated_projects" / "auto_agent_projects" / project_name
    project_dir.mkdir(parents=True)
    
    resp = client.get(f"/api/projects/{project_name}/git_status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["git_enabled"] is False

def test_git_status_enabled(client, tmp_path, monkeypatch):
    project_name = "test_git_enabled"
    project_dir = tmp_path / "generated_projects" / "auto_agent_projects" / project_name
    project_dir.mkdir(parents=True)
    (project_dir / ".git").mkdir()
    
    # Mock GitPRTool
    mock_git_pr_tool_class = MagicMock()
    monkeypatch.setattr(aabp_module, "GitPRTool", mock_git_pr_tool_class)
    mock_git = mock_git_pr_tool_class.return_value
    mock_git.list_open_prs.return_value = [
        {"number": 1, "title": "Test PR", "url": "http://github.com/test/pr/1"}
    ]
    
    # Mock Scheduler
    mock_get_scheduler = MagicMock()
    monkeypatch.setattr(aabp_module, "get_scheduler", mock_get_scheduler)
    mock_scheduler = mock_get_scheduler.return_value
    mock_scheduler.list_all_tasks.return_value = [
        {
            "id": "autonomous_maintenance_hourly",
            "name": "Ollash Autonomous Maintenance",
            "next_run_time": "2026-02-21T15:00:00",
            "paused": False
        }
    ]
    
    resp = client.get(f"/api/projects/{project_name}/git_status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["git_enabled"] is True
    assert data["sync_active"] is True
    assert len(data["prs"]) == 1
    assert data["prs"][0]["number"] == 1

def test_create_project_with_git(client, tmp_path, monkeypatch):
    # Mock AutoAgent.run
    mock_agent_class = MagicMock()
    monkeypatch.setattr(aabp_module, "AutoAgent", mock_agent_class)
    mock_agent_instance = mock_agent_class.return_value
    mock_agent_instance.run.return_value = tmp_path / "generated_projects" / "auto_agent_projects" / "test_project"
    
    # Mock scheduler
    mock_get_scheduler = MagicMock()
    monkeypatch.setattr(aabp_module, "get_scheduler", mock_get_scheduler)
    mock_scheduler_instance = mock_get_scheduler.return_value
    mock_scheduler_instance.scheduler = MagicMock()
    
    # Mock project root path
    project_root = tmp_path / "generated_projects" / "auto_agent_projects" / "test_project"
    project_root.mkdir(parents=True)
    
    # Bypass require_api_key
    monkeypatch.setattr("frontend.middleware.require_api_key", lambda x: x)
    
    resp = client.post("/api/projects/create", data={
        "project_name": "test_project",
        "project_description": "test description",
        "git_url": "https://github.com/user/repo.git",
        "enable_hourly_pr": "true"
    })
    
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "started"
