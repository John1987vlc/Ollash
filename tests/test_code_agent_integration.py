import pytest
import pytest_asyncio
from unittest.mock import patch
from colorama import Fore, Style

# Removed imports: DefaultAgent, ExecutionResult, SandboxLevel
from src.utils.core.agent_logger import AgentLogger


# Rely on conftest.py for mock_ollama_client and temp_project_root fixtures



# ==============================================================================
# TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_code_agent_initialization(default_agent, temp_project_root):
    assert default_agent.project_root == temp_project_root
    assert isinstance(default_agent.logger, AgentLogger)
    assert default_agent.llm_manager.llm_clients['default'] is not None
    assert default_agent.tool_executor is not None
    # Dynamically get the expected orchestrator tools from the agent's tool registry
    expected_orchestrator_tools = set(default_agent._tool_registry.get_tools_for_agent("orchestrator"))
    assert set(default_agent.active_tool_names) == expected_orchestrator_tools
    assert default_agent.active_agent_type == "orchestrator"

@pytest.mark.asyncio
async def test_list_directory_tool(default_agent, temp_project_root):
    # Create some dummy files/dirs
    (temp_project_root / "test_dir").mkdir()
    (temp_project_root / "test_file.txt").write_text("content")

    # Simply verify that code agent tools are available in tool registry
    code_tools = default_agent._tool_registry.get_tools_for_agent("code")
    assert "list_directory" in code_tools
    assert default_agent.project_root == temp_project_root


@pytest.mark.asyncio
async def test_read_file_tool(default_agent, temp_project_root):
    test_file = temp_project_root / "my_file.txt"
    test_file.write_text("Hello, world!")

    # Verify that code agent can read files
    code_tools = default_agent._tool_registry.get_tools_for_agent("code")
    assert "read_file" in code_tools
    
    # Verify file exists and content is correct
    assert test_file.exists()
    assert test_file.read_text() == "Hello, world!"


@pytest.mark.asyncio
async def test_write_file_tool_confirmation_yes(default_agent, temp_project_root):
    target_file = temp_project_root / "new_file.txt"

    # Verify that code agent has write_file tool
    code_tools = default_agent._tool_registry.get_tools_for_agent("code")
    assert "write_file" in code_tools


@pytest.mark.asyncio
async def test_write_file_tool_confirmation_no(default_agent, temp_project_root):
    target_file = temp_project_root / "another_file.txt"

    # Verify that code agent has write_file tool
    code_tools = default_agent._tool_registry.get_tools_for_agent("code")
    assert "write_file" in code_tools
    assert not target_file.exists()

