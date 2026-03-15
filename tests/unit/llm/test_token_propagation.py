from unittest.mock import MagicMock
from backend.utils.core.llm.token_tracker import TokenTracker
from backend.utils.core.llm.ollama_client import OllamaClient
from backend.services.llm_client_manager import LLMClientManager
from backend.agents.auto_agent_phases.phase_context import PhaseContext


def test_token_tracker_propagation():
    # 1. Setup
    tracker = TokenTracker()
    logger = MagicMock()
    config = MagicMock()
    recorder = MagicMock()

    # 2. Test OllamaClient
    client = OllamaClient(
        url="http://localhost:11434",
        model="test-model",
        timeout=30,
        logger=logger,
        config={},
        llm_recorder=recorder,
        token_tracker=tracker,
    )
    assert client.token_tracker == tracker

    # 3. Test LLMClientManager
    models_config = MagicMock()
    models_config.ollama_url = "http://localhost:11434"
    models_config.agent_roles = {"coder": "qwen3"}
    models_config.default_timeout = 30

    tool_settings = MagicMock()
    tool_settings.model_dump.return_value = {}

    manager = LLMClientManager(
        config=models_config, tool_settings=tool_settings, logger=logger, recorder=recorder, token_tracker=tracker
    )

    assert manager.token_tracker == tracker

    # Get a client and verify it has the tracker
    coder_client = manager.get_client("coder")
    assert coder_client.token_tracker == tracker


def test_phase_context_propagation(tmp_path):
    """PhaseContext.record_tokens / total_tokens correctly aggregate usage."""
    ctx = PhaseContext(
        project_name="test",
        project_description="test",
        project_root=tmp_path,
        llm_manager=MagicMock(),
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )

    assert ctx.total_tokens() == 0
    ctx.record_tokens("phase1", prompt_tokens=100, completion_tokens=50)
    ctx.record_tokens("phase2", prompt_tokens=200, completion_tokens=80)
    assert ctx.total_tokens() == 430
