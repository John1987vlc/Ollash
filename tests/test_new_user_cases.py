import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, call
import logging
from tests.conftest import TEST_OLLAMA_URL, TEST_TIMEOUT



# --- Fixtures ---

@pytest.fixture(scope="module")
def temp_project_root_with_config(tmp_path_factory):
    project_root = tmp_path_factory.mktemp("ollash_test_root_new_cases")

    config_dir = project_root / "config"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text(json.dumps({
        "model": "llama3.2:latest", # Using the recommended smaller model
        "ollama_url": TEST_OLLAMA_URL,
        "default_system_prompt_path": "prompts/orchestrator/default_orchestrator.json",
        "max_iterations": 10,
        "temperature": 0.7,
        "timeout": TEST_TIMEOUT,
        "log_file": "ollash_new_cases.log",
        "loop_detection_threshold": 3 # To test the new feature
    }))

    prompts_dir = project_root / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "orchestrator").mkdir()
    (prompts_dir / "code").mkdir()
    (prompts_dir / "network").mkdir()
    (prompts_dir / "system").mkdir()
    (prompts_dir / "cybersecurity").mkdir()
    (prompts_dir / "bonus").mkdir() # Need bonus for some test cases

    (prompts_dir / "orchestrator" / "default_orchestrator.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, an AI Orchestrator. Your primary goal is to analyze the user's request and determine the most appropriate domain for the task. Based on the domain, you will use the 'select_agent_type' tool to delegate to a specialized agent. Available domains are: 'code', 'network', 'system', 'cybersecurity'. Use the `detect_user_intent` tool to understand the user's goal. If `detect_user_intent` returns an 'exploration' intent with low confidence, or if the request is ambiguous, *you must ask for clarification* from the user or suggest available tools (e.g., 'What exactly do you want to explore?', 'Do you want to check system info, network status, or analyze code?'). Prioritize directing the user to the correct specialist. Be concise in your responses."
    }))
    (prompts_dir / "code" / "default_agent.json").write_text(json.dumps({
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
    (prompts_dir / "bonus" / "default_bonus_agent.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, a specialized AI Bonus Agent. Your task is to assist the user with various bonus operations. The orchestrator has already determined this request is bonus-related. Focus on tasks like sentiment analysis, content generation, translation, or blast radius estimation. Always prioritize user needs. If a task requires user confirmation, prompt for it. Respond with clear, concise information in markdown format. Always use relative paths. Think step-by-step."
    }))

    yield project_root

@pytest.fixture(scope="function")
def ollash_new_cases_agent(default_agent):
    # The default_agent from conftest.py is already set up with temp_project_root
    # Just need to ensure the logger baseFilename is correct for this test module if needed
    # For now, just return the default_agent
    return default_agent

# --- Test Cases (20 in total) ---

def test_case_1_ambiguous_request_clarification(ollash_new_cases_agent):
    # Test: Orchestrator should ask for clarification for an ambiguous request
    user_request = "Something is wrong with the system."
    
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Analyze system issue."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Orchestrator tries to detect intent, gets low confidence 'exploration'
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Orchestrator provides clarification question based on its prompt
        ({"message": {"content": "Your request is a bit ambiguous. What exactly do you want to explore? Do you want to check system info, network status, or analyze code?"}}, {"prompt_tokens": 10, "completion_tokens": 15}),
        # 4th call: _translate_to_user_language
        ({"message": {"content": "Your request is a bit ambiguous. What exactly do you want to explore? Do you want to check system info, network status, or analyze code?"}}, {"prompt_tokens": 10, "completion_tokens": 15})
    ]

    response = ollash_new_cases_agent.chat(user_request)
    assert "Your request is a bit ambiguous." in response
    assert ollash_new_cases_agent.ollama.chat.call_count == 4


def test_case_2_system_info_request(ollash_new_cases_agent):
    # Test: User asks for system info, agent switches to system and calls get_system_info
    user_request = "What's the status of this machine?"
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Get machine status."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Orchestrator detects system intent, suggests switch
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Orchestrator selects system agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "system", "reason": "User asked for system information."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: System agent calls get_system_info
        ({"message": {"tool_calls": [{"function": {"name": "get_system_info", "arguments": {}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: System agent provides summarized output
        ({"message": {"content": "Here is the system information: OS: Linux, CPU: x86_64, RAM: 16GB."}}, {"prompt_tokens": 10, "completion_tokens": 15}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "Here is the system information: OS: Linux, CPU: x86_64, RAM: 16GB."}}, {"prompt_tokens": 10, "completion_tokens": 15})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Here is the system information: OS: Linux, CPU: x86_64, RAM: 16GB." in response
    assert ollash_new_cases_agent.active_agent_type == "system"
    assert "get_system_info" in ollash_new_cases_agent.tool_functions
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_3_code_refactoring_request(ollash_new_cases_agent):
    # Test: User asks for code refactoring, agent switches to code and calls suggest_refactor
    user_request = "Can you suggest some refactoring for 'my_module.py'?"
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Suggest refactoring."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Orchestrator detects code intent, suggests switch
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Orchestrator selects code agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User requested code refactoring."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Code agent calls suggest_refactor
        ({"message": {"tool_calls": [{"function": {"name": "suggest_refactor", "arguments": {"file_path": "my_module.py"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: Code agent provides suggestions
        ({"message": {"content": "Refactoring suggestions for my_module.py: Extract method, Simplify conditional."}}, {"prompt_tokens": 10, "completion_tokens": 15}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "Refactoring suggestions for my_module.py: Extract method, Simplify conditional."}}, {"prompt_tokens": 10, "completion_tokens": 15})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Refactoring suggestions for my_module.py: Extract method, Simplify conditional." in response
    assert ollash_new_cases_agent.active_agent_type == "code"
    assert "suggest_refactor" in ollash_new_cases_agent.tool_functions
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_4_network_connectivity_check(ollash_new_cases_agent):
    # Test: User asks to ping a host, agent switches to network and calls ping_host
    user_request = "Ping google.com for me."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Ping google.com."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Orchestrator detects network intent, suggests switch
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Orchestrator selects network agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "network", "reason": "User requested to ping a host."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Network agent calls ping_host
        ({"message": {"tool_calls": [{"function": {"name": "ping_host", "arguments": {"host": "google.com"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: Network agent provides ping results
        ({"message": {"content": "Ping to google.com successful. Avg RTT: 20ms, 0% packet loss."}}, {"prompt_tokens": 10, "completion_tokens": 15}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "Ping to google.com successful. Avg RTT: 20ms, 0% packet loss."}}, {"prompt_tokens": 10, "completion_tokens": 15})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Ping to google.com successful. Avg RTT: 20ms, 0% packet loss." in response
    assert ollash_new_cases_agent.active_agent_type == "network"
    assert "ping_host" in ollash_new_cases_agent.tool_functions
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_5_cybersecurity_scan_ports(ollash_new_cases_agent):
    # Test: User asks to scan ports, agent switches to cybersecurity and calls scan_ports
    user_request = "Scan ports on my_server for common vulnerabilities."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Scan ports for vulnerabilities."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Orchestrator detects cybersecurity intent, suggests switch
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Orchestrator selects cybersecurity agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "cybersecurity", "reason": "User requested port scan for vulnerabilities."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Cybersecurity agent calls scan_ports
        ({"message": {"tool_calls": [{"function": {"name": "scan_ports", "arguments": {"host": "my_server"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: Cybersecurity agent provides scan results
        ({"message": {"content": "Port scan on my_server completed. Found open ports: 22, 80, 443."}}, {"prompt_tokens": 10, "completion_tokens": 15}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "Port scan on my_server completed. Found open ports: 22, 80, 443."}}, {"prompt_tokens": 10, "completion_tokens": 15})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Port scan on my_server completed. Found open ports: 22, 80, 443." in response
    assert ollash_new_cases_agent.active_agent_type == "cybersecurity"
    assert "scan_ports" in ollash_new_cases_agent.tool_functions
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_6_mixed_domain_request(ollash_new_cases_agent):
    # Test: User asks for a mixed domain request, orchestrator should ask for clarification
    user_request = "Check the server's network and also its code."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Analyze server network and code."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Orchestrator detects ambiguous intent (or low confidence exploration)
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Orchestrator asks for clarification
        ({"message": {"content": "Your request involves multiple domains. Would you like to focus on the network check or the code analysis first?"}}, {"prompt_tokens": 10, "completion_tokens": 15}),
        # 4th call: _translate_to_user_language
        ({"message": {"content": "Your request involves multiple domains. Would you like to focus on the network check or the code analysis first?"}}, {"prompt_tokens": 10, "completion_tokens": 15})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Your request involves multiple domains." in response
    assert ollash_new_cases_agent.active_agent_type == "orchestrator"
    assert ollash_new_cases_agent.ollama.chat.call_count == 4


def test_case_7_loop_detection_clarification(ollash_new_cases_agent):
    # Test: Orchestrator gets stuck in a loop of calling detect_user_intent due to ambiguous input
    # Agent should trigger human gate after loop_detection_threshold
    user_request = "Just help me, please."
    
    # Mock detect_user_intent to always return ambiguous/exploration for 3 consecutive calls
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: User requests help."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: LLM will call detect_user_intent, which will return ok=True, intent='exploration'
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: LLM will call detect_user_intent again
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: LLM will call detect_user_intent a third time, triggering loop detection, which returns the dict directly
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
    ]

    response = ollash_new_cases_agent.chat(user_request)

    # Assert that the chat method returns the dictionary directly from require_human_gate
    assert isinstance(response, dict)
    assert response.get("ok") is False
    assert response.get("result", {}).get("status") == "human_gate_requested"
    assert response.get("result", {}).get("action_description").startswith("Detected a loop!")
    assert "Loop detected" in response.get("result", {}).get("reason")
    # We assert that ollama.chat was called 4 times (1 preprocess + 3 detect_user_intent)
    assert ollash_new_cases_agent.ollama.chat.call_count == 4


def test_case_8_invalid_agent_type_selection(ollash_new_cases_agent):
    # Test: Orchestrator attempts to select an invalid agent type
    user_request = "Switch to the 'pizza' agent."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Switch to pizza agent."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Orchestrator detects intent, tries to select invalid agent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Orchestrator tries to select invalid agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "pizza", "reason": "User requested to switch to an invalid agent type."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Orchestrator should report the error or try to re-evaluate
        ({"message": {"content": "I cannot switch to 'pizza' agent. Please select from 'code', 'network', 'system', 'cybersecurity'."}}, {"prompt_tokens": 10, "completion_tokens": 20}),
        # 5th call: _translate_to_user_language
        ({"message": {"content": "I cannot switch to 'pizza' agent. Please select from 'code', 'network', 'system', 'cybersecurity'."}}, {"prompt_tokens": 10, "completion_tokens": 20})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "I cannot switch to 'pizza' agent." in response
    assert ollash_new_cases_agent.active_agent_type == "orchestrator" # Should remain orchestrator
    assert ollash_new_cases_agent.ollama.chat.call_count == 5


def test_case_9_file_read_non_existent(ollash_new_cases_agent):
    # Test: Code agent attempts to read a non-existent file
    user_request = "Read the file 'non_existent.txt'."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Read non_existent.txt."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Select code agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User requested to read a file."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Code agent calls read_file
        ({"message": {"tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "non_existent.txt"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: Code agent provides error output
        ({"message": {"content": "Error: File 'non_existent.txt' not found."}}, {"prompt_tokens": 10, "completion_tokens": 10}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "Error: File 'non_existent.txt' not found."}}, {"prompt_tokens": 10, "completion_tokens": 10})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "File 'non_existent.txt' not found." in response
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_10_git_status_check(ollash_new_cases_agent):
    # Test: User asks for git status, agent switches to code and calls git_status
    user_request = "What's the current git status?"
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Get git status."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Select code agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User requested git status."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Code agent calls git_status
        ({"message": {"tool_calls": [{"function": {"name": "git_status", "arguments": {}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: Code agent provides git status
        ({"message": {"content": "Git status: Clean working tree."}}, {"prompt_tokens": 10, "completion_tokens": 10}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "Git status: Clean working tree."}}, {"prompt_tokens": 10, "completion_tokens": 10})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Git status: Clean working tree." in response
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_11_install_package(ollash_new_cases_agent):
    # Test: User asks to install a package, agent switches to system and calls install_package
    user_request = "Please install 'htop' on the system."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Install htop."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Select system agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "system", "reason": "User requested package installation."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: System agent calls install_package
        ({"message": {"tool_calls": [{"function": {"name": "install_package", "arguments": {"package_name": "htop", "package_manager": "apt"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: System agent provides installation result
        ({"message": {"content": "Package 'htop' installed successfully using apt."}}, {"prompt_tokens": 10, "completion_tokens": 10}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "Package 'htop' installed successfully using apt."}}, {"prompt_tokens": 10, "completion_tokens": 10})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Package 'htop' installed successfully using apt." in response
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_12_analyze_network_latency(ollash_new_cases_agent):
    # Test: User asks to analyze network latency, agent switches to network and calls analyze_network_latency
    user_request = "Analyze network latency to example.com."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Analyze network latency."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Select network agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "network", "reason": "User requested network latency analysis."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Network agent calls analyze_network_latency
        ({"message": {"tool_calls": [{"function": {"name": "analyze_network_latency", "arguments": {"target_host": "example.com"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: Network agent provides latency results
        ({"message": {"content": "Network latency to example.com: Avg 50ms, 0% packet loss."}}, {"prompt_tokens": 10, "completion_tokens": 15}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "Network latency to example.com: Avg 50ms, 0% packet loss."}}, {"prompt_tokens": 10, "completion_tokens": 15})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Network latency to example.com: Avg 50ms, 0% packet loss." in response
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_13_check_file_hash(ollash_new_cases_agent):
    # Test: User asks to check file hash, agent switches to cybersecurity and calls check_file_hash
    user_request = "Check the SHA256 hash of 'document.pdf' against known_hash."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Check file hash."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Select cybersecurity agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "cybersecurity", "reason": "User requested file hash check."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Cybersecurity agent calls check_file_hash
        ({"message": {"tool_calls": [{"function": {"name": "check_file_hash", "arguments": {"path": "document.pdf", "expected_hash": "known_hash", "hash_type": "sha256"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: Cybersecurity agent provides hash check result
        ({"message": {"content": "SHA256 hash for document.pdf is correct."}}, {"prompt_tokens": 10, "completion_tokens": 10}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "SHA256 hash for document.pdf is correct."}}, {"prompt_tokens": 10, "completion_tokens": 10})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "SHA256 hash for document.pdf is correct." in response
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_14_propose_governance_policy(ollash_new_cases_agent):
    # Test: User asks for a governance policy, orchestrator stays and calls propose_governance_policy
    user_request = "Propose a data handling governance policy for customer data."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Propose data policy."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Orchestrator calls propose_governance_policy
        ({"message": {"tool_calls": [{"function": {"name": "propose_governance_policy", "arguments": {"policy_type": "data_handling", "scope": ["customer data"]}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Orchestrator provides policy proposal result
        ({"message": {"content": "Draft data handling policy proposed."}}, {"prompt_tokens": 10, "completion_tokens": 10}),
        # 5th call: _translate_to_user_language
        ({"message": {"content": "Draft data handling policy proposed."}}, {"prompt_tokens": 10, "completion_tokens": 10})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Draft data handling policy proposed." in response
    assert ollash_new_cases_agent.active_agent_type == "orchestrator"
    assert ollash_new_cases_agent.ollama.chat.call_count == 5


def test_case_15_detect_code_smells(ollash_new_cases_agent):
    # Test: User asks to detect code smells, agent switches to code and calls detect_code_smells
    user_request = "Detect code smells in 'src/main.py'."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Detect code smells."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Select code agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "code", "reason": "User requested code smell detection."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Code agent calls detect_code_smells
        ({"message": {"tool_calls": [{"function": {"name": "detect_code_smells", "arguments": {"path": "src/main.py"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: Code agent provides code smells result
        ({"message": {"content": "Code smells detected: Long function in main.py."}}, {"prompt_tokens": 10, "completion_tokens": 10}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "Code smells detected: Long function in main.py."}}, {"prompt_tokens": 10, "completion_tokens": 10})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Code smells detected: Long function in main.py." in response
    assert ollash_new_cases_agent.active_agent_type == "code"
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_16_monitor_resource_spikes(ollash_new_cases_agent):
    # Test: User asks to monitor CPU spikes, agent switches to system and calls monitor_resource_spikes
    user_request = "Monitor CPU spikes for the last 10 minutes."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Monitor CPU spikes."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Select system agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "system", "reason": "User requested monitoring of CPU spikes."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: System agent calls monitor_resource_spikes
        ({"message": {"tool_calls": [{"function": {"name": "monitor_resource_spikes", "arguments": {"resource_type": "cpu", "duration_minutes": 10}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: System agent provides resource spike result
        ({"message": {"content": "CPU spikes monitored. Max spike: 90% at 2026-02-07T21:00:00."}}, {"prompt_tokens": 10, "completion_tokens": 15}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "CPU spikes monitored. Max spike: 90% at 2026-02-07T21:00:00."}}, {"prompt_tokens": 10, "completion_tokens": 15})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "CPU spikes monitored. Max spike: 90% at 2026-02-07T21:00:00." in response
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_17_analyze_network_latency_multi_step(ollash_new_cases_agent):
    # Test: User asks for network latency, then asks for traceroute in follow-up
    user_request_1 = "Check network latency to internal.mycompany.com."
    user_request_2 = "Now, traceroute to the same host."

    # First interaction: Latency check
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call (chat 1): _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Check network latency."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call (chat 1): Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request_1}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call (chat 1): Select network agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "network", "reason": "User requested network latency check."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call (chat 1): Network agent calls analyze_network_latency
        ({"message": {"tool_calls": [{"function": {"name": "analyze_network_latency", "arguments": {"target_host": "internal.mycompany.com"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call (chat 1): Network agent provides latency results
        ({"message": {"content": "Latency to internal.mycompany.com: Avg 5ms, 0% packet loss."}}, {"prompt_tokens": 10, "completion_tokens": 15}),
        # 6th call (chat 1): _translate_to_user_language
        ({"message": {"content": "Latency to internal.mycompany.com: Avg 5ms, 0% packet loss."}}, {"prompt_tokens": 10, "completion_tokens": 15}),

        # 7th call (chat 2): _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Traceroute to same host."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 8th call (chat 2): Detect user intent (should detect network intent again)
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request_2}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 9th call (chat 2): Agent should remain in network context and call traceroute
        ({"message": {"tool_calls": [{"function": {"name": "traceroute_host", "arguments": {"host": "internal.mycompany.com"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 10th call (chat 2): Agent provides traceroute results
        ({"message": {"content": "Traceroute to internal.mycompany.com completed. Hops: 3."}}, {"prompt_tokens": 10, "completion_tokens": 10}),
        # 11th call (chat 2): _translate_to_user_language
        ({"message": {"content": "Traceroute to internal.mycompany.com completed. Hops: 3."}}, {"prompt_tokens": 10, "completion_tokens": 10})
    ]
    
    response_1 = ollash_new_cases_agent.chat(user_request_1)
    assert "Latency to internal.mycompany.com: Avg 5ms, 0% packet loss." in response_1
    assert ollash_new_cases_agent.active_agent_type == "network"
    assert ollash_new_cases_agent.ollama.chat.call_count == 6 # After first chat call

    response_2 = ollash_new_cases_agent.chat(user_request_2)
    assert "Traceroute to internal.mycompany.com completed. Hops: 3." in response_2
    assert ollash_new_cases_agent.active_agent_type == "network" # Should still be network agent
    assert ollash_new_cases_agent.ollama.chat.call_count == 11 # After second chat call


def test_case_18_analyze_security_log(ollash_new_cases_agent):
    # Test: User asks to analyze security log with specific keywords
    user_request = "Analyze 'auth.log' for 'FAILED LOGIN' attempts."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Analyze security log."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Select cybersecurity agent
        ({"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "cybersecurity", "reason": "User requested security log analysis."}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Cybersecurity agent calls analyze_security_log
        ({"message": {"tool_calls": [{"function": {"name": "analyze_security_log", "arguments": {"log_path": "auth.log", "keywords": ["FAILED LOGIN"]}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 5th call: Cybersecurity agent provides log analysis result
        ({"message": {"content": "Security log analyzed. Found 5 FAILED LOGIN entries."}}, {"prompt_tokens": 10, "completion_tokens": 10}),
        # 6th call: _translate_to_user_language
        ({"message": {"content": "Security log analyzed. Found 5 FAILED LOGIN entries."}}, {"prompt_tokens": 10, "completion_tokens": 10})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Security log analyzed. Found 5 FAILED LOGIN entries." in response
    assert ollash_new_cases_agent.active_agent_type == "cybersecurity"
    assert ollash_new_cases_agent.ollama.chat.call_count == 6


def test_case_19_generate_runbook(ollash_new_cases_agent):
    # Test: User asks to generate a runbook, orchestrator stays and calls generate_runbook
    user_request = "Generate a runbook for 'failed deployments'."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Generate runbook."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Orchestrator calls generate_runbook
        ({"message": {"tool_calls": [{"function": {"name": "generate_runbook", "arguments": {"incident_or_task_description": "failed deployments"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Orchestrator provides runbook generation result
        ({"message": {"content": "Runbook for failed deployments generated. Steps: 1. Check logs, 2. Rollback, 3. Notify team."}}, {"prompt_tokens": 10, "completion_tokens": 15}),
        # 5th call: _translate_to_user_language
        ({"message": {"content": "Runbook for failed deployments generated. Steps: 1. Check logs, 2. Rollback, 3. Notify team."}}, {"prompt_tokens": 10, "completion_tokens": 15})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Runbook for failed deployments generated." in response
    assert ollash_new_cases_agent.active_agent_type == "orchestrator"
    assert ollash_new_cases_agent.ollama.chat.call_count == 5


def test_case_20_estimate_change_blast_radius(ollash_new_cases_agent):
    # Test: User asks to estimate blast radius, orchestrator stays and calls estimate_change_blast_radius
    user_request = "Estimate blast radius for 'changing authentication mechanism'."
    ollash_new_cases_agent.ollama.chat.side_effect = [
        # 1st call: _preprocess_instruction
        ({"message": {"content": "Refined English instruction: Estimate blast radius."}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 2nd call: Detect user intent
        ({"message": {"tool_calls": [{"function": {"name": "detect_user_intent", "arguments": {"user_request": user_request}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 3rd call: Orchestrator calls estimate_change_blast_radius
        ({"message": {"tool_calls": [{"function": {"name": "estimate_change_blast_radius", "arguments": {"change_description": "changing authentication mechanism"}}}]}}, {"prompt_tokens": 10, "completion_tokens": 5}),
        # 4th call: Orchestrator provides blast radius estimation result
        ({"message": {"content": "Blast radius for changing authentication mechanism estimated as high."}}, {"prompt_tokens": 10, "completion_tokens": 15}),
        # 5th call: _translate_to_user_language
        ({"message": {"content": "Blast radius for changing authentication mechanism estimated as high."}}, {"prompt_tokens": 10, "completion_tokens": 15})
    ]
    response = ollash_new_cases_agent.chat(user_request)
    assert "Blast radius for changing authentication mechanism estimated as high." in response
    assert ollash_new_cases_agent.active_agent_type == "orchestrator"
    assert ollash_new_cases_agent.ollama.chat.call_count == 5

