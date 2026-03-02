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
    tracker = TokenTracker()
    llm_manager = MagicMock()
    response_parser = MagicMock()
    logger = MagicMock()
    blackboard = MagicMock()

    # Create PhaseContext
    context = PhaseContext(
        config={},
        logger=logger,
        ollash_root_dir=tmp_path,
        llm_manager=llm_manager,
        response_parser=response_parser,
        file_manager=MagicMock(),
        file_validator=MagicMock(),
        documentation_manager=MagicMock(),
        event_publisher=MagicMock(),
        code_quarantine=MagicMock(),
        fragment_cache=MagicMock(),
        dependency_graph=MagicMock(),
        dependency_scanner=MagicMock(),
        parallel_generator=MagicMock(),
        error_knowledge_base=MagicMock(),
        policy_enforcer=MagicMock(),
        rag_context_selector=MagicMock(),
        project_planner=MagicMock(),
        structure_generator=MagicMock(),
        file_content_generator=MagicMock(),
        file_refiner=MagicMock(),
        file_completeness_checker=MagicMock(),
        project_reviewer=MagicMock(),
        improvement_suggester=MagicMock(),
        improvement_planner=MagicMock(),
        senior_reviewer=MagicMock(),
        test_generator=MagicMock(),
        contingency_planner=MagicMock(),
        structure_pre_reviewer=MagicMock(),
        generated_projects_dir=tmp_path / "gen",
        decision_blackboard=blackboard,
        token_tracker=tracker,
    )

    assert context.token_tracker == tracker
    # Verify sub-context has it
    assert context.llm.token_tracker == tracker
