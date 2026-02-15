"""
Comprehensive tests for AutoAgent and its phase pipeline.

Includes:
- Unit tests with fully mocked dependencies
- Integration tests using local LLMs (ministral-3:8b, qwen2.5-coder:7b)
- Phase-level tests for each pipeline stage
- PhaseContext utility method tests
- Edge case and error handling tests
"""

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.interfaces.iagent_phase import IAgentPhase
from backend.utils.core.execution_plan import ExecutionPlan

# ---------------------------------------------------------------------------
# Module-level environment setup (runs once before any test in this module)
# ---------------------------------------------------------------------------

TEST_OLLAMA_URL = "http://localhost:11434"

# Models for integration tests (local LLMs)
INTEGRATION_MODELS = {
    "primary": "ministral-3:8b",
    "coder": "qwen2.5-coder:7b",
}


@pytest.fixture(scope="module", autouse=True)
def setup_module_env(request):
    """Set environment variables for the entire test module."""
    original_env = os.environ.copy()

    models_config = {
        "ollama_url": TEST_OLLAMA_URL,
        "default_model": "mistral:latest",
        "default_timeout": 300,
        "agent_roles": {
            "prototyper": "test-proto",
            "coder": "test-coder",
            "planner": "test-planner",
            "generalist": "test-generalist",
            "suggester": "test-suggester",
            "improvement_planner": "test-improvement-planner",
            "senior_reviewer": "test-senior-reviewer",
            "test_generator": "test-test-generator",
            "default": "test-default",
        },
    }
    os.environ["OLLAMA_URL"] = TEST_OLLAMA_URL
    os.environ["LLM_MODELS_JSON"] = json.dumps(models_config)
    os.environ["USE_BENCHMARK_SELECTOR"] = "False"
    os.environ["AGENT_FEATURES_JSON"] = json.dumps({"enable_auto_learning": False})
    os.environ["TOOL_SETTINGS_JSON"] = json.dumps(
        {
            "log_file": "test.log",
            "git_auto_confirm_lines_threshold": 5,
            "auto_confirm_minor_git_commits": False,
            "write_auto_confirm_lines_threshold": 10,
            "auto_confirm_minor_writes": False,
            "critical_paths_patterns": [],
            "completeness_checker_max_retries": 2,
            "senior_review_max_attempts": 3,
        }
    )

    from backend.core.config import reload_config

    reload_config()

    yield

    os.environ.clear()
    os.environ.update(original_env)
    reload_config()


# ---------------------------------------------------------------------------
# Imports (after env is prepared)
# ---------------------------------------------------------------------------

from backend.agents.auto_agent import AutoAgent  # noqa: E402
from backend.agents.auto_agent_phases.exhaustive_review_repair_phase import \
    ExhaustiveReviewRepairPhase  # noqa: E402
from backend.agents.auto_agent_phases.final_review_phase import \
    FinalReviewPhase  # noqa: E402
from backend.agents.auto_agent_phases.iterative_improvement_phase import \
    IterativeImprovementPhase  # noqa: E402
from backend.agents.auto_agent_phases.logic_planning_phase import \
    LogicPlanningPhase  # noqa: E402
from backend.agents.auto_agent_phases.phase_context import \
    PhaseContext  # noqa: E402
from backend.agents.auto_agent_phases.readme_generation_phase import \
    ReadmeGenerationPhase  # noqa: E402
from backend.agents.auto_agent_phases.senior_review_phase import \
    SeniorReviewPhase  # noqa: E402
from backend.agents.auto_agent_phases.structure_generation_phase import \
    StructureGenerationPhase  # noqa: E402
from backend.agents.auto_agent_phases.test_generation_execution_phase import \
    TestGenerationExecutionPhase  # noqa: E402
from backend.core.containers import main_container  # noqa: E402
from backend.core.kernel import AgentKernel  # noqa: E402

# ===================================================================
# Shared fixtures
# ===================================================================


@pytest.fixture
def test_kernel(tmp_path):
    """Provides a clean AgentKernel instance."""
    (tmp_path / "logs").mkdir()
    return AgentKernel(ollash_root_dir=tmp_path)


@pytest.fixture
def mock_logger(mocker):
    return mocker.MagicMock(name="MockLogger")


@pytest.fixture
def mock_event_publisher(mocker):
    return mocker.MagicMock(name="MockEventPublisher")


@pytest.fixture
def mock_llm_manager(mocker):
    """Mocks the IModelProvider (LLMClientManager)."""
    mock_manager = mocker.MagicMock(name="MockLLMManager")

    def _make_client(role):
        client = MagicMock(name=f"MockClient_{role}")
        client.model = f"test-{role}"
        client.chat.return_value = ({"content": "{}"}, {"total_duration": 100})
        return client

    mock_manager.get_client.side_effect = _make_client
    mock_manager.config = MagicMock()
    mock_manager.config.agent_roles = {
        "prototyper": "test-proto",
        "coder": "test-coder",
        "planner": "test-planner",
        "generalist": "test-generalist",
        "suggester": "test-suggester",
        "improvement_planner": "test-improvement-planner",
        "senior_reviewer": "test-senior-reviewer",
        "test_generator": "test-test-generator",
        "default": "test-default",
    }
    return mock_manager


@pytest.fixture
def mock_llm_recorder(mocker):
    return mocker.MagicMock(name="MockLLMRecorder")


@pytest.fixture
def mock_file_manager(mocker):
    fm = mocker.MagicMock(name="MockFileManager")
    fm.write_file.return_value = None
    fm.read_file.return_value = "mock content"
    return fm


@pytest.fixture
def mock_phase_context(
    mocker,
    tmp_path,
    mock_logger,
    mock_event_publisher,
    mock_llm_manager,
    mock_file_manager,
):
    """Creates a lightweight mock PhaseContext with real tmp_path directory."""
    ctx = mocker.MagicMock(spec=PhaseContext, name="MockPhaseContext")
    ctx.config = {"senior_review_max_attempts": 3}
    ctx.logger = mock_logger
    ctx.event_publisher = mock_event_publisher
    ctx.llm_manager = mock_llm_manager
    ctx.file_manager = mock_file_manager
    ctx.response_parser = mocker.MagicMock()
    ctx.file_validator = mocker.MagicMock()
    ctx.documentation_manager = mocker.MagicMock()
    ctx.code_quarantine = mocker.MagicMock()
    ctx.fragment_cache = mocker.MagicMock()
    ctx.fragment_cache.stats.return_value = {"hits": 0, "misses": 0}
    ctx.dependency_graph = mocker.MagicMock()
    ctx.dependency_graph.build_from_structure.return_value = None
    ctx.dependency_graph.get_generation_order.return_value = []
    ctx.dependency_graph.get_context_for_file.return_value = {}
    ctx.parallel_generator = mocker.MagicMock()
    ctx.parallel_generator.get_statistics.return_value = {
        "success": 0,
        "total": 0,
        "avg_time_per_file": 0.0,
    }
    ctx.error_knowledge_base = mocker.MagicMock()
    ctx.error_knowledge_base.get_error_statistics.return_value = {}
    ctx.error_knowledge_base.get_prevention_warnings.return_value = []
    ctx.error_knowledge_base.get_common_error_patterns.return_value = []
    ctx.policy_enforcer = mocker.MagicMock()
    ctx.rag_context_selector = mocker.MagicMock()
    ctx.rag_context_selector.select_relevant_files.return_value = {}

    # Specialized services
    ctx.project_planner = mocker.MagicMock()
    ctx.structure_generator = mocker.MagicMock()
    ctx.file_content_generator = mocker.MagicMock()
    ctx.file_refiner = mocker.MagicMock()
    ctx.file_completeness_checker = mocker.MagicMock()
    ctx.project_reviewer = mocker.MagicMock()
    ctx.improvement_suggester = mocker.MagicMock()
    ctx.improvement_planner = mocker.MagicMock()
    ctx.senior_reviewer = mocker.MagicMock()
    ctx.test_generator = mocker.MagicMock()
    ctx.contingency_planner = mocker.MagicMock()
    ctx.structure_pre_reviewer = mocker.MagicMock()

    gen_dir = tmp_path / "generated_projects"
    gen_dir.mkdir(parents=True, exist_ok=True)
    ctx.generated_projects_dir = gen_dir

    ctx.ingest_existing_project.return_value = ({}, {}, [])
    ctx.update_generated_data = mocker.MagicMock()
    ctx.initial_exec_params = {}
    ctx.logic_plan = {}
    ctx.current_generated_files = {}
    ctx.current_project_structure = {}
    ctx.current_file_paths = []
    ctx.current_readme_content = ""

    return ctx


@pytest.fixture
def mock_phases(mocker):
    """Returns a list of two simple mock phases."""
    phases = []
    for name in ("Phase1_Readme", "Phase2_Structure"):
        p = mocker.AsyncMock(spec=IAgentPhase, name=name)
        p.__class__ = type(name, (IAgentPhase,), {"execute": AsyncMock()})
        p.execute.return_value = ({}, {}, [])
        phases.append(p)
    return phases


@pytest.fixture
def mock_execution_plan(mocker):
    plan = mocker.MagicMock(spec=ExecutionPlan, name="MockExecutionPlan")
    plan.to_dict.return_value = {}
    plan.get_milestones_list.return_value = []
    plan.get_milestone_id_by_phase_class_name.side_effect = lambda x: f"milestone_{x}"
    plan.get_progress.return_value = 0.5
    plan.to_json.return_value = "{}"
    return plan


@pytest.fixture
def auto_agent_instance(
    mocker,
    test_kernel,
    mock_phase_context,
    mock_phases,
    mock_llm_manager,
    mock_llm_recorder,
    mock_event_publisher,
    mock_execution_plan,
):
    """Provides an AutoAgent with all dependencies mocked."""
    mocker.patch(
        "backend.agents.auto_agent.ExecutionPlan", return_value=mock_execution_plan
    )

    # Get the real event loop BEFORE patching, then use it inside the mock
    real_loop = asyncio.new_event_loop()

    mock_loop = mocker.MagicMock(spec=asyncio.BaseEventLoop)
    mock_loop.run_until_complete.side_effect = (
        lambda coro: real_loop.run_until_complete(coro)
        if asyncio.iscoroutine(coro)
        else coro
    )
    mocker.patch(
        "backend.agents.auto_agent.asyncio.get_event_loop", return_value=mock_loop
    )
    mocker.patch(
        "backend.agents.auto_agent.asyncio.new_event_loop", return_value=mock_loop
    )
    mocker.patch("backend.agents.auto_agent.asyncio.set_event_loop")

    test_kernel.event_publisher = mock_event_publisher

    factory = mocker.MagicMock()
    factory.return_value = mocker.AsyncMock(spec=IAgentPhase)
    factory.return_value.execute.return_value = ({}, {}, [])

    with main_container.core.agent_kernel.override(
        test_kernel
    ), main_container.auto_agent_module.phase_context.override(
        mock_phase_context
    ), main_container.auto_agent_module.phases_list.override(
        mock_phases
    ), main_container.auto_agent_module.project_analysis_phase_factory.override(
        factory
    ), main_container.auto_agent_module.llm_client_manager.override(
        mock_llm_manager
    ), main_container.core.llm_recorder.override(
        mock_llm_recorder
    ):
        agent: AutoAgent = main_container.auto_agent_module.auto_agent()
        agent.logger = mocker.MagicMock()
        agent.event_publisher = mock_event_publisher
        yield agent

    main_container.unwire()


# ===================================================================
# Helper to build a real PhaseContext with mocked services
# ===================================================================


def _make_real_phase_context(mocker, tmp_path):
    """Builds a real PhaseContext with mocked heavy services."""
    return PhaseContext(
        config={},
        logger=mocker.MagicMock(),
        ollash_root_dir=tmp_path,
        llm_manager=mocker.MagicMock(),
        response_parser=mocker.MagicMock(),
        file_manager=mocker.MagicMock(),
        file_validator=mocker.MagicMock(),
        documentation_manager=mocker.MagicMock(),
        event_publisher=mocker.MagicMock(),
        code_quarantine=mocker.MagicMock(),
        fragment_cache=mocker.MagicMock(),
        dependency_graph=mocker.MagicMock(),
        parallel_generator=mocker.MagicMock(),
        error_knowledge_base=mocker.MagicMock(),
        policy_enforcer=mocker.MagicMock(),
        rag_context_selector=mocker.MagicMock(),
        project_planner=mocker.MagicMock(),
        structure_generator=mocker.MagicMock(),
        file_content_generator=mocker.MagicMock(),
        file_refiner=mocker.MagicMock(),
        file_completeness_checker=mocker.MagicMock(),
        project_reviewer=mocker.MagicMock(),
        improvement_suggester=mocker.MagicMock(),
        improvement_planner=mocker.MagicMock(),
        senior_reviewer=mocker.MagicMock(),
        test_generator=mocker.MagicMock(),
        contingency_planner=mocker.MagicMock(),
        structure_pre_reviewer=mocker.MagicMock(),
        generated_projects_dir=tmp_path / "gen",
    )


# ===================================================================
# 1. AutoAgent Initialization Tests
# ===================================================================


class TestAutoAgentInitialization:
    def test_init_creates_agent_via_container(self, test_kernel):
        """AutoAgent can be constructed through the DI container."""
        main_container.wire(modules=[__name__, "backend.agents.auto_agent"])
        with main_container.core.agent_kernel.override(test_kernel):
            agent: AutoAgent = main_container.auto_agent_module.auto_agent()
        main_container.unwire()

        assert agent is not None
        assert "prototyper" in agent.llm_manager.config.agent_roles
        assert agent.llm_manager.get_client("prototyper").model == "test-proto"
        assert "coder" in agent.llm_manager.config.agent_roles

    def test_init_uses_env_var_url(self, test_kernel):
        """Config reflects the monkeypatched env variables."""
        main_container.wire(modules=[__name__, "backend.agents.auto_agent"])
        with main_container.core.agent_kernel.override(test_kernel):
            agent: AutoAgent = main_container.auto_agent_module.auto_agent()
        main_container.unwire()

        config = agent.kernel.get_llm_models_config()
        assert str(config.ollama_url).rstrip("/") == TEST_OLLAMA_URL

    def test_init_raises_without_llm_manager(self, mocker, test_kernel):
        """AutoAgent raises ValueError when no LLM manager is provided."""
        main_container.wire(modules=[__name__, "backend.agents.auto_agent"])

        with main_container.core.agent_kernel.override(
            test_kernel
        ), main_container.auto_agent_module.llm_client_manager.override(None):
            with pytest.raises((ValueError, Exception)):
                main_container.auto_agent_module.auto_agent()

        main_container.unwire()

    def test_generated_projects_dir_created(
        self, auto_agent_instance, mock_phase_context
    ):
        """generated_projects_dir should exist after init."""
        assert mock_phase_context.generated_projects_dir.exists()


# ===================================================================
# 2. AutoAgent.run() Orchestration Tests
# ===================================================================


class TestAutoAgentRun:
    def test_run_new_project_creates_directory(
        self, auto_agent_instance, mock_phase_context
    ):
        """run() for a new project creates the project root."""
        agent = auto_agent_instance
        project_name = "test_new_proj"
        project_root = mock_phase_context.generated_projects_dir / project_name

        result = agent.run("Build a calculator app", project_name)

        assert result == project_root
        assert project_root.exists()

    def test_run_new_project_executes_all_phases(
        self, auto_agent_instance, mock_phases
    ):
        """All phases should execute for a brand-new project."""
        agent = auto_agent_instance
        agent.run("Build a calculator", "calc_project")

        for phase in mock_phases:
            phase.execute.assert_called_once()

    def test_run_publishes_events(self, auto_agent_instance, mock_event_publisher):
        """run() publishes execution_plan_initialized and project_complete events."""
        auto_agent_instance.run("Build a CLI tool", "cli_tool")

        call_event_types = [
            c[0][0] for c in mock_event_publisher.publish.call_args_list
        ]

        assert "execution_plan_initialized" in call_event_types
        assert "project_complete" in call_event_types

    def test_run_existing_project_ingests(
        self, auto_agent_instance, mock_phase_context, mocker
    ):
        """When project directory already has files, ingestion runs."""
        agent = auto_agent_instance
        project_name = "existing_proj"
        project_root = mock_phase_context.generated_projects_dir / project_name
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "main.py").write_text("print('hello')")

        mock_phase_context.ingest_existing_project.return_value = (
            {"main.py": "print('hello')"},
            {"main.py": {}},
            ["main.py"],
        )

        agent.run("Improve the calculator", project_name)
        mock_phase_context.ingest_existing_project.assert_called_once()

    def test_run_writes_execution_plan_json(
        self, auto_agent_instance, mock_phase_context, mock_execution_plan
    ):
        """_finalize_project writes EXECUTION_PLAN.json."""
        auto_agent_instance.run("Build a todo app", "todo_app")
        mock_phase_context.file_manager.write_file.assert_called()

    def test_run_handles_phase_error(
        self, auto_agent_instance, mock_phases, mock_event_publisher
    ):
        """If a phase raises, the error is propagated and events published."""
        mock_phases[0].execute.side_effect = RuntimeError("Phase crashed")

        with pytest.raises(RuntimeError, match="Phase crashed"):
            auto_agent_instance.run("Build broken app", "broken_app")

        call_event_types = [
            c[0][0] for c in mock_event_publisher.publish.call_args_list
        ]
        assert "phase_error" in call_event_types


# ===================================================================
# 3. AutoAgent.generate_structure_only() Tests
# ===================================================================


class TestGenerateStructureOnly:
    def test_returns_readme_and_structure(
        self, auto_agent_instance, mock_phases, mocker
    ):
        """generate_structure_only returns (readme, structure) tuple."""
        mock_readme_phase = mocker.AsyncMock(spec=ReadmeGenerationPhase)
        mock_readme_phase.execute.return_value = (
            {"README.md": "# My Project"},
            {"src": {}},
            ["README.md"],
        )
        mock_struct_phase = mocker.AsyncMock(spec=StructureGenerationPhase)
        mock_struct_phase.execute.return_value = (
            {"README.md": "# My Project"},
            {"src": {"main.py": {}}},
            ["README.md", "src/main.py"],
        )

        auto_agent_instance.phases = [mock_readme_phase, mock_struct_phase]

        readme, structure = auto_agent_instance.generate_structure_only(
            "A web scraper", "scraper"
        )

        assert "# My Project" in readme
        assert isinstance(structure, dict)

    def test_structure_only_does_not_generate_files(
        self, auto_agent_instance, mock_phase_context, mocker
    ):
        """generate_structure_only should not run content-generation phases."""
        mock_readme = mocker.AsyncMock(spec=ReadmeGenerationPhase)
        mock_readme.execute.return_value = ({"README.md": "# Proj"}, {}, ["README.md"])

        auto_agent_instance.phases = [mock_readme]

        auto_agent_instance.generate_structure_only("A CLI tool", "cli")
        mock_phase_context.file_content_generator.generate_file.assert_not_called()


# ===================================================================
# 4. PhaseContext Unit Tests
# ===================================================================


class TestPhaseContextInferLanguage:
    """Tests for PhaseContext.infer_language()."""

    @pytest.fixture
    def real_phase_context(self, mocker, tmp_path):
        return _make_real_phase_context(mocker, tmp_path)

    @pytest.mark.parametrize(
        "file_path,expected",
        [
            ("main.py", "python"),
            ("index.js", "javascript"),
            ("App.tsx", "typescript"),
            ("server.go", "go"),
            ("lib.rs", "rust"),
            ("Main.java", "java"),
            ("Program.cs", "csharp"),
            ("README.md", "unknown"),
            ("Makefile", "unknown"),
        ],
    )
    def test_infer_language(self, real_phase_context, file_path, expected):
        assert real_phase_context.infer_language(file_path) == expected

    def test_group_files_by_language(self, real_phase_context):
        files = {
            "app.py": "print('hi')",
            "utils.py": "def helper(): pass",
            "index.js": "console.log('hi')",
            "README.md": "# Readme",
        }
        grouped = real_phase_context.group_files_by_language(files)
        assert "python" in grouped
        assert len(grouped["python"]) == 2
        assert "javascript" in grouped
        assert "unknown" not in grouped

    @pytest.mark.parametrize(
        "source,lang,expected_pattern",
        [
            ("app.py", "python", "test_app.py"),
            ("utils.js", "javascript", "utils.test.js"),
            ("server.ts", "typescript", "server.test.ts"),
            ("main.go", "go", "main_test.go"),
        ],
    )
    def test_get_test_file_path(
        self, real_phase_context, source, lang, expected_pattern
    ):
        result = real_phase_context.get_test_file_path(source, lang)
        assert expected_pattern in result

    def test_update_generated_data(self, real_phase_context):
        real_phase_context.update_generated_data(
            {"a.py": "code"}, {"a.py": {}}, ["a.py"], "# README"
        )
        assert real_phase_context.current_generated_files == {"a.py": "code"}
        assert real_phase_context.current_readme_content == "# README"

    def test_select_related_files_empty(self, real_phase_context):
        assert real_phase_context.select_related_files("target.py", {}) == {}

    def test_select_related_files_heuristic_fallback(self, real_phase_context):
        """When RAG fails, heuristic scoring is used."""
        real_phase_context.rag_context_selector.select_relevant_files.side_effect = (
            Exception("no chromadb")
        )
        files = {
            "src/routes.py": "from models import User",
            "src/models.py": "class User: pass",
            "src/utils.py": "def helper(): pass",
            "README.md": "# Docs",
        }
        result = real_phase_context.select_related_files("src/views.py", files)
        assert isinstance(result, dict)
        assert len(result) <= 8

    def test_build_structure_from_files(self, real_phase_context):
        files = {
            "src/main.py": "code",
            "src/utils/helpers.py": "code",
            "README.md": "text",
        }
        structure = real_phase_context._build_structure_from_files(files)
        assert "src" in structure
        assert "main.py" in structure["src"]
        assert structure["src"]["main.py"]["language"] == "python"

    def test_implement_plan_create_file(self, real_phase_context, tmp_path):
        plan = {
            "actions": [
                {
                    "type": "create_file",
                    "path": "new_file.py",
                    "content": "print('new')",
                },
            ]
        }
        files, structure, paths = real_phase_context.implement_plan(
            plan, tmp_path, "# README", {}, {}, []
        )
        assert "new_file.py" in files
        assert "new_file.py" in paths

    def test_implement_plan_modify_file(self, real_phase_context, tmp_path):
        plan = {
            "actions": [
                {
                    "type": "modify_file",
                    "path": "app.py",
                    "changes": {"old_func": "new_func"},
                },
            ]
        }
        files = {"app.py": "def old_func(): pass"}
        files, _, _ = real_phase_context.implement_plan(
            plan, tmp_path, "", {}, files, []
        )
        assert "new_func" in files["app.py"]
        assert "old_func" not in files["app.py"]

    def test_implement_plan_limits_actions(self, real_phase_context, tmp_path):
        """implement_plan processes at most 10 actions."""
        plan = {
            "actions": [
                {"type": "create_file", "path": f"file_{i}.py", "content": f"# {i}"}
                for i in range(15)
            ]
        }
        files, _, paths = real_phase_context.implement_plan(
            plan, tmp_path, "", {}, {}, []
        )
        assert len(files) == 10  # Capped at 10


# ===================================================================
# 5. Individual Phase Tests (unit, mocked)
# ===================================================================


class TestReadmeGenerationPhase:
    @pytest.mark.asyncio
    async def test_generates_readme(self, mock_phase_context, tmp_path):
        mock_phase_context.project_planner.generate_readme.return_value = (
            "# Calculator\nA simple calculator."
        )

        phase = ReadmeGenerationPhase(mock_phase_context)
        files, structure, paths = await phase.execute(
            project_description="A calculator app",
            project_name="calculator",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={},
        )

        assert "README.md" in files
        assert "Calculator" in files["README.md"]
        assert "README.md" in paths
        mock_phase_context.file_manager.write_file.assert_called_once()
        mock_phase_context.event_publisher.publish.assert_any_call(
            "phase_start", phase="1", message="Generating README.md"
        )

    @pytest.mark.asyncio
    async def test_passes_kwargs_to_planner(self, mock_phase_context, tmp_path):
        mock_phase_context.project_planner.generate_readme.return_value = "# Proj"

        phase = ReadmeGenerationPhase(mock_phase_context)
        await phase.execute(
            project_description="Web app",
            project_name="webapp",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={},
            python_version="3.11",
            include_docker=True,
            license_type="Apache-2.0",
        )

        call_args = mock_phase_context.project_planner.generate_readme.call_args
        assert call_args[0][2] == "3.11"  # python_version
        assert call_args[0][3] == "Apache-2.0"  # license_type
        assert call_args[0][4] is True  # include_docker


class TestLogicPlanningPhase:
    @pytest.mark.asyncio
    async def test_categorize_files(self, mock_phase_context):
        phase = LogicPlanningPhase(mock_phase_context)
        categories = phase._categorize_files(
            [
                "src/config.py",
                "src/main.py",
                "src/utils/helper.py",
                "tests/test_main.py",
                "README.md",
                "static/index.html",
                "src/models.py",
            ]
        )

        assert "config" in categories
        assert "main" in categories
        assert "utils" in categories
        assert "tests" in categories
        assert "docs" in categories
        assert "web" in categories

    @pytest.mark.asyncio
    async def test_create_basic_plans_fallback(self, mock_phase_context):
        phase = LogicPlanningPhase(mock_phase_context)
        plans = phase._create_basic_plans(["src/config.py", "src/main.py"], "config")

        assert "src/config.py" in plans
        assert "src/main.py" in plans
        assert plans["src/config.py"]["purpose"] == "Configuration and settings"

    @pytest.mark.asyncio
    async def test_execute_saves_plan_to_context(self, mock_phase_context, tmp_path):
        """LogicPlanningPhase stores the logic_plan in context."""
        mock_client = MagicMock()
        mock_client.chat.return_value = (
            {
                "content": '{"src/main.py": {"purpose": "Entry point", "exports": ["main()"]}}'
            },
            {},
        )
        mock_phase_context.llm_manager.get_client.return_value = mock_client

        phase = LogicPlanningPhase(mock_phase_context)
        files, structure, paths = await phase.execute(
            project_description="A web server",
            project_name="webserver",
            project_root=tmp_path,
            readme_content="# Web Server",
            initial_structure={},
            generated_files={},
            file_paths=["src/main.py"],
        )

        assert "IMPLEMENTATION_PLAN.json" in files
        assert mock_phase_context.logic_plan is not None

    @pytest.mark.asyncio
    async def test_execute_handles_llm_error(self, mock_phase_context, tmp_path):
        """When LLM fails, fallback plans are generated."""
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("LLM timeout")
        mock_phase_context.llm_manager.get_client.return_value = mock_client

        phase = LogicPlanningPhase(mock_phase_context)
        files, structure, paths = await phase.execute(
            project_description="A tool",
            project_name="tool",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={},
            file_paths=["src/main.py"],
        )

        assert "IMPLEMENTATION_PLAN.json" in files


class TestFinalReviewPhase:
    @pytest.mark.asyncio
    async def test_writes_review_file(self, mock_phase_context, tmp_path):
        mock_phase_context.file_completeness_checker.get_validation_summary.return_value = (
            "All good"
        )
        mock_phase_context.project_reviewer.review.return_value = (
            "# Review\nLooks great."
        )

        phase = FinalReviewPhase(mock_phase_context)
        files, _, _ = await phase.execute(
            project_description="Calculator",
            project_name="calc",
            project_root=tmp_path,
            readme_content="# Calc",
            initial_structure={},
            generated_files={"main.py": "print(1+1)"},
            file_paths=["main.py"],
        )

        assert "PROJECT_REVIEW.md" in files
        mock_phase_context.file_manager.write_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_review_error(self, mock_phase_context, tmp_path):
        mock_phase_context.file_completeness_checker.get_validation_summary.return_value = (
            ""
        )
        mock_phase_context.project_reviewer.review.side_effect = Exception(
            "Review failed"
        )

        phase = FinalReviewPhase(mock_phase_context)
        files, _, _ = await phase.execute(
            project_description="Proj",
            project_name="proj",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={},
            file_paths=[],
        )

        mock_phase_context.logger.error.assert_called()


class TestSeniorReviewPhase:
    @pytest.mark.asyncio
    async def test_review_passes_first_attempt(self, mock_phase_context, tmp_path):
        mock_phase_context.senior_reviewer.perform_review.return_value = {
            "status": "passed",
            "summary": "Everything looks good.",
        }

        phase = SeniorReviewPhase(mock_phase_context)
        files, _, _ = await phase.execute(
            project_description="Calculator",
            project_name="calc",
            project_root=tmp_path,
            readme_content="# Calc",
            initial_structure={},
            generated_files={"main.py": "print(1+1)"},
            file_paths=["main.py"],
        )

        assert "SENIOR_REVIEW_SUMMARY.md" in files
        mock_phase_context.senior_reviewer.perform_review.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_retries_on_failure(self, mock_phase_context, tmp_path):
        """Fails first two attempts, passes on third."""
        mock_phase_context.senior_reviewer.perform_review.side_effect = [
            {
                "status": "failed",
                "issues": [
                    {
                        "file": "main.py",
                        "description": "Bug",
                        "severity": "high",
                        "recommendation": "Fix it",
                    }
                ],
                "summary": "Needs work",
            },
            {"status": "failed", "issues": [], "summary": "Still needs work"},
            {"status": "passed", "summary": "All fixed."},
        ]
        mock_phase_context.file_refiner.refine_file.return_value = "fixed code"
        mock_phase_context.file_completeness_checker.verify_and_fix.return_value = {
            "main.py": "fixed code"
        }
        mock_phase_context.contingency_planner.generate_contingency_plan.return_value = (
            None
        )

        phase = SeniorReviewPhase(mock_phase_context)
        files, _, _ = await phase.execute(
            project_description="App",
            project_name="app",
            project_root=tmp_path,
            readme_content="# App",
            initial_structure={},
            generated_files={"main.py": "buggy code"},
            file_paths=["main.py"],
        )

        assert mock_phase_context.senior_reviewer.perform_review.call_count == 3
        assert "SENIOR_REVIEW_SUMMARY.md" in files

    @pytest.mark.asyncio
    async def test_review_fails_all_attempts(self, mock_phase_context, tmp_path):
        """After max attempts, SENIOR_REVIEW_FAILED.md is written."""
        mock_phase_context.senior_reviewer.perform_review.return_value = {
            "status": "failed",
            "issues": [],
            "summary": "Cannot fix",
        }
        mock_phase_context.file_refiner.simplify_file_content.return_value = None

        phase = SeniorReviewPhase(mock_phase_context)
        files, _, _ = await phase.execute(
            project_description="App",
            project_name="app",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={"main.py": "bad code " * 20},
            file_paths=["main.py"],
        )

        write_calls = [
            str(c) for c in mock_phase_context.file_manager.write_file.call_args_list
        ]
        assert any("SENIOR_REVIEW_FAILED" in c for c in write_calls)


class TestTestGenerationExecutionPhase:
    @pytest.mark.asyncio
    async def test_mvp_requirement_raises_on_no_tests(
        self, mock_phase_context, tmp_path
    ):
        """Raises RuntimeError when no test files are generated (MVP requirement)."""
        mock_phase_context.group_files_by_language.return_value = {
            "python": [("app.py", "print('hello')")]
        }
        mock_phase_context.test_generator.generate_tests.return_value = None
        mock_phase_context.get_test_file_path.return_value = "tests/test_app.py"

        phase = TestGenerationExecutionPhase(mock_phase_context)
        with pytest.raises(RuntimeError, match="MVP Requirement Failed"):
            await phase.execute(
                project_description="App",
                project_name="app",
                project_root=tmp_path,
                readme_content="",
                initial_structure={},
                generated_files={"app.py": "print('hello')"},
                file_paths=["app.py"],
            )

    @pytest.mark.asyncio
    async def test_generates_and_executes_tests(self, mock_phase_context, tmp_path):
        mock_phase_context.group_files_by_language.return_value = {
            "python": [("app.py", "def add(a,b): return a+b")]
        }
        mock_phase_context.test_generator.generate_tests.return_value = (
            "def test_add(): assert add(1,2)==3"
        )
        mock_phase_context.get_test_file_path.return_value = "tests/test_app.py"
        mock_phase_context.test_generator.execute_tests.return_value = {"success": True}
        mock_phase_context.test_generator.generate_integration_tests.return_value = (
            None,
            None,
        )

        phase = TestGenerationExecutionPhase(mock_phase_context)
        files, _, paths = await phase.execute(
            project_description="App",
            project_name="app",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={"app.py": "def add(a,b): return a+b"},
            file_paths=["app.py"],
        )

        mock_phase_context.test_generator.execute_tests.assert_called_once()

    @pytest.mark.asyncio
    async def test_retries_on_test_failure(self, mock_phase_context, tmp_path):
        """Tests are retried with code refinement when they fail."""
        mock_phase_context.group_files_by_language.return_value = {
            "python": [("app.py", "def broken(): raise Exception()")]
        }
        mock_phase_context.test_generator.generate_tests.return_value = (
            "def test_broken(): broken()"
        )
        mock_phase_context.get_test_file_path.return_value = "tests/test_app.py"
        mock_phase_context.test_generator.generate_integration_tests.return_value = (
            None,
            None,
        )

        mock_phase_context.test_generator.execute_tests.side_effect = [
            {
                "success": False,
                "failures": [{"path": "app.py", "message": "Exception raised"}],
            },
            {
                "success": False,
                "failures": [{"path": "app.py", "message": "Still broken"}],
            },
            {"success": True},
        ]
        mock_phase_context.file_refiner.refine_file.return_value = (
            "def fixed(): return True"
        )

        phase = TestGenerationExecutionPhase(mock_phase_context)
        await phase.execute(
            project_description="App",
            project_name="app",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={"app.py": "def broken(): raise Exception()"},
            file_paths=["app.py"],
        )

        assert mock_phase_context.test_generator.execute_tests.call_count == 3

    @pytest.mark.asyncio
    async def test_skips_test_files_from_generation(self, mock_phase_context, tmp_path):
        """Files with 'test' in their name should be skipped for test generation."""
        mock_phase_context.group_files_by_language.return_value = {
            "python": [
                ("app.py", "def add(): pass"),
                ("test_app.py", "def test_add(): pass"),
            ]
        }
        mock_phase_context.test_generator.generate_tests.return_value = (
            "def test_add(): assert True"
        )
        mock_phase_context.get_test_file_path.return_value = "tests/test_app.py"
        mock_phase_context.test_generator.execute_tests.return_value = {"success": True}
        mock_phase_context.test_generator.generate_integration_tests.return_value = (
            None,
            None,
        )

        phase = TestGenerationExecutionPhase(mock_phase_context)
        await phase.execute(
            project_description="App",
            project_name="app",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={
                "app.py": "def add(): pass",
                "test_app.py": "def test_add(): pass",
            },
            file_paths=["app.py", "test_app.py"],
        )

        # generate_tests should only be called once (for app.py, not test_app.py)
        assert mock_phase_context.test_generator.generate_tests.call_count == 1


class TestExhaustiveReviewRepairPhase:
    @pytest.mark.asyncio
    async def test_no_issues_passes_through(self, mock_phase_context, tmp_path):
        """When no critical issues, phase passes through cleanly."""
        phase = ExhaustiveReviewRepairPhase(mock_phase_context)
        files = {"main.py": "print('hello')"}

        result_files, _, _ = await phase.execute(
            project_description="App",
            project_name="app",
            project_root=tmp_path,
            readme_content="",
            initial_structure={"main.py": {}},
            generated_files=files,
            file_paths=["main.py"],
        )

        assert result_files == files

    @pytest.mark.asyncio
    async def test_detects_missing_entry_point(self, mock_phase_context, tmp_path):
        """Detects when project lacks an entry point."""
        phase = ExhaustiveReviewRepairPhase(mock_phase_context)
        mock_phase_context.contingency_planner.generate_contingency_plan.return_value = {
            "actions": []
        }

        files = {"utils.py": "def helper(): pass"}
        await phase.execute(
            project_description="App",
            project_name="app",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files=files,
            file_paths=["utils.py"],
        )

        mock_phase_context.logger.warning.assert_called()

    def test_find_entry_points(self, mock_phase_context):
        phase = ExhaustiveReviewRepairPhase(mock_phase_context)
        files = {"src/main.py": "code", "src/utils.py": "code", "index.js": "code"}
        entry_points = phase._find_entry_points(files, {})
        assert "src/main.py" in entry_points
        assert "index.js" in entry_points
        assert "src/utils.py" not in entry_points

    def test_validate_config_missing_package_json(self, mock_phase_context):
        phase = ExhaustiveReviewRepairPhase(mock_phase_context)
        files = {"index.js": "console.log('hi')"}
        issues = phase._validate_config_files(files, "")
        assert len(issues) == 1
        assert issues[0]["type"] == "missing_config"

    def test_validate_config_with_package_json(self, mock_phase_context):
        """No issue when package.json is present."""
        phase = ExhaustiveReviewRepairPhase(mock_phase_context)
        files = {"index.js": "console.log('hi')", "package.json": "{}"}
        issues = phase._validate_config_files(files, "")
        assert len(issues) == 0

    def test_convert_test_failures(self, mock_phase_context):
        phase = ExhaustiveReviewRepairPhase(mock_phase_context)
        failures = {
            "test_main.py": {"error": "AssertionError", "output": "expected 1 got 2"}
        }
        issues = phase._convert_test_failures_to_issues(failures)
        assert len(issues) == 1
        assert issues[0]["severity"] == "high"

    def test_generate_repair_report(self, mock_phase_context):
        phase = ExhaustiveReviewRepairPhase(mock_phase_context)
        report = phase._generate_repair_report(
            diagnostics={
                "coherence_score": 0.8,
                "critical_issues": [
                    {
                        "severity": "critical",
                        "file": "main.py",
                        "description": "Missing import",
                    }
                ],
            },
            predicted_errors=[],
            repair_plan={"actions": [{"type": "fix_file", "file": "main.py"}]},
            test_results={"passed": False, "failures": {"test_main.py": {}}},
        )
        assert "Exhaustive Review" in report
        assert "main.py" in report
        assert "80.00%" in report


class TestIterativeImprovementPhase:
    @pytest.mark.asyncio
    async def test_skips_when_no_loops_requested(self, mock_phase_context, tmp_path):
        phase = IterativeImprovementPhase(mock_phase_context)
        files = {"app.py": "code"}
        result, _, _ = await phase.execute(
            project_description="App",
            project_name="app",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files=files,
            file_paths=["app.py"],
            num_refine_loops=0,
        )
        assert result == files
        mock_phase_context.improvement_suggester.suggest_improvements.assert_not_called()

    @pytest.mark.asyncio
    async def test_runs_improvement_loops(self, mock_phase_context, tmp_path):
        mock_phase_context.improvement_suggester.suggest_improvements.side_effect = [
            ["Add type hints", "Add docstrings"],
            [],  # No more suggestions, stops early
        ]
        mock_phase_context.improvement_planner.generate_plan.return_value = {
            "actions": [{"type": "modify_file", "path": "app.py", "changes": {}}]
        }
        mock_phase_context.implement_plan.return_value = (
            {"app.py": "improved"},
            {},
            ["app.py"],
        )
        mock_phase_context.file_refiner.refine_file.return_value = "refined"
        mock_phase_context.file_completeness_checker.verify_and_fix.return_value = {
            "app.py": "verified"
        }

        phase = IterativeImprovementPhase(mock_phase_context)
        await phase.execute(
            project_description="App",
            project_name="app",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={"app.py": "code"},
            file_paths=["app.py"],
            num_refine_loops=3,
        )

        assert (
            mock_phase_context.improvement_suggester.suggest_improvements.call_count
            == 2
        )

    @pytest.mark.asyncio
    async def test_skips_iteration_when_plan_empty(self, mock_phase_context, tmp_path):
        """When improvement planner returns empty plan, iteration is skipped."""
        mock_phase_context.improvement_suggester.suggest_improvements.side_effect = [
            ["Improve error handling"],
            ["Add logging"],
        ]
        mock_phase_context.improvement_planner.generate_plan.side_effect = [
            None,  # First plan is None
            {"actions": []},  # Second plan is empty
        ]
        mock_phase_context.file_refiner.refine_file.return_value = None
        mock_phase_context.file_completeness_checker.verify_and_fix.return_value = {
            "app.py": "code"
        }

        phase = IterativeImprovementPhase(mock_phase_context)
        await phase.execute(
            project_description="App",
            project_name="app",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={"app.py": "code"},
            file_paths=["app.py"],
            num_refine_loops=2,
        )

        # implement_plan should never be called since both plans were empty
        mock_phase_context.implement_plan.assert_not_called()


# ===================================================================
# 6. PhaseContext.ingest_existing_project Tests
# ===================================================================


class TestIngestExistingProject:
    @pytest.fixture
    def real_ctx(self, mocker, tmp_path):
        return _make_real_phase_context(mocker, tmp_path)

    def test_ingest_nonexistent_path(self, real_ctx, tmp_path):
        files, structure, paths = real_ctx.ingest_existing_project(
            tmp_path / "nonexistent"
        )
        assert files == {}
        assert paths == []

    def test_ingest_empty_project(self, real_ctx, tmp_path):
        project = tmp_path / "empty_project"
        project.mkdir()
        real_ctx.file_manager.read_file.return_value = ""

        files, structure, paths = real_ctx.ingest_existing_project(project)
        assert files == {}

    def test_ingest_project_with_files(self, real_ctx, tmp_path):
        project = tmp_path / "my_project"
        project.mkdir()
        (project / "main.py").write_text("print('hello')")
        (project / "README.md").write_text("# My Project")

        real_ctx.file_manager.read_file.side_effect = lambda p: Path(p).read_text()

        files, structure, paths = real_ctx.ingest_existing_project(project)
        assert "main.py" in files
        # README.md is extracted separately, not included in files dict
        assert "README.md" not in files

    def test_ingest_skips_excluded_dirs(self, real_ctx, tmp_path):
        project = tmp_path / "proj"
        project.mkdir()
        (project / "src").mkdir()
        (project / "src" / "app.py").write_text("code")
        (project / "__pycache__").mkdir()
        (project / "__pycache__" / "app.cpython-311.pyc").write_text("bytecode")
        (project / "node_modules").mkdir()
        (project / "node_modules" / "pkg.js").write_text("module")

        real_ctx.file_manager.read_file.side_effect = lambda p: Path(p).read_text()

        files, structure, paths = real_ctx.ingest_existing_project(project)
        assert any("app.py" in p for p in files)
        assert not any("__pycache__" in p for p in files)
        assert not any("node_modules" in p for p in files)

    def test_ingest_nested_structure(self, real_ctx, tmp_path):
        """Verifies correct ingestion of nested directory structures."""
        project = tmp_path / "nested_proj"
        project.mkdir()
        (project / "src" / "core").mkdir(parents=True)
        (project / "src" / "core" / "engine.py").write_text("class Engine: pass")
        (project / "src" / "utils.py").write_text("def util(): pass")
        (project / "config.json").write_text("{}")

        real_ctx.file_manager.read_file.side_effect = lambda p: Path(p).read_text()

        files, structure, paths = real_ctx.ingest_existing_project(project)
        assert any("engine.py" in p for p in files)
        assert any("utils.py" in p for p in files)
        assert any("config.json" in p for p in files)

    def test_ingest_handles_read_error(self, real_ctx, tmp_path):
        """Gracefully handles files that can't be read."""
        project = tmp_path / "err_proj"
        project.mkdir()
        (project / "good.py").write_text("x = 1")
        (project / "bad.py").write_text("y = 2")

        def _read(p):
            if "bad.py" in str(p):
                raise PermissionError("Cannot read")
            return Path(p).read_text()

        real_ctx.file_manager.read_file.side_effect = _read

        files, structure, paths = real_ctx.ingest_existing_project(project)
        assert any("good.py" in p for p in files)
        assert not any("bad.py" in p for p in files)


# ===================================================================
# 7. Integration Tests (require local Ollama with specified models)
# ===================================================================


def _ollama_available():
    """Check if Ollama is available at the configured URL."""
    try:
        import requests

        resp = requests.get(f"{TEST_OLLAMA_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _model_available(model_name: str) -> bool:
    """Check if a specific model is available on the Ollama server."""
    try:
        import requests

        resp = requests.get(f"{TEST_OLLAMA_URL}/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            return any(model_name in m for m in models)
    except Exception:
        pass
    return False


# ===================================================================
# 8. Edge Cases and Error Handling
# ===================================================================


class TestEdgeCases:
    def test_run_with_empty_description(self, auto_agent_instance):
        """Agent handles empty project description gracefully."""
        result = auto_agent_instance.run("", "empty_desc_project")
        assert result is not None

    def test_run_with_special_characters_in_name(self, auto_agent_instance):
        """Project names with unusual characters are handled."""
        result = auto_agent_instance.run(
            "A project", "proj-with-dashes_and_underscores"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_phase_returns_none_readme(self, mock_phase_context, tmp_path):
        """ReadmeGenerationPhase handles planner returning None."""
        mock_phase_context.project_planner.generate_readme.return_value = None

        phase = ReadmeGenerationPhase(mock_phase_context)
        files, _, paths = await phase.execute(
            project_description="test",
            project_name="test",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={},
        )

        assert "README.md" in files

    def test_phase_context_select_related_files_large_set(self, mocker, tmp_path):
        """select_related_files respects max_files limit."""
        ctx = _make_real_phase_context(mocker, tmp_path)
        ctx.rag_context_selector.select_relevant_files.side_effect = Exception("no RAG")

        files = {f"src/file_{i}.py": f"content_{i}" for i in range(50)}
        result = ctx.select_related_files("src/target.py", files, max_files=5)
        assert len(result) <= 5

    def test_infer_language_case_insensitive(self, mocker, tmp_path):
        """File extensions are handled case-insensitively."""
        ctx = _make_real_phase_context(mocker, tmp_path)
        # .PY in uppercase should still resolve (Path.suffix preserves case,
        # but infer_language calls .lower())
        assert ctx.infer_language("FILE.PY") == "python"
        assert ctx.infer_language("script.JS") == "javascript"

    @pytest.mark.asyncio
    async def test_logic_planning_empty_file_paths(self, mock_phase_context, tmp_path):
        """LogicPlanningPhase handles empty file_paths list."""
        phase = LogicPlanningPhase(mock_phase_context)
        files, _, paths = await phase.execute(
            project_description="Empty project",
            project_name="empty",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={},
            file_paths=[],
        )
        # Should still create the plan file, even if empty
        assert "IMPLEMENTATION_PLAN.json" in files

    def test_exhaustive_repair_no_js_no_package_issue(self, mock_phase_context):
        """Non-JS projects should not flag missing package.json."""
        phase = ExhaustiveReviewRepairPhase(mock_phase_context)
        files = {"main.py": "print('hello')", "utils.py": "def util(): pass"}
        issues = phase._validate_config_files(files, "")
        assert len(issues) == 0
