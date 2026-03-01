import pytest
from pathlib import Path
from unittest.mock import MagicMock
from backend.agents.auto_agent import AutoAgent


@pytest.fixture
def mock_deps():
    return {
        "phase_context": MagicMock(),
        "phases": [],
        "project_analysis_phase_factory": MagicMock(),
        "kernel": MagicMock(),
        "llm_manager": MagicMock(),
        "llm_recorder": MagicMock(),
        "dependency_scanner": MagicMock(),
    }


@pytest.fixture
def agent(mock_deps):
    mock_deps["kernel"].get_full_config.return_value = {"models": {"writer": "qwen"}}
    mock_deps["phase_context"].generated_projects_dir = Path("/tmp/projects")
    return AutoAgent(**mock_deps)


def test_manage_github_issues_basic(agent):
    agent.git_tool = MagicMock()
    agent.git_tool.create_issue.return_value = {"success": True, "number": 123}

    structure = {
        "tasks": [
            {"id": "T1", "title": "Task 1", "description": "Desc 1"},
            {"id": "T2", "title": "Task 2", "description": "Desc 2", "dependencies": ["T1"]},
        ]
    }
    agent.phase_context.backlog = []  # Use structure

    agent._manage_github_issues(structure)

    assert agent.git_tool.create_issue.call_count == 2
    # Verify linking call (second pass)
    agent.git_tool.update_issue_body.assert_called_with(123, "Desc 2\n\n🚫 Blocked by: #123")


@pytest.mark.asyncio
async def test_update_ollash_manifest(agent):
    mock_writer = MagicMock()
    mock_writer.chat.return_value = ({"content": "# Manifest content"}, {})
    agent.llm_manager.get_client.return_value = mock_writer

    agent.phase_context.backlog = [{"status": "done", "github_number": 1}]
    agent.phase_context.initial_exec_params = {"project_name": "test"}

    content = await agent._update_ollash_manifest("T1")
    assert content == "# Manifest content"
    agent.llm_manager.get_client.assert_called_with("writer")


def test_finalize_project(agent):
    execution_plan = MagicMock()
    project_root = Path("/tmp/project")
    agent.event_publisher = MagicMock()

    agent._finalize_project("test", project_root, 5, execution_plan)

    execution_plan.mark_complete.assert_called_once()
    agent.phase_context.file_manager.write_file.assert_called()
    assert agent.event_publisher.publish.call_count >= 2
