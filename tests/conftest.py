import os
import sys
import random
from pathlib import Path
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

# Ensure the project root is on the Python path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.core.ollama_client import OllamaClient # Import the real class
import chromadb # Import chromadb to patch it
from src.services.llm_manager import LLMClientManager # NEW


# Centralized test configuration — override via environment variables
TEST_OLLAMA_URL = os.environ.get("OLLAMA_TEST_URL", "http://localhost:11434")
TEST_TIMEOUT = int(os.environ.get("OLLAMA_TEST_TIMEOUT", "300"))


def _make_varying_embedding():
    """Return a different random-ish embedding each call to avoid loop detection false positives."""
    counter = [0]
    rng = random.Random(42)  # deterministic seed for reproducibility

    def _gen(*args, **kwargs):
        counter[0] += 1
        # Each call produces a distinct vector (seeded by call index)
        return [rng.gauss(0, 1) for _ in range(384)]

    return _gen


@pytest.fixture
def mock_ollama_client_factory(mocker):
    """
    Fixture that provides a factory function to create mocked OllamaClient instances.
    Each mock instance will have default achat and embedd side effects.
    Accepts all arguments from OllamaClient.__init__
    """
    def _factory(url=None, model=None, timeout=None, logger=None, config=None, model_health_monitor=None, llm_recorder=None): # Added llm_recorder
        # Use MagicMock without spec to allow any attributes
        mock_client = MagicMock()
        mock_client.achat = AsyncMock() # No default side_effect here
        mock_client.embedd = AsyncMock(return_value={"embedding": [0.1]*384})
        mock_client.model = model if model else "mocked-model"
        mock_client.base_url = url if url else TEST_OLLAMA_URL
        mock_client.url = url if url else TEST_OLLAMA_URL  # Some code uses .url instead of .base_url
        mock_client.timeout = timeout if timeout else TEST_TIMEOUT
        return mock_client
    return _factory


@pytest.fixture(autouse=True) # Apply this globally to all tests
def patch_ollama_client_class(mocker, mock_ollama_client_factory):
    """
    Patches the OllamaClient class so that any instantiation creates a mock.
    """
    # When OllamaClient() is called, it will actually call mock_ollama_client_factory
    # The arguments passed to OllamaClient() will be passed to _factory.
    mocker.patch('src.utils.core.ollama_client.OllamaClient', side_effect=mock_ollama_client_factory)


@pytest.fixture
def mock_chromadb_client_factory(mocker):
    """
    Fixture that provides a factory function to create mocked chromadb.Client instances.
    """
    def _factory(*args, **kwargs):
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.add.return_value = None
        mock_collection.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_collection.delete.return_value = None

        mock_client = MagicMock() # Removed spec=chromadb.Client
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client.delete_collection.return_value = None
        mock_client.reset.return_value = None # Add reset for ephemeral client cleanup
        return mock_client
    return _factory


@pytest.fixture(autouse=True) # Apply this globally to all tests
def patch_chromadb_client_class(mocker, mock_chromadb_client_factory):
    """
    Patches the chromadb.Client class so that any instantiation creates a mock.
    """
    mocker.patch('chromadb.Client', side_effect=mock_chromadb_client_factory)


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
        "ollama_backoff_factor": 0.1,
        "auto_confirm_tools": False, # NEWLY ADDED
        "models": { # Ensure these exist for CoreAgent initialization
            "default": "test-model",
            "prototyper": "test-prototyper",
            "coder": "test-coder",
            "planner": "test-planner",
            "generalist": "test-generalist",
            "suggester": "test-suggester",
            "improvement_planner": "test-improvement-planner",
            "test_generator": "test-test-generator",
            "senior_reviewer": "test-senior-reviewer",
            "orchestration": "test-orchestration", # Used in _preprocess_instruction etc.
            "self_correction": "test-self-correction" # Used in _handle_tool_error
        }
    }))
    
    # Create an agent.log file
    (tmp_path / "logs").mkdir() # Ensure logs directory exists
    (tmp_path / "logs" / "defaultagent.log").touch() # Use specific log file name

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
def default_agent(temp_project_root, mock_ollama_client_factory, mocker):
    """Fixture for DefaultAgent with mocked LLMClientManager and OllamaClient instances."""
    from src.agents.default_agent import DefaultAgent

    # Create a mock LLMClientManager
    mock_llm_manager = MagicMock(spec=LLMClientManager)
    
    # Populate its llm_clients with mocked OllamaClient instances
    # Each mocked OllamaClient needs an AsyncMock for achat
    mock_llm_manager.llm_clients = {
        "default": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-default", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        "orchestration": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-orchestration", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        "coder": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-coder", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        "senior_reviewer": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-senior-reviewer", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        "prototyper": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-prototyper", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        "planner": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-planner", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        "generalist": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-generalist", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        "suggester": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-suggester", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        "improvement_planner": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-improvement-planner", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        "test_generator": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-test-generator", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        "analyst": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-analyst", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        "writer": MagicMock(achat=AsyncMock(), embedd=AsyncMock(return_value={"embedding": [0.1]*384}), model="mocked-writer", base_url=TEST_OLLAMA_URL, url=TEST_OLLAMA_URL, timeout=TEST_TIMEOUT),
        # Add other roles as needed by tests
    }

    # Ensure get_client returns the correct mock OllamaClient
    mock_llm_manager.get_client.side_effect = lambda role: mock_llm_manager.llm_clients.get(role)

    # Patch LLMClientManager when it's instantiated inside DefaultAgent (via CoreAgent)
    mocker.patch('src.agents.core_agent.LLMClientManager', return_value=mock_llm_manager)

    agent = DefaultAgent(project_root=str(temp_project_root), llm_manager=mock_llm_manager)
    yield agent

# Fixture for live_ollash_agent (for tests that might need a different name)
@pytest.fixture
def live_ollash_agent(default_agent):
    return default_agent