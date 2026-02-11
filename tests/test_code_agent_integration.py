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
    assert default_agent.llm_clients['default'] is not None
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

    # Mock the orchestration client for pre-processing and intent classification
    default_agent.llm_clients['orchestration'].achat.side_effect = [
        ({"message": {"content": "Refined English instruction: List contents."}}, {"prompt_tokens": 10, "completion_tokens": 5}), # For _preprocess_instruction
        ({"message": {"content": "Code Generation"}}, {"prompt_tokens": 10, "completion_tokens": 5}), # For _classify_intent (should return full intent string)
    ]

    # Mock the main (default) client's achat calls
    # This assumes the main loop starts with the default client, then switches.
    default_agent.llm_clients['default'].achat.side_effect = [
        # 1st call: Main agent LLM decides to call 'select_agent_type'
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User wants to list directory."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
    ]

    # Mock the responses for the coder client (after agent type switch)
    default_agent.llm_clients['coder'].achat.side_effect = [
        # 1st call (from coder, after agent type switch): Main code agent LLM calls list_directory
        (
            {"message": {"tool_calls": [{"function": {"name": "list_directory", "arguments": {"path": "."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 2nd call (from coder, after tool execution): Main code agent LLM returns final answer
        ({"message": {"content": "Directory listing completed."}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    # Minimal mocks for other clients involved in ModelRouter to prevent hangs
    default_agent.llm_clients['senior_reviewer'].achat.side_effect = [
        ({"message": {"content": "senior reviewer passing through"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
        ({"message": {"content": "senior reviewer passing through"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
    ]
    default_agent.llm_clients['prototyper'].achat.side_effect = [
        ({"message": {"content": "prototyper did nothing"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
        ({"message": {"content": "prototyper did nothing"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
    ]
    # No need to mock default client beyond the first select_agent_type call
    # as subsequent calls for it should not occur if switch is successful.

    # Execute chat command
    response = await default_agent.chat("List contents of current directory")

    # Assertions
    assert default_agent.llm_clients['orchestration'].achat.call_count == 2
    assert default_agent.llm_clients['default'].achat.call_count == 1 # Just for select_agent_type
    assert default_agent.llm_clients['coder'].achat.call_count == 2
    assert default_agent.llm_clients['senior_reviewer'].achat.call_count >= 1
    assert default_agent.llm_clients['prototyper'].achat.call_count >= 1 # Prototyper might be called by ModelRouter
    assert "Directory listing completed." in response
    assert default_agent.active_agent_type == "code"
    assert "list_directory" in default_agent.active_tool_names


@pytest.mark.asyncio
async def test_read_file_tool(default_agent, temp_project_root):
    test_file = temp_project_root / "my_file.txt"
    test_file.write_text("Hello, world!")

    # Mock the orchestration client for pre-processing and intent classification
    default_agent.llm_clients['orchestration'].achat.side_effect = [
        ({"message": {"content": "Refined English instruction: Read file."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        ({"message": {"content": "Code Generation"}}, {"prompt_tokens": 10, "completion_tokens": 5}), # Needs to be "Code Generation"
    ]

    # Mock the main (default) client's achat calls
    # This assumes the main loop starts with the default client, then switches.
    default_agent.llm_clients['default'].achat.side_effect = [
        # 1st call: Main agent LLM decides to call 'select_agent_type'
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User wants to read a file."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
    ]

    # Mock the responses for the coder client (after agent type switch)
    default_agent.llm_clients['coder'].achat.side_effect = [
        # 1st call (from coder, after agent type switch): Main code agent LLM calls read_file
        (
            {"message": {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "my_file.txt"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 2nd call (from coder, after tool execution): Main code agent LLM returns final answer
        ({"message": {"content": "Content of my_file.txt: Hello, world!"}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    # Minimal mocks for other clients involved in ModelRouter to prevent hangs
    default_agent.llm_clients['senior_reviewer'].achat.side_effect = [
        ({"message": {"content": "senior reviewer passing through"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
        ({"message": {"content": "senior reviewer passing through"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
    ]
    default_agent.llm_clients['prototyper'].achat.side_effect = [
        ({"message": {"content": "prototyper did nothing"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
        ({"message": {"content": "prototyper did nothing"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
    ]
    # No need to mock default client beyond the first select_agent_type call
    # as subsequent calls for it should not occur if switch is successful.


    response = await default_agent.chat("Read my_file.txt")

    assert default_agent.llm_clients['orchestration'].achat.call_count == 2
    assert default_agent.llm_clients['default'].achat.call_count == 1 # Just for select_agent_type
    assert default_agent.llm_clients['coder'].achat.call_count == 2
    assert default_agent.llm_clients['senior_reviewer'].achat.call_count >= 1
    assert default_agent.llm_clients['prototyper'].achat.call_count >= 1
    assert "Content of my_file.txt: Hello, world!" in response
    assert default_agent.active_agent_type == "code"
    assert "read_file" in default_agent.active_tool_names


@pytest.mark.asyncio
@patch('builtins.input', side_effect=['yes'])
async def test_write_file_tool_confirmation_yes(mock_input, default_agent, temp_project_root):
    target_file = temp_project_root / "new_file.txt"
    content = "New content for testing."

    # Mock the orchestration client for pre-processing and intent classification
    default_agent.llm_clients['orchestration'].achat.side_effect = [
        ({"message": {"content": "Refined English instruction: Write file."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        ({"message": {"content": "Code Generation"}}, {"prompt_tokens": 10, "completion_tokens": 5}), # Needs to be "Code Generation"
    ]

    # Mock the main (default) client's achat calls
    # This assumes the main loop starts with the default client, then switches.
    default_agent.llm_clients['default'].achat.side_effect = [
        # 1st call: Main agent LLM decides to call 'select_agent_type'
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User wants to write a file."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
    ]

    # Mock the responses for the coder client (after agent type switch)
    default_agent.llm_clients['coder'].achat.side_effect = [
        # 1st call (from coder, after agent type switch): Main code agent LLM calls write_file
        (
            {"message": {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "new_file.txt", "content": content, "reason": "test"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 2nd call (from coder, after tool execution): Main code agent LLM returns final answer
        ({"message": {"content": "File new_file.txt written successfully."}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    # Minimal mocks for other clients involved in ModelRouter to prevent hangs
    default_agent.llm_clients['senior_reviewer'].achat.side_effect = [
        ({"message": {"content": "senior reviewer passing through"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
        ({"message": {"content": "senior reviewer passing through"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
    ]
    default_agent.llm_clients['prototyper'].achat.side_effect = [
        ({"message": {"content": "prototyper did nothing"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
        ({"message": {"content": "prototyper did nothing"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
    ]

    response = await default_agent.chat("Write new_file.txt with some content")

    assert default_agent.llm_clients['orchestration'].achat.call_count == 2
    assert default_agent.llm_clients['default'].achat.call_count == 1 # Just for select_agent_type
    assert default_agent.llm_clients['coder'].achat.call_count == 2
    assert default_agent.llm_clients['senior_reviewer'].achat.call_count >= 1
    assert default_agent.llm_clients['prototyper'].achat.call_count >= 1
    assert "File new_file.txt written successfully." in response
    mock_input.assert_called_once_with(f"{Fore.GREEN}Proceed? (yes/no/view): {Style.RESET_ALL}")
    assert target_file.exists()
    assert target_file.read_text() == content
    assert "written successfully." in response
    assert default_agent.active_agent_type == "code"
    assert "write_file" in default_agent.active_tool_names


@pytest.mark.asyncio
@patch('builtins.input', side_effect=['no'])
async def test_write_file_tool_confirmation_no(mock_input, default_agent, temp_project_root):
    agent = await default_agent
    target_file = temp_project_root / "another_file.txt"
    content = "Content that should not be written."

    # Mock the orchestration client for pre-processing and intent classification
    default_agent.llm_clients['orchestration'].achat.side_effect = [
        ({"message": {"content": "Refined English instruction: Attempt write."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        ({"message": {"content": "Code Generation"}}, {"prompt_tokens": 10, "completion_tokens": 5}), # Needs to be "Code Generation"
    ]

    # Mock the main (default) client's achat calls
    # This assumes the main loop starts with the default client, then switches.
    default_agent.llm_clients['default'].achat.side_effect = [
        # 1st call: Main agent LLM decides to call 'select_agent_type'
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User wants to write a file."}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
    ]

    # Mock the responses for the coder client (after agent type switch)
    default_agent.llm_clients['coder'].achat.side_effect = [
        # 1st call (from coder, after agent type switch): Main code agent LLM calls write_file
        (
            {"message": {"tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "another_file.txt", "content": content, "reason": "test"}}}]}},
            {"prompt_tokens": 10, "completion_tokens": 5}
        ),
        # 2nd call (from coder, after tool execution): Main code agent LLM returns final answer
        ({"message": {"content": "File write cancelled."}}, {"prompt_tokens": 5, "completion_tokens": 3})
    ]

    # Minimal mocks for other clients involved in ModelRouter to prevent hangs
    default_agent.llm_clients['senior_reviewer'].achat.side_effect = [
        ({"message": {"content": "senior reviewer passing through"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
        ({"message": {"content": "senior reviewer passing through"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
    ]
    default_agent.llm_clients['prototyper'].achat.side_effect = [
        ({"message": {"content": "prototyper did nothing"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
        ({"message": {"content": "prototyper did nothing"}}, {"prompt_tokens": 1, "completion_tokens": 1}),
    ]

    response = await default_agent.chat("Attempt to write another_file.txt but deny")

    assert default_agent.llm_clients['orchestration'].achat.call_count == 2
    assert default_agent.llm_clients['default'].achat.call_count == 1 # Just for select_agent_type
    assert default_agent.llm_clients['coder'].achat.call_count == 2
    assert default_agent.llm_clients['senior_reviewer'].achat.call_count >= 1
    assert default_agent.llm_clients['prototyper'].achat.call_count >= 1
    assert "File write cancelled." in response
    mock_input.assert_called_once_with(f"{Fore.GREEN}Proceed? (yes/no/view): {Style.RESET_ALL}")
    assert not target_file.exists()
    assert "cancelled." in response
    assert default_agent.active_agent_type == "code"
    assert "write_file" in default_agent.active_tool_names

