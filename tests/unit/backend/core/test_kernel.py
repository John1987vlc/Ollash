import pytest
import uuid
from unittest.mock import MagicMock, patch

from backend.core.kernel import AgentKernel
from backend.core.config_schemas import LLMModelsConfig, AgentFeaturesConfig, ToolSettingsConfig


@pytest.fixture
def mock_structured_logger():
    """Fixture for StructuredLogger mock."""
    return MagicMock()


@pytest.fixture
def mock_config_loader():
    """Fixture to mock ConfigLoader class in AgentKernel."""
    with patch("backend.core.kernel.ConfigLoader") as mock:
        yield mock


class TestAgentKernel:
    """Test suite for AgentKernel core component."""

    def test_init_creates_logs_dir(self, tmp_path):
        """Test that __init__ creates a logs directory if not provided."""
        # Using tmp_path to avoid polluting project root
        kernel = AgentKernel(ollash_root_dir=tmp_path)
        log_dir = tmp_path / "logs"
        assert log_dir.exists()
        assert log_dir.is_dir()
        assert kernel.ollash_root_dir == tmp_path

    def test_init_uses_provided_logger(self, tmp_path, mock_structured_logger):
        """Test that provided structured logger is used."""
        kernel = AgentKernel(ollash_root_dir=tmp_path, structured_logger=mock_structured_logger)
        assert kernel._structured_logger == mock_structured_logger

    def test_get_llm_models_config_success(self, tmp_path, mock_config_loader):
        """Test successful retrieval of LLM models config."""
        mock_config = MagicMock(spec=LLMModelsConfig)
        mock_instance = mock_config_loader.return_value
        mock_instance.get_config.return_value = mock_config

        kernel = AgentKernel(ollash_root_dir=tmp_path)
        config = kernel.get_llm_models_config()

        assert config == mock_config
        mock_instance.get_config.assert_called_with("llm_models")

    def test_get_llm_models_config_failure(self, tmp_path, mock_config_loader):
        """Test that RuntimeError is raised if config is missing or invalid type."""
        mock_instance = mock_config_loader.return_value
        mock_instance.get_config.return_value = None  # Not a LLMModelsConfig

        kernel = AgentKernel(ollash_root_dir=tmp_path)
        with pytest.raises(RuntimeError) as excinfo:
            kernel.get_llm_models_config()
        assert "LLM models configuration not loaded" in str(excinfo.value)

    def test_get_agent_features_config_success(self, tmp_path, mock_config_loader):
        """Test successful retrieval of agent features config."""
        mock_config = MagicMock(spec=AgentFeaturesConfig)
        mock_instance = mock_config_loader.return_value
        mock_instance.get_config.return_value = mock_config

        kernel = AgentKernel(ollash_root_dir=tmp_path)
        config = kernel.get_agent_features_config()
        assert config == mock_config
        mock_instance.get_config.assert_called_with("agent_features")

    def test_get_tool_settings_config_success(self, tmp_path, mock_config_loader):
        """Test successful retrieval of tool settings config."""
        mock_config = MagicMock(spec=ToolSettingsConfig)
        mock_instance = mock_config_loader.return_value
        mock_instance.get_config.return_value = mock_config

        kernel = AgentKernel(ollash_root_dir=tmp_path)
        config = kernel.get_tool_settings_config()
        assert config == mock_config
        mock_instance.get_config.assert_called_with("tool_settings")

    def test_get_full_config(self, tmp_path, mock_config_loader):
        """Test retrieval of raw configuration data."""
        raw_data = {"key": "value"}
        mock_instance = mock_config_loader.return_value
        mock_instance.get_raw_config_data.return_value = raw_data

        kernel = AgentKernel(ollash_root_dir=tmp_path)
        assert kernel.get_full_config() == raw_data

    @patch("backend.core.kernel.set_correlation_id")
    @patch("backend.core.kernel.uuid.uuid4")
    def test_interaction_context_start_stop(self, mock_uuid, mock_set_corr, tmp_path):
        """Test starting and ending interaction context with correlation ID."""
        fixed_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        mock_uuid.return_value = fixed_uuid

        kernel = AgentKernel(ollash_root_dir=tmp_path)

        # Start
        corr_id = kernel.start_interaction_context()
        assert corr_id == str(fixed_uuid)
        mock_set_corr.assert_called_with(str(fixed_uuid))

        # End
        kernel.end_interaction_context(corr_id, status="finished")
        mock_set_corr.assert_called_with(None)

    def test_get_logger(self, tmp_path):
        """Test retrieval of AgentLogger."""
        kernel = AgentKernel(ollash_root_dir=tmp_path)
        logger = kernel.get_logger()
        from backend.utils.core.system.agent_logger import AgentLogger

        assert isinstance(logger, AgentLogger)
        assert logger.name == "AgentKernel"
