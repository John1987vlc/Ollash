import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import json
import os
from colorama import Fore, Style # Added import

from src.agents.code_agent import CodeAgent
from src.utils.command_executor import ExecutionResult, SandboxLevel
from src.utils.agent_logger import AgentLogger # Added import for AgentLogger


# Mock external dependencies for isolated testing
@pytest.fixture
def mock_ollama_client():
    with patch('src.agents.code_agent.OllamaClient') as MockClient:
        instance = MockClient.return_value
        instance.chat.return_value = (
            {"message": {"content": "Mocked response"}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        )
        yield instance

@pytest.fixture
def temp_project_root(tmp_path):
    # Create a dummy config file
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text(json.dumps({
        "model": "test-model",
        "ollama_url": "http://localhost:11434",
        "system_prompt": "Test system prompt",
        "max_iterations": 2,
        "timeout": 300
    }))
    # Create an agent.log file as the agent expects it
    (tmp_path / "agent.log").touch()
    yield tmp_path

@pytest.fixture
def code_agent(temp_project_root, mock_ollama_client):
    agent = CodeAgent(project_root=str(temp_project_root))
    # Replace the actual OllamaClient with the mock
    agent.ollama = mock_ollama_client
    return agent

# ==============================================================================
# TESTS
# ==============================================================================

def test_code_agent_initialization(code_agent, temp_project_root):
    assert code_agent.project_root == temp_project_root
    assert isinstance(code_agent.logger, AgentLogger) # Changed from MagicMock to AgentLogger
    assert code_agent.ollama is not None
    assert code_agent.tool_executor is not None
    assert code_agent.file_system_tools is not None
    assert code_agent.code_analysis_tools is not None
    assert code_agent.command_line_tools is not None
    assert code_agent.git_operations_tools is not None
    assert code_agent.planning_tools is not None
    assert "plan_actions" in code_agent.tool_functions
    assert "read_file" in code_agent.tool_functions

def test_list_directory_tool(code_agent, temp_project_root):
    # Create some dummy files/dirs
    (temp_project_root / "test_dir").mkdir()
    (temp_project_root / "test_file.txt").write_text("content")

    # Mock the tool call response from the LLM
    code_agent.ollama.chat.return_value = (
        {"message": {"tool_calls": [{"function": {"name": "list_directory", "arguments": {"path": "."}}}]}},
        {"prompt_tokens": 10, "completion_tokens": 5}
    )

    # Mock the subsequent LLM response after tool execution (final answer)
    code_agent.ollama.chat.side_effect = [
        (
            {"message": {"tool_calls": [{"function": {"name": "list_directory", "arguments": {"path": "."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        ({"message": {"content": "Directory listing completed."}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    # Execute chat command
    response = code_agent.chat("List contents of current directory")

    # Assertions
    code_agent.ollama.chat.assert_called()
    assert "Directory listing completed." in response

    # Verify that the actual tool function was called
    # (We rely on CodeAgent.tool_functions to correctly map, so testing the output from the mock is sufficient)
    # The list_directory tool returns a dict with 'items'
    # We can check the logger output or ensure our mock capture this
    # For a deeper integration test, we'd mock the tool's dependencies instead of the tool directly.
    # For simplicity, we just check the chat response logic.


def test_read_file_tool(code_agent, temp_project_root):
    test_file = temp_project_root / "my_file.txt"
    test_file.write_text("Hello, world!")

    # Mock the tool call response from the LLM
    code_agent.ollama.chat.side_effect = [
        (
            {"message": {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "my_file.txt"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        ({"message": {"content": "Content of my_file.txt: Hello, world!"}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    response = code_agent.chat("Read my_file.txt")

    code_agent.ollama.chat.assert_called()
    assert "Content of my_file.txt: Hello, world!" in response


@patch('builtins.input', side_effect=['yes'])
def test_write_file_tool_confirmation_yes(mock_input, code_agent, temp_project_root):
    target_file = temp_project_root / "new_file.txt"
    content = "New content for testing."

    # Mock the tool call response from the LLM
    code_agent.ollama.chat.side_effect = [
        (
            {"message": {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "new_file.txt", "content": content, "reason": "test"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        ({"message": {"content": "File new_file.txt written successfully."}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    response = code_agent.chat("Write new_file.txt with some content")

    mock_input.assert_called_once_with(f"{Fore.GREEN}Proceed? (yes/no/view): {Style.RESET_ALL}")
    assert target_file.exists()
    assert target_file.read_text() == content
    assert "written successfully." in response


@patch('builtins.input', side_effect=['no'])
def test_write_file_tool_confirmation_no(mock_input, code_agent, temp_project_root):
    target_file = temp_project_root / "another_file.txt"
    content = "Content that should not be written."

    # Mock the tool call response from the LLM
    code_agent.ollama.chat.side_effect = [
        (
            {"message": {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "another_file.txt", "content": content, "reason": "test"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        ({"message": {"content": "File write cancelled."}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    response = code_agent.chat("Attempt to write another_file.txt but deny")

    mock_input.assert_called_once_with(f"{Fore.GREEN}Proceed? (yes/no/view): {Style.RESET_ALL}")
    assert not target_file.exists()
    assert "cancelled." in response