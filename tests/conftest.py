import os
import sys
from pathlib import Path
import pytest
import json
from unittest.mock import patch


# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root)) # Re-enabled as it's necessary for imports

# Centralized test configuration — override via environment variables
TEST_OLLAMA_URL = os.environ.get("OLLAMA_TEST_URL", "http://localhost:11434")
TEST_TIMEOUT = int(os.environ.get("OLLAMA_TEST_TIMEOUT", "300"))


# Fixture for mocking OllamaClient
@pytest.fixture
def mock_ollama_client():
    with patch('src.agents.default_agent.OllamaClient') as MockAgentClient, \
         patch('src.utils.core.memory_manager.OllamaClient') as MockMemoryClient:
        instance = MockAgentClient.return_value
        # Use centralized test URL and timeout from environment variables
        instance.url = TEST_OLLAMA_URL
        instance.base_url = TEST_OLLAMA_URL
        instance.timeout = TEST_TIMEOUT
        # Mock the get_embedding method
        instance.get_embedding.return_value = [0.1] * 384  # Return a dummy embedding vector
        # Make MemoryManager's OllamaClient instances use the same mock
        MockMemoryClient.return_value = instance
        yield instance

# Helper fixture for creating a temporary project root with necessary config and prompt files
@pytest.fixture
def temp_project_root(tmp_path):
    # Create config directory and settings.json
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text(json.dumps({
        "model": "test-model",
        "ollama_url": TEST_OLLAMA_URL,
        "default_system_prompt_path": "prompts/orchestrator/default_orchestrator.json",
        "max_iterations": 5,
        "timeout": 300,
        "ollama_retries": 1,
        "ollama_backoff_factor": 0.1
    }))
    
    # Create an agent.log file
    (tmp_path / "agent.log").touch()

    # Create dummy prompts for all agent types
    prompts_dir = tmp_path / "prompts"
    
    # Orchestrator prompt
    orchestrator_prompt_dir = prompts_dir / "orchestrator"
    orchestrator_prompt_dir.mkdir(parents=True, exist_ok=True)
    (orchestrator_prompt_dir / "default_orchestrator.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, an AI Orchestrator. Your primary goal is to analyze the user's request and determine the most appropriate specialized agent (code, network, system, cybersecurity) to handle it. If the request is ambiguous or falls into multiple domains, ask for clarification. Prioritize directing the user to the correct specialist. Be concise in your responses.",
        "tools": [
            "plan_actions", "select_agent_type", "evaluate_plan_risk", "detect_user_intent",
            "require_human_gate", "summarize_session_state", "explain_decision",
            "validate_environment_expectations", "detect_configuration_drift",
            "evaluate_compliance", "generate_audit_report", "propose_governance_policy",
            "estimate_change_blast_radius", "generate_runbook",
            "analyze_sentiment", "generate_creative_content", "translate_text"
        ]
    }))

    # Code agent prompt
    code_prompt_dir = prompts_dir / "code"
    code_prompt_dir.mkdir(parents=True, exist_ok=True)
    (code_prompt_dir / "default_agent.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, a specialized AI Code Agent. You excel at understanding, writing, and debugging code across various languages. You have access to file system tools, code analysis tools, and Git operations. Your goal is to assist developers with their coding tasks efficiently and accurately.",
        "tools": [
            "plan_actions", "analyze_project", "read_file", "read_files", "write_file", "delete_file", "file_diff", "summarize_file", "summarize_files", "search_code", "run_command", "run_tests", "validate_change", "git_status", "git_commit", "git_push", "list_directory", "select_agent_type", "detect_code_smells",
            "suggest_refactor", "map_code_dependencies", "compare_configs"
        ]
    }))
    
    # Network agent prompt
    network_prompt_dir = prompts_dir / "network"
    network_prompt_dir.mkdir(parents=True, exist_ok=True)
    (network_prompt_dir / "default_network_agent.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, a specialized AI Network Agent. Your expertise lies in diagnosing network issues, mapping network topologies, and analyzing network traffic. You have access to various network diagnostic tools.",
        "tools": [
            "plan_actions", "ping_host", "traceroute_host", "list_active_connections", "check_port_status", "select_agent_type",
            "analyze_network_latency", "detect_unexpected_services", "map_internal_network"
        ]
    }))

    # System agent prompt
    system_prompt_dir = prompts_dir / "system"
    system_prompt_dir.mkdir(parents=True, exist_ok=True)
    (system_prompt_dir / "default_system_agent.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, a specialized AI System Agent. You manage system resources, monitor performance, and troubleshoot operating system-level problems. You have access to system information and process management tools.",
        "tools": [
            "plan_actions", "get_system_info", "list_processes", "install_package", "read_log_file", "select_agent_type",
            "check_disk_health", "monitor_resource_spikes", "analyze_startup_services", "rollback_last_change"
        ]
    }))

    # Cybersecurity agent prompt
    cybersecurity_prompt_dir = prompts_dir / "cybersecurity"
    cybersecurity_prompt_dir.mkdir(parents=True, exist_ok=True)
    (cybersecurity_prompt_dir / "default_cybersecurity_agent.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, a specialized AI Cybersecurity Agent. Your role is to identify and mitigate security vulnerabilities, analyze threats, and ensure compliance. You have access to security scanning and analysis tools.",
        "tools": [
            "plan_actions", "scan_ports", "check_file_hash", "analyze_security_log", "recommend_security_hardening", "select_agent_type",
            "assess_attack_surface", "detect_ioc", "analyze_permissions", "security_posture_score"
        ]
    }))

    # Bonus agent prompt (if applicable for specialized tools)
    bonus_prompt_dir = prompts_dir / "bonus"
    bonus_prompt_dir.mkdir(parents=True, exist_ok=True)
    (bonus_prompt_dir / "default_bonus_agent.json").write_text(json.dumps({
        "prompt": "You are Local IT Agent - Ollash, a specialized AI Bonus Agent. You provide additional utility functions not covered by other agents, such as sentiment analysis, content generation, and advanced planning.",
        "tools": [
            "plan_actions", "estimate_change_blast_radius", "generate_runbook", "analyze_sentiment", 
            "generate_creative_content", "translate_text", "select_agent_type"
        ]
    }))

    yield tmp_path

# Fixture for the DefaultAgent instance, using the common temp_project_root
@pytest.fixture
def default_agent(temp_project_root, mock_ollama_client):
    from src.agents.default_agent import DefaultAgent

    agent = DefaultAgent(project_root=str(temp_project_root))
    agent.ollama = mock_ollama_client
    return agent

# Fixture for live_ollash_agent (for tests that might need a different name)
@pytest.fixture
def live_ollash_agent(default_agent):
    return default_agent
