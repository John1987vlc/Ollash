import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, call # Added call for side_effect
import time # For potential delays with Ollama
import logging # For checking logs

from src.agents.code_agent import CodeAgent
from src.utils.command_executor import SandboxLevel # Assuming this is used for CommandExecutor init

# --- Fixtures ---

@pytest.fixture(scope="module")
def temp_project_root_with_config(tmp_path_factory):
    # Create a persistent temp directory for the module tests
    project_root = tmp_path_factory.mktemp("ollash_test_root")

    # Create config directory and settings.json
    config_dir = project_root / "config"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text(json.dumps({
        "model": "ministral-3:8b", # Use actual Ollama model
        "ollama_url": "http://localhost:11434",
        "default_system_prompt_path": "prompts/orchestrator/default_orchestrator.json",
        "max_iterations": 10, # Increased iterations for live Ollama tests
        "temperature": 0.7,  # Increased temperature for more flexible tool calling
        "timeout": 300,
        "log_file": "ollash_test.log"
    }))

    # Create prompts directory and prompt files
    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "orchestrator").mkdir()
    (prompts_dir / "code").mkdir()
    (prompts_dir / "network").mkdir()
    (prompts_dir / "system").mkdir()
    (prompts_dir / "cybersecurity").mkdir()

    (prompts_dir / "orchestrator" / "default_orchestrator.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, an AI Orchestrator. Your primary goal is to analyze the user's request and determine the most appropriate domain for the task. Based on the domain, you will use the 'select_agent_type' tool to delegate to a specialized agent. Available domains are: 'code', 'network', 'system', 'cybersecurity'. If the request is ambiguous or requires information from multiple domains, ask for clarification. Prioritize directing the user to the correct specialist. Be concise in your responses."
    }))
    (prompts_dir / "code" / "default_code_agent.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, a specialized AI Code Agent. Your task is to assist the user with their software development and coding tasks. The orchestrator has already determined this request is code-related. Focus on analyzing, generating, refactoring, and debugging code, managing files, and interacting with version control. Always prioritize user safety and project conventions. If a task requires user confirmation, prompt for it. Respond with clear, concise information in markdown format. Always use relative paths. Importantly, you have access to various general IT tools (network, system, file system, git, security). If any of these tools can directly fulfill the user's request, use it without hesitation. Think step-by-step."
    }))
    (prompts_dir / "network" / "default_network_agent.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, a specialized AI Network Agent. Your task is to assist the user with network-related operations, diagnostics, and configurations. The orchestrator has already determined this request is network-related. Focus on tasks like checking network status, diagnosing connectivity issues, managing firewall rules, or listing active connections. Always prioritize network security and operational best practices. If a task requires user confirmation, prompt for it. Respond with clear, concise information in markdown format. Always use relative paths. Think step-by-step."
    }))
    (prompts_dir / "system" / "default_system_agent.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, a specialized AI System Agent. Your task is to assist the user with operating system-related operations, diagnostics, and management. The orchestrator has already determined this request is system-related. Focus on tasks like checking system resources, managing processes, installing software, or reviewing system logs. Always prioritize system stability and security. If a task requires user confirmation, prompt for it. Respond with clear, concise information in markdown format. Always use relative paths. **IMPORTANT:** If you successfully execute a tool, report its output clearly and concisely to the user, summarizing the key findings or next steps based on the output, and then finish your response. Avoid unnecessary chatter and get straight to the point after a tool execution. Think step-by-step."
    }))
    (prompts_dir / "cybersecurity" / "default_cybersecurity_agent.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, a specialized AI Cybersecurity Agent. Your task is to assist the user with cybersecurity-related operations, analysis, and recommendations. The orchestrator has already determined this request is cybersecurity-related. Focus on tasks like scanning for vulnerabilities, analyzing security logs, recommending security best practices, or checking file integrity. Always prioritize data protection and threat mitigation. If a task requires user confirmation, prompt for it. Respond with clear, concise information in markdown format. Always use relative paths. Think step-by-step."
    }))

    yield project_root

@pytest.fixture(scope="module")
def live_ollash_agent(temp_project_root_with_config):
    # This agent will interact with a live Ollama instance
    # Set the project_root to the sandbox directory
    agent = CodeAgent(project_root=str(temp_project_root_with_config))
    # Override log_file path for this specific test run, as the agent.log path is relative to project_root
    agent.logger.logger.handlers[0].baseFilename = str(temp_project_root_with_config / "ollash_test.log")
    return agent

# --- Tests ---

def test_orchestrator_initial_prompt(live_ollash_agent):
    # Assert that the agent starts with the orchestrator prompt
    expected_orchestrator_prompt_part = "You are Local IT Agent - Ollash, an AI Orchestrator."
    assert expected_orchestrator_prompt_part in live_ollash_agent.system_prompt

@patch('src.agents.code_agent.OllamaClient.chat') # Patch OllamaClient.chat directly
def test_orchestrator_to_code_switch(mock_ollama_chat, live_ollash_agent):
    initial_prompt = live_ollash_agent.system_prompt
    assert "AI Orchestrator" in initial_prompt

    user_request = "Necesito ayuda para refactorizar una función Python en mi proyecto."
    print(f"""
User: {user_request}""") 
    
    # Mock Ollama's response to simulate the orchestrator selecting the 'code' agent type
    mock_ollama_chat.side_effect = [
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code"}}}]}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # After select_agent_type, the agent will load the code prompt and then the LLM will provide a final answer
        ({"message": {"content": "Switched to code agent. How can I help with refactoring?"}}, {"prompt_tokens": 50, "completion_tokens": 20})
    ]

    response = live_ollash_agent.chat(user_request)
    print(f"Agent: {response}")

    expected_code_prompt_part = "You are Local IT Agent - Ollash, a specialized AI Code Agent."
    assert expected_code_prompt_part in live_ollash_agent.system_prompt
    assert "AI Orchestrator" not in live_ollash_agent.system_prompt
    assert live_ollash_agent.active_agent_type == "code"
    assert "read_file" in live_ollash_agent.tool_functions # Should now have code tools loaded

    print(f"Agent successfully switched to Code context. New prompt starts with: {live_ollash_agent.system_prompt[:80]}...")
    
@patch('src.agents.code_agent.OllamaClient.chat') # Patch OllamaClient.chat directly
def test_code_agent_pings_localhost(mock_ollama_chat, live_ollash_agent):
    # Mock Ollama's responses to force the agent to switch context and then call ping_host
    mock_ollama_chat.side_effect = [
        # First chat call (orchestrator_request): Orchestrator is asked to switch to network agent
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "network"}}}]}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # Second chat call (user_request to ping): Agent (now network) receives ping request and calls ping_host
        (
            {"message": {"tool_calls": [{"function": {"name": "ping_host", "arguments": {"host": "localhost", "count": 2}}}]}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # Third chat call (after ping_host executes): Agent processes the tool result (JSON)
        (
            {"message": {"content": json.dumps({"ok": True, "result": {"host": "localhost", "packets_sent": 2, "packets_received": 2, "packet_loss_percent": 0, "avg_rtt_ms": 1}})}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # Fourth chat call (after tool result is processed): Agent generates final textual response
        (
            {"message": {"content": "Ping to localhost completed successfully. Result: 2 packets sent, 2 received, 0% loss, avg 1ms."}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        )
    ]

    # Simulate orchestrator's initial request
    orchestrator_request = "Necesito comprobar la conectividad de red con localhost."
    # The first chat call will consume the first side_effect (select_agent_type)
    live_ollash_agent.chat(orchestrator_request) 
    
    # Assert that the agent switched to network context
    assert "AI Network Agent" in live_ollash_agent.system_prompt
    assert live_ollash_agent.active_agent_type == "network"
    assert "ping_host" in live_ollash_agent.tool_functions # Should now have network tools loaded

    # Now, with the agent in network context, ask it to ping
    user_request = "Por favor, haz ping a localhost 2 veces."
    # The second chat call will consume the second side_effect (ping_host)
    # The third chat call will consume the third side_effect (tool result processing)
    # The fourth chat call will consume the fourth side_effect (final response)
    response = live_ollash_agent.chat(user_request)
    print(f"Agent: {response}")

    # Assert that ping_host was indeed called and the response contains success/failure
    assert mock_ollama_chat.call_count == 4
    
    # Check the final response
    assert "Ping to localhost completed successfully. Result: 2 packets sent, 2 received, 0% loss, avg 1ms." in response


@patch('src.agents.code_agent.OllamaClient.chat') # Patch OllamaClient.chat directly
def test_system_agent_get_info_placeholder(mock_ollama_chat, live_ollash_agent, caplog):
    mock_ollama_chat.side_effect = [
        # First chat call (orchestrator_request): Orchestrator is asked to switch to system agent
        (
            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "system"}}}]}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # Second chat call (user_request for system info): Agent (now system) receives request and calls get_system_info
        (
            {"message": {"tool_calls": [{"function": {"name": "get_system_info", "arguments": {}}}]}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        ),
        # Third chat call (after get_system_info executes): Agent generates final textual response directly
        (
            {"message": {"content": "System information retrieved: OS is Microsoft Windows 10 Pro."}},
            {"prompt_tokens": 100, "completion_tokens": 50}
        )
    ]
    
    user_request = "Dime la información básica del sistema."
    print(f"""
User (System Context): {user_request}""") 
    
    with caplog.at_level(logging.INFO): # Capture log messages
        response = live_ollash_agent.chat(user_request)
        print(f"Agent: {response}")
    
    assert "AI System Agent" in live_ollash_agent.system_prompt
    assert live_ollash_agent.active_agent_type == "system"
    assert "get_system_info" in live_ollash_agent.tool_functions

    assert mock_ollama_chat.call_count == 3
    assert "System information retrieved: OS is Microsoft Windows 10 Pro." in response
    assert "ℹ️ Getting system information..." in caplog.text
    assert "✅ System information retrieved successfully." in caplog.text