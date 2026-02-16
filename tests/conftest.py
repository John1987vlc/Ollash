import json
from pathlib import Path

import pytest

from backend.agents.default_agent import DefaultAgent
from backend.core.config import reload_config  # Still needed for refreshing our own config
from backend.core.kernel import AgentKernel

# Removed importlib as it's no longer needed for module reloading hacks


# Constants for tests
TEST_OLLAMA_URL = "http://localhost:11434"
TEST_TIMEOUT = 300


@pytest.fixture(autouse=True)
def mock_chromadb_client(mocker):
    """
    Mocks the chromadb.Client and its internal state to prevent actual ChromaDB
    instantiation and its related global state issues during tests.
    """
    # Mock the Client and PersistentClient to prevent them from doing anything real
    mocker.patch("chromadb.Client")
    mocker.patch("chromadb.PersistentClient")

    # Crucially, ensure ChromaDB's internal singleton tracking is always reset.
    # This prevents the "An instance of Chroma already exists" error.
    try:
        import chromadb.config

        mocker.patch.object(chromadb.config.Settings, "instances", {})
    except (ImportError, AttributeError):
        pass  # If chromadb isn't installed or structure changes, don't fail all tests


@pytest.fixture(scope="function")
def temp_project_root(tmp_path: Path) -> Path:
    """Creates a temporary, isolated project directory for a test."""
    project_root = tmp_path / "ollash_test_project"
    project_root.mkdir()
    (project_root / ".ollash" / "logs").mkdir(parents=True)

    # Create dummy prompts so the agent can initialize
    prompts_dir = project_root / "prompts"
    for agent_type in ["orchestrator", "code", "network", "system", "cybersecurity"]:
        agent_prompts_dir = prompts_dir / agent_type
        agent_prompts_dir.mkdir(parents=True)
        fname = f"default_{agent_type}.json"
        if agent_type == "code":
            fname = "default_agent.json"

        with open(agent_prompts_dir / fname, "w") as f:
            json.dump({"system_prompt": f"Test prompt for {agent_type}."}, f)

    return project_root


@pytest.fixture(scope="function")
def default_agent(monkeypatch, temp_project_root: Path) -> DefaultAgent:
    """
    Provides a standard, initialized DefaultAgent for integration tests.
    This fixture creates a fresh instance for each test.
    """
    # Monkeypatch settings BEFORE reloading config and creating the agent
    monkeypatch.setenv("PROMPTS_DIR", str(temp_project_root / "prompts"))
    monkeypatch.setenv("USE_BENCHMARK_SELECTOR", "False")
    monkeypatch.setenv("AGENT_FEATURES_JSON", json.dumps({"enable_auto_learning": False}))
    monkeypatch.setenv("OLLAMA_URL", TEST_OLLAMA_URL)

    # Set LLM_MODELS_JSON explicitly for tests in conftest
    models_config = {
        "ollama_url": TEST_OLLAMA_URL,
        "default_model": "mistral:latest",
        "default_timeout": TEST_TIMEOUT,  # Include default_timeout
        "agent_roles": {
            "prototyper": "test-proto",
            "coder": "test-coder",
            "planner": "test-planner",
            "generalist": "test-generalist",
            "suggester": "test-suggester",
            "improvement_planner": "test-improvement-planner",
            "senior_reviewer": "test-senior-reviewer",
            "test_generator": "test-test-generator",
            "default": "test-default",  # Ensure a default is present for get_client("default")
        },
    }
    monkeypatch.setenv("LLM_MODELS_JSON", json.dumps(models_config))

    # Force a reload of the config to pick up monkeypatched vars
    reload_config()

    # Reset AgentKernel singleton to force it to reload its config
    AgentKernel._instance = None
    AgentKernel._config = None

    # Create fresh instances for the test
    kernel = AgentKernel(ollash_root_dir=temp_project_root)
    agent = DefaultAgent(kernel=kernel, project_root=str(temp_project_root))

    return agent
