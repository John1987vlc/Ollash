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
        "max_iterations": 5,
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
    assert isinstance(code_agent.logger, AgentLogger)
    assert code_agent.ollama is not None
    assert code_agent.tool_executor is not None
    assert code_agent.file_system_tools is not None
    assert code_agent.code_analysis_tools is not None
    assert code_agent.command_line_tools is not None
    assert code_agent.git_operations_tools is not None
    assert code_agent.planning_tools is not None
    # Initially, the orchestrator should only have planning tools
    expected_orchestrator_tools = {
        "plan_actions", "select_agent_type", "evaluate_plan_risk", "detect_user_intent",
        "require_human_gate", "summarize_session_state", "explain_decision",
        "validate_environment_expectations", "detect_configuration_drift",
        "evaluate_compliance", "generate_audit_report", "propose_governance_policy",
        "estimate_change_blast_radius", "generate_runbook"
    }
    assert set(code_agent.tool_functions.keys()) == expected_orchestrator_tools
    assert code_agent.active_agent_type == "orchestrator"

def test_list_directory_tool(code_agent, temp_project_root):
    # Create some dummy files/dirs
    (temp_project_root / "test_dir").mkdir()
    (temp_project_root / "test_file.txt").write_text("content")

    # Mock responses:
    # 1. LLM decides to switch to 'code' agent type
    # 2. LLM decides to call 'list_directory' tool (after agent type switch)
    # 3. LLM returns final answer
    code_agent.ollama.chat.side_effect = [
        # First call: LLM selects 'code' agent type
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # Second call (after agent type switch): LLM calls list_directory
        (
            {"message": {"tool_calls": [{"function": {"name": "list_directory", "arguments": {"path": "."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # Third call (after tool execution): LLM returns final answer
        ({"message": {"content": "Directory listing completed."}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    # Mock system prompt loading for 'code' agent
    # Create a dummy prompts/code/default_code_agent.json
    code_prompt_dir = temp_project_root / "prompts" / "code"
    code_prompt_dir.mkdir(parents=True, exist_ok=True)
    (code_prompt_dir / "default_code_agent.json").write_text(json.dumps({
        "prompt": "You are a code agent. Your tools are file system and code analysis.",
        "tools": ["plan_actions", "analyze_project", "read_file", "read_files", "write_file", "delete_file", "file_diff", "summarize_file", "summarize_files", "search_code", "run_command", "run_tests", "validate_change", "git_status", "git_commit", "git_push", "list_directory", "select_agent_type"]
    }))

    # Execute chat command
    response = code_agent.chat("List contents of current directory")

    # Assertions
    assert code_agent.ollama.chat.call_count == 3
    assert "Directory listing completed." in response
    assert code_agent.active_agent_type == "code"
    assert "list_directory" in code_agent.tool_functions


def test_read_file_tool(code_agent, temp_project_root):
    test_file = temp_project_root / "my_file.txt"
    test_file.write_text("Hello, world!")

    # Mock responses:
    # 1. LLM decides to switch to 'code' agent type
    # 2. LLM decides to call 'read_file' tool (after agent type switch)
    # 3. LLM returns final answer
    code_agent.ollama.chat.side_effect = [
        # First call: LLM selects 'code' agent type
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # Second call (after agent type switch): LLM calls read_file
        (
            {"message": {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "my_file.txt"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # Third call (after tool execution): LLM returns final answer
        ({"message": {"content": "Content of my_file.txt: Hello, world!"}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    # Mock system prompt loading for 'code' agent
    # Create a dummy prompts/code/default_code_agent.json
    code_prompt_dir = temp_project_root / "prompts" / "code"
    code_prompt_dir.mkdir(parents=True, exist_ok=True)
    (code_prompt_dir / "default_code_agent.json").write_text(json.dumps({
        "prompt": "You are a code agent. Your tools are file system and code analysis.",
        "tools": ["plan_actions", "analyze_project", "read_file", "read_files", "write_file", "delete_file", "file_diff", "summarize_file", "summarize_files", "search_code", "run_command", "run_tests", "validate_change", "git_status", "git_commit", "git_push", "list_directory", "select_agent_type"]
    }))

    response = code_agent.chat("Read my_file.txt")

    assert code_agent.ollama.chat.call_count == 3
    assert "Content of my_file.txt: Hello, world!" in response
    assert code_agent.active_agent_type == "code"
    assert "read_file" in code_agent.tool_functions


@patch('builtins.input', side_effect=['yes'])
def test_write_file_tool_confirmation_yes(mock_input, code_agent, temp_project_root):
    target_file = temp_project_root / "new_file.txt"
    content = "New content for testing."

    # Mock responses:
    # 1. LLM decides to switch to 'code' agent type
    # 2. LLM decides to call 'write_file' tool (after agent type switch)
    # 3. LLM returns final answer
    code_agent.ollama.chat.side_effect = [
        # First call: LLM selects 'code' agent type
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # Second call (after agent type switch): LLM calls write_file
        (
            {"message": {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "new_file.txt", "content": content, "reason": "test"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # Third call (after tool execution): LLM returns final answer
        ({"message": {"content": "File new_file.txt written successfully."}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    # Mock system prompt loading for 'code' agent
    code_prompt_dir = temp_project_root / "prompts" / "code"
    code_prompt_dir.mkdir(parents=True, exist_ok=True)
    (code_prompt_dir / "default_code_agent.json").write_text(json.dumps({
        "prompt": "You are a code agent. Your tools are file system and code analysis.",
        "tools": ["plan_actions", "analyze_project", "read_file", "read_files", "write_file", "delete_file", "file_diff", "summarize_file", "summarize_files", "search_code", "run_command", "run_tests", "validate_change", "git_status", "git_commit", "git_push", "list_directory", "select_agent_type"]
    }))

    response = code_agent.chat("Write new_file.txt with some content")

    assert code_agent.ollama.chat.call_count == 3
    mock_input.assert_called_once_with(f"{Fore.GREEN}Proceed? (yes/no/view): {Style.RESET_ALL}")
    assert target_file.exists()
    assert target_file.read_text() == content
    assert "written successfully." in response
    assert code_agent.active_agent_type == "code"
    assert "write_file" in code_agent.tool_functions


@patch('builtins.input', side_effect=['no'])


def test_write_file_tool_confirmation_no(mock_input, code_agent, temp_project_root):


    target_file = temp_project_root / "another_file.txt"


    content = "Content that should not be written."





    # Mock responses:


    # 1. LLM decides to switch to 'code' agent type


    # 2. LLM decides to call 'write_file' tool (after agent type switch)


    # 3. LLM returns final answer


    code_agent.ollama.chat.side_effect = [


        # First call: LLM selects 'code' agent type


        (


            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code"}}}]}},


            {"prompt_tokens": 10, "completion_tokens": 5}


        ),


        # Second call (after agent type switch): LLM calls write_file


        (


            {"message": {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "another_file.txt", "content": content, "reason": "test"}}}]}},


            {"prompt_tokens": 10, "completion_tokens": 5}


        ),


        # Third call (after tool execution): LLM returns final answer


        ({"message": {"content": "File write cancelled."}}, {"prompt_tokens": 5, "completion_tokens": 3})


    ]





    # Mock system prompt loading for 'code' agent


    code_prompt_dir = temp_project_root / "prompts" / "code"


    code_prompt_dir.mkdir(parents=True, exist_ok=True)


    (code_prompt_dir / "default_code_agent.json").write_text(json.dumps({


        "prompt": "You are a code agent. Your tools are file system and code analysis.",


        "tools": ["plan_actions", "analyze_project", "read_file", "read_files", "write_file", "delete_file", "file_diff", "summarize_file", "summarize_files", "search_code", "run_command", "run_tests", "validate_change", "git_status", "git_commit", "git_push", "list_directory", "select_agent_type"]


    }))





    response = code_agent.chat("Attempt to write another_file.txt but deny")





    assert code_agent.ollama.chat.call_count == 3


    mock_input.assert_called_once_with(f"{Fore.GREEN}Proceed? (yes/no/view): {Style.RESET_ALL}")


    assert not target_file.exists()


    assert "cancelled." in response


    assert code_agent.active_agent_type == "code"


    assert "write_file" in code_agent.tool_functions

