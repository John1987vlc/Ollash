"""Agent and kernel fixtures — DefaultAgent, AgentKernel mock, project root."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.core.kernel import AgentKernel
from backend.agents.default_agent import DefaultAgent


@pytest.fixture(scope="session")
def project_root():
    """Returns the absolute path to the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def mock_kernel(tmp_path_factory):
    """Provides a fully mocked AgentKernel for unit tests."""
    tmp_path = tmp_path_factory.mktemp("ollash_test_root")
    kernel = MagicMock(spec=AgentKernel)
    kernel.ollash_root_dir = tmp_path

    mock_tool_config = MagicMock()
    mock_tool_config.max_iterations = 5
    mock_tool_config.default_system_prompt_path = "prompts/default.json"
    mock_tool_config.model_dump.return_value = {
        "ollama_max_retries": 5,
        "ollama_backoff_factor": 1.0,
        "ollama_retry_status_forcelist": [500],
    }
    kernel.get_tool_settings_config.return_value = mock_tool_config
    kernel.get_full_config.return_value = {
        "use_docker_sandbox": False,
        "models": {"summarization": "qwen"},
    }
    kernel.get_logger.return_value = MagicMock()

    mock_llm_config = MagicMock()
    mock_llm_config.ollama_url = "http://localhost:11434"
    mock_llm_config.default_model = "qwen3-coder:30b"
    mock_llm_config.default_timeout = 30
    mock_llm_config.agent_roles = {"orchestrator": "qwen3-coder:30b"}
    kernel.get_llm_models_config.return_value = mock_llm_config

    return kernel


@pytest.fixture
def default_agent(mock_kernel, tmp_path_factory):
    """Provides a fully initialized DefaultAgent with mocked I/O dependencies."""
    tmp_path = tmp_path_factory.mktemp("agent_data")
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "default.json").write_text(json.dumps({"prompt": "You are a test agent"}))

    with (
        patch("backend.agents.default_agent.FileManager"),
        patch("backend.agents.default_agent.CommandExecutor"),
    ):
        agent = DefaultAgent(kernel=mock_kernel)
        agent.logger = MagicMock()
        return agent
