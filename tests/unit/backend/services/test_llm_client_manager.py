import pytest
from unittest.mock import MagicMock, patch
from backend.services.llm_client_manager import LLMClientManager
from backend.core.config_schemas import LLMModelsConfig, ToolSettingsConfig


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_recorder():
    return MagicMock()


@pytest.fixture
def llm_config():
    return LLMModelsConfig(
        ollama_url="http://localhost:11434",
        default_model="qwen3",
        embedding="mxbai-embed-large",
        agent_roles={"coder": "qwen3-coder", "analyst": "llama3"},
    )


@pytest.fixture
def tool_settings():
    return ToolSettingsConfig()


@pytest.fixture
def manager(llm_config, tool_settings, mock_logger, mock_recorder):
    return LLMClientManager(config=llm_config, tool_settings=tool_settings, logger=mock_logger, recorder=mock_recorder)


class TestLLMClientManager:
    """Test suite for LLMClientManager role-based routing."""

    async def test_get_client_by_role(self, manager):
        with patch("backend.services.llm_client_manager.OllamaClient") as mock_client_cls:
            client = await manager.get_client("coder")

            assert client == mock_client_cls.return_value
            mock_client_cls.assert_called_once()
            args, kwargs = mock_client_cls.call_args
            assert kwargs["model"] == "qwen3-coder"

    async def test_get_client_fallback_to_default(self, manager):
        with patch("backend.services.llm_client_manager.OllamaClient") as mock_client_cls:
            client = await manager.get_client("unknown_role")

            assert client == mock_client_cls.return_value
            args, kwargs = mock_client_cls.call_args
            assert kwargs["model"] == "qwen3"  # default_model

    async def test_client_caching(self, manager):
        with patch("backend.services.llm_client_manager.OllamaClient") as mock_client_cls:
            # First call creates
            client1 = await manager.get_client("coder")
            # Second call for SAME model (even if different role) should return same instance
            # In our config, 'coder' maps to 'qwen3-coder'

            # Let's map another role to same model to test caching
            manager.config.agent_roles["developer"] = "qwen3-coder"
            client2 = await manager.get_client("developer")

            assert client1 == client2
            assert mock_client_cls.call_count == 1

    async def test_get_embedding_client(self, manager):
        with patch("backend.services.llm_client_manager.OllamaClient") as mock_client_cls:
            client = await manager.get_embedding_client()

            assert client == mock_client_cls.return_value
            pass

    async def test_get_vision_client(self, manager):
        with patch("backend.services.llm_client_manager.OllamaClient") as mock_client_cls:
            client = await manager.get_vision_client()
            assert client == mock_client_cls.return_value
            args, kwargs = mock_client_cls.call_args
            assert kwargs["model"] == "llava"  # default fallback
