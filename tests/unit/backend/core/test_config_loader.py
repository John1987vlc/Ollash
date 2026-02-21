import pytest
from unittest.mock import MagicMock, patch

from backend.core.config_loader import ConfigLoader
from backend.core.config_schemas import LLMModelsConfig, AgentFeaturesConfig, ToolSettingsConfig


@pytest.fixture
def mock_logger():
    """Fixture for AgentLogger mock."""
    return MagicMock()


@pytest.fixture
def valid_raw_config():
    """Fixture for a valid raw configuration structure."""

    class MockConfig:
        LLM_MODELS = {"ollama_url": "http://test-server:11434", "default_model": "test-model:latest"}
        AGENT_FEATURES = {"cross_reference": True, "ocr_enabled": False}
        TOOL_SETTINGS = {"sandbox": "full", "max_iterations": 10}

    return MockConfig()


class TestConfigLoader:
    """Test suite for ConfigLoader class."""

    def test_init_success(self, mock_logger, valid_raw_config):
        """Test successful initialization and validation with valid data."""
        with patch("backend.core.config_loader.get_config", return_value=valid_raw_config):
            loader = ConfigLoader(mock_logger)

            # Verify logger was called
            mock_logger.info.assert_any_call("Loading configuration from central config object.")
            mock_logger.info.assert_any_call("All configurations loaded and validated successfully.")

            # Verify loaded models
            llm_config = loader.get_config("llm_models")
            assert isinstance(llm_config, LLMModelsConfig)
            assert str(llm_config.ollama_url) == "http://test-server:11434/"
            assert llm_config.default_model == "test-model:latest"

            features_config = loader.get_config("agent_features")
            assert isinstance(features_config, AgentFeaturesConfig)
            assert features_config.cross_reference is True

            tools_config = loader.get_config("tool_settings")
            assert isinstance(tools_config, ToolSettingsConfig)
            assert tools_config.sandbox_level == "full"

    def test_init_with_missing_optional_fields(self, mock_logger):
        """Test initialization with minimal data, verifying Pydantic defaults."""

        class MinimalConfig:
            LLM_MODELS = {}  # All fields in LLMModelsConfig have defaults or are optional
            AGENT_FEATURES = {}
            TOOL_SETTINGS = {}

        with patch("backend.core.config_loader.get_config", return_value=MinimalConfig()):
            loader = ConfigLoader(mock_logger)

            llm_config = loader.get_config("llm_models")
            assert llm_config.default_model == "mistral:latest"  # Default from schema
            assert str(llm_config.ollama_url).rstrip("/") == "http://localhost:11434"

    def test_init_validation_error(self, mock_logger):
        """Test that RuntimeError is raised when data violates schema."""

        class InvalidConfig:
            LLM_MODELS = {
                "ollama_url": "not-a-url"  # Should fail pydantic HttpUrl validation
            }
            AGENT_FEATURES = {}
            TOOL_SETTINGS = {}

        with patch("backend.core.config_loader.get_config", return_value=InvalidConfig()):
            with pytest.raises(RuntimeError) as excinfo:
                ConfigLoader(mock_logger)

            assert "Invalid configuration" in str(excinfo.value)
            mock_logger.error.assert_called()

    def test_init_unexpected_exception(self, mock_logger):
        """Test handling of unexpected non-pydantic exceptions."""
        # ConfigLoader wraps unexpected exceptions into RuntimeError
        with patch("backend.core.config_loader.get_config", side_effect=Exception("Database down")):
            with pytest.raises(RuntimeError) as excinfo:
                ConfigLoader(mock_logger)

            assert "Configuration error" in str(excinfo.value)
            assert "Database down" in str(excinfo.value)

    def test_get_raw_config_data(self, mock_logger, valid_raw_config):
        """Test that get_raw_config_data returns the original data dict."""
        with patch("backend.core.config_loader.get_config", return_value=valid_raw_config):
            loader = ConfigLoader(mock_logger)
            raw_data = loader.get_raw_config_data()

            assert raw_data["llm_models"] == valid_raw_config.LLM_MODELS
            assert raw_data["agent_features"] == valid_raw_config.AGENT_FEATURES
            assert raw_data["tool_settings"] == valid_raw_config.TOOL_SETTINGS

    def test_get_config_invalid_key(self, mock_logger, valid_raw_config):
        """Test get_config with a key that doesn't exist."""
        with patch("backend.core.config_loader.get_config", return_value=valid_raw_config):
            loader = ConfigLoader(mock_logger)
            assert loader.get_config("non_existent_key") is None

    def test_logger_property_and_setter(self, mock_logger, valid_raw_config):
        """Test the logger property and its setter."""
        with patch("backend.core.config_loader.get_config", return_value=valid_raw_config):
            loader = ConfigLoader(mock_logger)
            assert loader.logger == mock_logger

            new_logger = MagicMock()
            loader.logger = new_logger
            assert loader.logger == new_logger
