import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from contextlib import ExitStack
from backend.agents.default_agent import DefaultAgent
from backend.core.kernel import AgentKernel


@pytest.fixture
def mock_kernel(tmp_path):
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

    kernel.get_full_config.return_value = {"use_docker_sandbox": False, "models": {"summarization": "qwen"}}
    kernel.get_logger.return_value = MagicMock()

    mock_llm_config = MagicMock()
    mock_llm_config.ollama_url = "http://localhost:11434"
    mock_llm_config.default_model = "qwen3"
    mock_llm_config.default_timeout = 30
    mock_llm_config.agent_roles = {"orchestrator": "qwen3"}
    kernel.get_llm_models_config.return_value = mock_llm_config

    return kernel


@pytest.fixture
def default_agent(mock_kernel, tmp_path):
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "default.json").write_text(json.dumps({"prompt": "You are a test agent"}))

    # Use ExitStack to handle many patches
    with ExitStack() as stack:
        # Patch where they are imported in default_agent.py or core_agent.py
        patches = [
            "backend.agents.default_agent.FileManager",
            "backend.agents.default_agent.CommandExecutor",
            "backend.agents.default_agent.GitManager",
            "backend.agents.default_agent.CodeAnalyzer",
            "backend.agents.default_agent.MemoryManager",
            "backend.agents.default_agent.ConfirmationManager",
            "backend.agents.default_agent.PolicyEnforcer",
            "backend.agents.default_agent.ToolRegistry",
            "backend.agents.default_agent.ToolExecutor",
            "backend.agents.default_agent.LoopDetector",
            "backend.agents.default_agent.LLMRecorder",
            "backend.agents.default_agent.ToolSpanManager",
            # Patches from CoreAgent (since DefaultAgent calls super().__init__)
            "backend.agents.core_agent.LLMClientManager",
            "backend.agents.core_agent.PermissionProfileManager",
            "backend.agents.core_agent.DocumentationManager",
            "backend.agents.core_agent.CrossReferenceAnalyzer",
            "backend.agents.core_agent.DependencyScanner",
            "backend.agents.core_agent.RAGContextSelector",
            "backend.agents.core_agent.ConcurrentGPUAwareRateLimiter",
            "backend.agents.core_agent.SessionResourceManager",
            "backend.agents.core_agent.AutoModelSelector",
            "backend.agents.core_agent.AutomaticLearningSystem",
            # Critical: OllamaClient accessed via LLMClientManager
            "backend.services.llm_client_manager.OllamaClient",
        ]
        for p in patches:
            stack.enter_context(patch(p))

        agent = DefaultAgent(kernel=mock_kernel, project_root=str(tmp_path), base_path=tmp_path)
        return agent


class TestDefaultAgent:
    """Test suite for DefaultAgent orchestration logic."""

    def test_init(self, default_agent):
        assert default_agent.active_agent_type == "orchestrator"
        assert default_agent.system_prompt == "You are a test agent"

    @pytest.mark.asyncio
    async def test_chat_simple_response(self, default_agent):
        default_agent._preprocess_instruction = AsyncMock(return_value=("refined", "en"))
        default_agent._classify_intent = AsyncMock(return_value="coding")

        mock_client = AsyncMock()
        mock_client.model = "test-model"
        mock_client.achat.return_value = (
            {"message": {"content": "Final answer"}},
            {"prompt_tokens": 10, "completion_tokens": 10},
        )
        default_agent._select_model_for_intent = MagicMock(return_value=mock_client)
        default_agent._translate_to_user_language = AsyncMock(return_value="Final answer")
        default_agent._manage_context_window = AsyncMock(side_effect=lambda msgs: msgs)

        result = await default_agent.chat("hello")

        assert result["text"] == "Final answer"
        assert result["metrics"]["iterations"] == 1

    @pytest.mark.asyncio
    async def test_chat_tool_call_loop(self, default_agent):
        default_agent._preprocess_instruction = AsyncMock(return_value=("refined", "en"))
        default_agent._classify_intent = AsyncMock(return_value="coding")

        mock_client = AsyncMock()
        mock_client.model = "test-model"

        mock_client.achat.side_effect = [
            (
                {"message": {"tool_calls": [{"id": "call_1", "function": {"name": "test_tool", "arguments": {}}}]}},
                {"total_tokens": 20},
            ),
            ({"message": {"content": "Task done"}}, {"total_tokens": 10}),
        ]
        default_agent._select_model_for_intent = MagicMock(return_value=mock_client)
        default_agent._execute_tool_loop = AsyncMock(return_value=[{"ok": True, "result": "tool output"}])
        default_agent._manage_context_window = AsyncMock(side_effect=lambda msgs: msgs)
        default_agent._translate_to_user_language = AsyncMock(return_value="Task done")

        result = await default_agent.chat("do tool")

        assert result["text"] == "Task done"
        assert result["metrics"]["iterations"] == 2

    def test_get_fallback_system_prompt(self, default_agent):
        prompt = default_agent._get_fallback_system_prompt()
        assert "disciplined coding agent" in prompt
