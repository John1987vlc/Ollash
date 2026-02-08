import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import json
import os
from colorama import Fore, Style

# Removed imports: DefaultAgent, ExecutionResult, SandboxLevel
from src.utils.core.agent_logger import AgentLogger


# Rely on conftest.py for mock_ollama_client and temp_project_root fixtures



# ==============================================================================
# TESTS
# ==============================================================================

def test_code_agent_initialization(default_agent, temp_project_root):
    assert default_agent.project_root == temp_project_root
    assert isinstance(default_agent.logger, AgentLogger)
    assert default_agent.ollama is not None
    assert default_agent.tool_executor is not None
    # Initially, the orchestrator should only have planning tools
    expected_orchestrator_tools = {
        "plan_actions", "select_agent_type", "evaluate_plan_risk", "detect_user_intent",
        "require_human_gate", "summarize_session_state", "explain_decision",
        "validate_environment_expectations", "detect_configuration_drift",
        "evaluate_compliance", "generate_audit_report", "propose_governance_policy",
        "estimate_change_blast_radius", "generate_runbook",
        "analyze_sentiment", "generate_creative_content", "translate_text"
    }
    assert set(default_agent.active_tool_names) == expected_orchestrator_tools
    assert default_agent.active_agent_type == "orchestrator"

def test_list_directory_tool(default_agent, temp_project_root):
    # Create some dummy files/dirs
    (temp_project_root / "test_dir").mkdir()
    (temp_project_root / "test_file.txt").write_text("content")

    default_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: List contents."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: _classify_intent (Returns a message, not a tool call directly)
        ({"message": {"content": "Intent: code"}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Main orchestrator LLM decides to call 'select_agent_type'
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User wants to list directory."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 4th call (after agent type switch): Main code agent LLM calls list_directory
        (
            {"message": {"tool_calls": [{"function": {"name": "list_directory", "arguments": {"path": "."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 5th call (after tool execution): Main code agent LLM returns final answer
        ({"message": {"content": "Directory listing completed."}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    # Execute chat command
    response = default_agent.chat("List contents of current directory")

    # Assertions
    assert default_agent.ollama.chat.call_count == 5
    assert "Directory listing completed." in response
    assert default_agent.active_agent_type == "code"
    assert "list_directory" in default_agent.active_tool_names


def test_read_file_tool(default_agent, temp_project_root):
    test_file = temp_project_root / "my_file.txt"
    test_file.write_text("Hello, world!")

    default_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Read file."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: _classify_intent (Returns a message, not a tool call directly)
        ({"message": {"content": "Intent: code"}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Main orchestrator LLM decides to call 'select_agent_type'
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User wants to read a file."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 4th call (after agent type switch): Main code agent LLM calls read_file
        (
            {"message": {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "my_file.txt"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 5th call (after tool execution): Main code agent LLM returns final answer
        ({"message": {"content": "Content of my_file.txt: Hello, world!"}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    response = default_agent.chat("Read my_file.txt")

    assert default_agent.ollama.chat.call_count == 5
    assert "Content of my_file.txt: Hello, world!" in response
    assert default_agent.active_agent_type == "code"
    assert "read_file" in default_agent.active_tool_names


@patch('builtins.input', side_effect=['yes'])
def test_write_file_tool_confirmation_yes(mock_input, default_agent, temp_project_root):
    target_file = temp_project_root / "new_file.txt"
    content = "New content for testing."

    default_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Write file."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: _classify_intent (Returns a message, not a tool call directly)
        ({"message": {"content": "Intent: code"}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Main orchestrator LLM decides to call 'select_agent_type'
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User wants to write a file."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 4th call (after agent type switch): Main code agent LLM calls write_file
        (
            {"message": {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "new_file.txt", "content": content, "reason": "test"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 5th call (after tool execution): Main code agent LLM returns final answer
        ({"message": {"content": "File new_file.txt written successfully."}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    response = default_agent.chat("Write new_file.txt with some content")

    assert default_agent.ollama.chat.call_count == 5
    mock_input.assert_called_once_with(f"{Fore.GREEN}Proceed? (yes/no/view): {Style.RESET_ALL}")
    assert target_file.exists()
    assert target_file.read_text() == content
    assert "written successfully." in response
    assert default_agent.active_agent_type == "code"
    assert "write_file" in default_agent.active_tool_names


@patch('builtins.input', side_effect=['no'])
def test_write_file_tool_confirmation_no(mock_input, default_agent, temp_project_root):
    target_file = temp_project_root / "another_file.txt"
    content = "Content that should not be written."

    default_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Attempt write."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: _classify_intent (Returns a message, not a tool call directly)
        ({"message": {"content": "Intent: code"}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Main orchestrator LLM decides to call 'select_agent_type'
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User wants to write a file."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 4th call (after agent type switch): Main code agent LLM calls write_file
        (
            {"message": {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "another_file.txt", "content": content, "reason": "test"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 5th call (after tool execution): Main code agent LLM returns final answer
        ({"message": {"content": "File write cancelled."}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    response = default_agent.chat("Attempt to write another_file.txt but deny")

    assert default_agent.ollama.chat.call_count == 5
    mock_input.assert_called_once_with(f"{Fore.GREEN}Proceed? (yes/no/view): {Style.RESET_ALL}")
    assert not target_file.exists()
    assert "cancelled." in response
    assert default_agent.active_agent_type == "code"
    assert "write_file" in default_agent.active_tool_names

