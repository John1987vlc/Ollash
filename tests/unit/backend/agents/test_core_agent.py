import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from backend.agents.core_agent import CoreAgent
from backend.core.kernel import AgentKernel


class MockAgent(CoreAgent):
    """Concrete implementation of CoreAgent for testing."""

    def run(self, *args, **kwargs):
        return "running"


@pytest.fixture
def mock_kernel(tmp_path):
    kernel = MagicMock(spec=AgentKernel)
    kernel.ollash_root_dir = tmp_path

    # Setup tool settings mock to return dict with real values
    mock_tool_settings = MagicMock()
    mock_tool_settings.model_dump.return_value = {
        "use_docker_sandbox": False,
        "ollama_max_retries": 5,
        "ollama_backoff_factor": 1.0,
        "ollama_retry_status_forcelist": [500],
    }
    kernel.get_tool_settings_config.return_value = mock_tool_settings

    kernel.get_full_config.return_value = {"use_docker_sandbox": False}
    kernel.get_logger.return_value = MagicMock()

    mock_llm_config = MagicMock()
    mock_llm_config.ollama_url = "http://localhost:11434"
    mock_llm_config.default_timeout = 30
    kernel.get_llm_models_config.return_value = mock_llm_config

    return kernel


@pytest.fixture
def agent(mock_kernel):
    # Patch components where they are imported in CoreAgent
    with (
        patch("backend.agents.core_agent.CommandExecutor"),
        patch("backend.agents.core_agent.FileValidator"),
        patch("backend.agents.core_agent.DocumentationManager"),
        patch("backend.agents.core_agent.CrossReferenceAnalyzer"),
        patch("backend.agents.core_agent.DependencyScanner") as mock_ds_cls,
        patch("backend.agents.core_agent.RAGContextSelector") as mock_rag_cls,
        patch("backend.agents.core_agent.ConcurrentGPUAwareRateLimiter"),
        patch("backend.agents.core_agent.SessionResourceManager"),
        patch("backend.agents.core_agent.AutoModelSelector"),
        patch("backend.agents.core_agent.PermissionProfileManager"),
        patch("backend.agents.core_agent.PolicyEnforcer"),
        patch("backend.agents.core_agent.AutomaticLearningSystem"),
        patch("backend.agents.core_agent.LLMClientManager"),
    ):
        # We need the instances to be mocks too
        mock_agent = MockAgent(kernel=mock_kernel)
        mock_agent.rag_context_mock = mock_rag_cls.return_value
        mock_agent.ds_mock = mock_ds_cls.return_value
        return mock_agent


class TestCoreAgent:
    """Test suite for CoreAgent base functionality."""

    def test_init(self, agent, mock_kernel):
        assert agent.kernel == mock_kernel
        assert agent.ollash_root_dir == mock_kernel.ollash_root_dir

    def test_save_file(self, agent, tmp_path):
        test_file = tmp_path / "test.txt"
        content = "hello world"
        agent._save_file(test_file, content)

        assert test_file.exists()
        assert test_file.read_text() == content

    def test_select_related_files_heuristic(self, agent):
        files = {
            "src/app.py": "app code",
            "src/models.py": "model code",
            "src/utils.py": "utils code",
            "docs/README.md": "readme",
            "package.json": "{}",
        }

        # Use the captured mock instance
        agent.rag_context_mock.select_relevant_files.return_value = {}

        related = agent._select_related_files("src/routes.py", files, max_files=2)

        assert len(related) <= 2
        assert "src/app.py" in related or "src/models.py" in related

    def test_reconcile_requirements_delegation(self, agent):
        files = {"requirements.txt": ""}
        # Use the captured mock instance
        agent.ds_mock.reconcile_dependencies.return_value = files

        agent._reconcile_requirements(files, Path("."), "3.10")
        agent.ds_mock.reconcile_dependencies.assert_called_once()
