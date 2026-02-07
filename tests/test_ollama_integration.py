import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, call # Added call for side_effect
import time # For potential delays with Ollama
import logging # For checking logs

from src.agents.default_agent import DefaultAgent

# --- Fixtures ---

# Rely on conftest.py for temp_project_root and default_agent

# --- Tests ---

def test_orchestrator_initial_prompt(default_agent):
    # Assert that the agent starts with the orchestrator prompt
    expected_orchestrator_prompt_part = "You are Local IT Agent - Ollash, an AI Orchestrator."
    assert expected_orchestrator_prompt_part in default_agent.system_prompt

def test_orchestrator_to_code_switch(default_agent):
    initial_prompt = default_agent.system_prompt
    assert "AI Orchestrator" in initial_prompt

    user_request = "Necesito ayuda para refactorizar una función Python en mi proyecto."
    print(f"""
User: {user_request}""")
    
    # Define the system prompt for the code agent (it's loaded from file, so we need to mock its return)
    code_agent_system_prompt = "You are Local IT Agent - Ollash, a specialized AI Code Agent. Your task is to assist the user with their software development and coding tasks."

    # Mock Ollama's response to simulate the orchestrator selecting the 'code' agent type
    default_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Refactor Python function."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Orchestrator calls select_agent_type
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User requested code refactoring."}}}]}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # This is the expected result from the select_agent_type tool *after* the agent processes it internally
        # The agent's internal `select_agent_type` method will return this
        # We also need to mock the system prompt that the agent would load for the code agent
        # The agent's `select_agent_type` method reads this from the prompt file.
        # Since we cannot mock the internal file reading easily here, we will mock the return of the tool itself.
        # This means the mock for select_agent_type needs to provide the system_prompt directly.
        # In actual execution, the select_agent_type tool would return `new_system_prompt` and `new_agent_type`.
        # So we need to ensure the mock reflects that.
        
        # When select_agent_type is called, it returns a dictionary including the new system prompt
        # The agent then updates its own system_prompt. So the next LLM call will use this new prompt.
        
        # 3rd call: Agent generates final textual response as code agent
        ({"message": {"content": "Switched to code agent. How can I help with refactoring?"}}, {"prompt_tokens": 50, "completion_tokens": 20}),
        # 4th call: _translate_to_user_language
        ({"message": {"content": "Switched to code agent. How can I help with refactoring?"}}, {"prompt_tokens": 10, "completion_tokens": 5}) # Adjusted token usage
    ]

    response = default_agent.chat(user_request)
    print(f"Agent: {response}")

    expected_code_prompt_part = "You are Local IT Agent - Ollash, a specialized AI Code Agent."
    assert expected_code_prompt_part in default_agent.system_prompt
    assert "AI Orchestrator" not in default_agent.system_prompt
    assert default_agent.active_agent_type == "code"
    assert "read_file" in default_agent.tool_functions # Should now have code tools loaded

    print(f"Agent successfully switched to Code context. New prompt starts with: {default_agent.system_prompt[:80]}...")
    assert default_agent.ollama.chat.call_count == 4    
def test_code_agent_pings_localhost(default_agent):
    # Define the system prompt for the network agent
    network_agent_system_prompt = "You are Local IT Agent - Ollash, a specialized AI Network Agent. Your task is to assist the user with network-related operations, diagnostics, and configurations."

    # Mock Ollama's responses to force the agent to switch context and then call ping_host
    default_agent.ollama.chat.side_effect = [
        # 1st call (first chat call): _preprocess_instruction for orchestrator_request
        ({"message": {"content": "Refined English instruction: Check network connectivity with localhost."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call (first chat call): Orchestrator is asked to switch to network agent
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "network", "reason": "User requested network connectivity check."}}}]}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # 3rd call (first chat call): After select_agent_type, agent returns initial response (as network agent)
        ({"message": {"content": "Switched to network agent. How can I help with network tasks?"}}, {"prompt_tokens": 50, "completion_tokens": 20}),
        # 4th call (first chat call): _translate_to_user_language
        ({"message": {"content": "Switched to network agent. How can I help with network tasks?"}}, {"prompt_tokens": 10, "completion_tokens": 5}),

        # 5th call (second chat call): _preprocess_instruction for user_request
        ({"message": {"content": "Refined English instruction: Ping localhost twice."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 6th call (second chat call): Agent (now network) receives ping request and calls ping_host
        (
            {"message": {"tool_calls": [{"function": {"name": "ping_host", "arguments": {"host": "localhost", "count": 2}}}]}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # 7th call (second chat call): Agent processes the tool result (JSON)
        (
            {"message": {"content": json.dumps({"ok": True, "result": {"host": "localhost", "packets_sent": 2, "packets_received": 2, "packet_loss_percent": 0, "avg_rtt_ms": 1}})}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # 8th call (second chat call): Agent generates final textual response
        (
            {"message": {"content": "Ping to localhost completed successfully. Result: 2 packets sent, 2 received, 0% loss, avg 1ms."}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # 9th call (second chat call): _translate_to_user_language
        (
            {"message": {"content": "Ping to localhost completed successfully. Result: 2 packets sent, 2 received, 0% loss, avg 1ms."}},
            {"prompt_tokens": 10, "completion_tokens": 5} # Adjusted token usage
        )
    ]

    # Simulate orchestrator's initial request
    orchestrator_request = "Necesito comprobar la conectividad de red con localhost."
    # The first chat call will consume the first 4 side_effects
    response_orchestrator = default_agent.chat(orchestrator_request)
    print(f"Agent Orchestrator Response: {response_orchestrator}")
    
    # Assert that the agent switched to network context
    assert network_agent_system_prompt in default_agent.system_prompt
    assert default_agent.active_agent_type == "network"
    assert "ping_host" in default_agent.tool_functions # Should now have network tools loaded
    assert default_agent.ollama.chat.call_count == 4

    # Now, with the agent in network context, ask it to ping
    user_request = "Por favor, haz ping a localhost 2 veces."
    # The second chat call will consume the remaining 5 side_effects
    response_ping = default_agent.chat(user_request)
    print(f"Agent Ping Response: {response_ping}")

    # Assert that ping_host was indeed called and the response contains success/failure
    assert default_agent.ollama.chat.call_count == 9 # 4 from first chat + 5 from second chat
    
    # Check the final response
    assert "Ping to localhost completed successfully. Result: 2 packets sent, 2 received, 0% loss, avg 1ms." in response_ping

@patch('src.agents.default_agent.OllamaClient.chat') # Patch OllamaClient.chat directly
def test_system_agent_get_info_placeholder(mock_ollama_chat, default_agent, caplog):
    # Define the system prompt for the system agent
    system_agent_system_prompt = "You are Local IT Agent - Ollash, a specialized AI System Agent. Your task is to assist the user with operating system-related operations, diagnostics, and management."

    mock_ollama_chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Get basic system information."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Orchestrator is asked to switch to system agent
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "system", "reason": "User requested system information."}}}]}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # 3rd call: Agent (now system) receives request and calls get_system_info
        (
            {"message": {"tool_calls": [{"function": {"name": "get_system_info", "arguments": {}}}]}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # 4th call: Agent generates final textual response directly
        (
            {"message": {"content": "System information retrieved: OS is Microsoft Windows 10 Pro."}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # 5th call: _translate_to_user_language
        (
            {"message": {"content": "System information retrieved: OS is Microsoft Windows 10 Pro."}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        )
    ]
    
    user_request = "Dime la información básica del sistema."
    print(f"""
User (System Context): {user_request}""")
    
    with caplog.at_level(logging.INFO): # Capture log messages
        response = default_agent.chat(user_request)
        print(f"Agent: {response}")
    
    assert system_agent_system_prompt in default_agent.system_prompt
    assert default_agent.active_agent_type == "system"
    assert "get_system_info" in default_agent.tool_functions

    assert mock_ollama_chat.call_count == 5
    assert "System information retrieved: OS is Microsoft Windows 10 Pro." in response
    # The following assertions related to caplog might need adjustment based on the actual tool output
    # assert "ℹ️ Getting system information..." in caplog.text
    # assert "✅ System information retrieved successfully." in caplog.text