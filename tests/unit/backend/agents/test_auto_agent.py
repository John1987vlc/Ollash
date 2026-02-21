import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from backend.agents.auto_agent import AutoAgent


@pytest.fixture
def mock_kernel():
    kernel = MagicMock()
    kernel.get_full_config.return_value = {"generated_projects_dir": "gen"}
    kernel.get_logger.return_value = MagicMock()
    kernel.get_llm_models_config.return_value = MagicMock()
    kernel.get_tool_settings_config.return_value = MagicMock()
    return kernel


@pytest.fixture
def mock_context(tmp_path):
    ctx = MagicMock()
    ctx.generated_projects_dir = tmp_path / "gen"
    ctx.error_knowledge_base = MagicMock()
    ctx.fragment_cache = MagicMock()
    ctx.file_manager = MagicMock()
    ctx.initial_exec_params = {}
    ctx.ingest_existing_project.return_value = ({}, {}, [])
    return ctx


@pytest.fixture
def auto_agent(mock_kernel, mock_context):
    with (
        patch("backend.utils.core.command_executor.CommandExecutor"),
        patch("backend.utils.core.analysis.file_validator.FileValidator"),
        patch("backend.utils.core.io.documentation_manager.DocumentationManager"),
        patch("backend.utils.core.memory.cross_reference_analyzer.CrossReferenceAnalyzer"),
        patch("backend.utils.core.analysis.scanners.dependency_scanner.DependencyScanner"),
        patch("backend.utils.core.analysis.scanners.rag_context_selector.RAGContextSelector"),
        patch("backend.utils.core.system.concurrent_rate_limiter.ConcurrentGPUAwareRateLimiter"),
        patch("backend.utils.core.system.concurrent_rate_limiter.SessionResourceManager"),
        patch("backend.utils.core.llm.benchmark_model_selector.AutoModelSelector"),
        patch("backend.utils.core.system.permission_profiles.PermissionProfileManager"),
        patch("backend.utils.core.system.permission_profiles.PolicyEnforcer"),
        patch("backend.utils.core.memory.automatic_learning.AutomaticLearningSystem"),
        patch("backend.services.llm_client_manager.LLMClientManager") as mock_llm_mgr,
    ):
        agent = AutoAgent(
            phase_context=mock_context,
            phases=[],
            project_analysis_phase_factory=MagicMock(),
            kernel=mock_kernel,
            llm_manager=mock_llm_mgr.return_value,
        )
        return agent


class TestAutoAgent:
    """Test suite for AutoAgent project pipeline orchestration."""

    def test_init(self, auto_agent, mock_context):
        assert auto_agent.phase_context == mock_context
        assert mock_context.auto_agent == auto_agent

    def test_run_orchestration(self, auto_agent, mock_context, tmp_path):
        mock_phase = MagicMock()
        mock_phase.execute = AsyncMock(return_value=({}, {}, []))
        auto_agent.phases = [mock_phase]

        with patch("backend.agents.auto_agent.ExecutionPlan") as mock_plan_cls:
            mock_plan = mock_plan_cls.return_value

            project_root = auto_agent.run("create a website", "my_site")

            assert "my_site" in str(project_root)
            mock_phase.execute.assert_called_once()

    def test_run_existing_project(self, auto_agent, mock_context, tmp_path):
        project_name = "existing"
        project_dir = tmp_path / "gen" / project_name
        project_dir.mkdir(parents=True)
        (project_dir / "file.txt").write_text("content")

        mock_analysis_phase = MagicMock()
        mock_analysis_phase.execute = AsyncMock(return_value=({}, {}, []))
        auto_agent.project_analysis_phase_factory.return_value = mock_analysis_phase

        auto_agent.phases = []

        with patch("backend.agents.auto_agent.ExecutionPlan"):
            auto_agent.run("update project", project_name)
            mock_context.ingest_existing_project.assert_called_once_with(project_dir)
            mock_analysis_phase.execute.assert_called_once()

    def test_generate_structure_only(self, auto_agent, mock_context):
        with patch.object(auto_agent, "_run_structure_phases_async", new=AsyncMock()) as mock_run_async:
            mock_run_async.return_value = ("readme", {"struct": "data"})

            readme, struct = auto_agent.generate_structure_only("desc", "name")

            assert readme == "readme"
            assert struct == {"struct": "data"}
            mock_run_async.assert_called_once()
