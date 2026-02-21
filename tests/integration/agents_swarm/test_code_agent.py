import json

import pytest

from backend.agents.default_agent import DefaultAgent


@pytest.fixture
def default_agent(tmp_path, monkeypatch):
    """Fixture to create a DefaultAgent in a temporary directory."""
    models_config = {
        "agent_roles": {
            "coder": "test-coder",
            "default": "test-default",
        }
    }
    monkeypatch.setenv("LLM_MODELS_JSON", json.dumps(models_config))
    from backend.core.config import reload_config

    reload_config()

    project_root = tmp_path / "ollash_test_project"
    project_root.mkdir()
    (project_root / ".ollash").mkdir()
    agent = DefaultAgent(project_root=str(project_root))
    return agent


@pytest.mark.asyncio
async def test_code_agent_initialization(default_agent):
    """Test that the Code Agent initializes correctly."""
    assert default_agent is not None
    assert default_agent.project_root is not None
    assert default_agent.llm_manager is not None
    assert default_agent.llm_manager.get_client("coder") is not None


@pytest.mark.asyncio
async def test_list_directory_tool(default_agent, tmp_path):
    """Test the list_directory tool."""
    (tmp_path / "ollash_test_project" / "test_file.txt").touch()
    result = await default_agent.tool_executor.execute_tool("list_directory", path=".")
    assert "test_file.txt" in result["items"]


@pytest.mark.asyncio
async def test_read_file_tool(default_agent, tmp_path):
    """Test the read_file tool."""
    test_file = tmp_path / "ollash_test_project" / "test_file.txt"
    test_file.write_text("hello world")
    result = await default_agent.tool_executor.execute_tool("read_file", path="test_file.txt")
    assert result["content"] == "hello world"


@pytest.mark.asyncio
async def test_write_file_tool_confirmation_yes(default_agent, tmp_path, monkeypatch):
    """Test the write_file tool with user confirmation."""
    monkeypatch.setattr("builtins.input", lambda _: "y")
    file_path = "new_file.txt"
    content = "new content"
    result = await default_agent.tool_executor.execute_tool(
        "write_file", path=file_path, content=content, reason="test"
    )
    assert result["ok"]
    assert (tmp_path / "ollash_test_project" / file_path).read_text() == content


@pytest.mark.asyncio
async def test_write_file_tool_confirmation_no(default_agent, tmp_path, monkeypatch):
    """Test the write_file tool with user rejection."""
    monkeypatch.setattr("builtins.input", lambda _: "n")
    file_path = "new_file.txt"
    content = "new content"
    result = await default_agent.tool_executor.execute_tool(
        "write_file", path=file_path, content=content, reason="test"
    )
    assert not result["ok"]
    assert "user_cancelled" in result["error"]
    assert not (tmp_path / "ollash_test_project" / file_path).exists()
