import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.agents.auto_agent_phases.file_content_generation_phase import FileContentGenerationPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=PhaseContext)
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.event_publisher.publish = AsyncMock()
    ctx.dependency_graph = MagicMock()
    ctx.parallel_generator = MagicMock()
    ctx.error_knowledge_base = MagicMock()
    ctx.file_manager = MagicMock()
    ctx.llm_manager = MagicMock()
    ctx.response_parser = MagicMock()
    ctx.file_content_generator = MagicMock()
    ctx.config = {}

    # Default project type info to avoid extension guard skipping files
    from backend.utils.domains.auto_generation.utilities.project_type_detector import ProjectTypeInfo

    ctx.project_type_info = ProjectTypeInfo(
        project_type="python_app", allowed_extensions=frozenset([".py"]), detected_keywords=[], confidence=0.9
    )

    def _mock_infer(fp):
        if fp.endswith(".py"):
            return "python"
        if fp.endswith(".js"):
            return "javascript"
        return "unknown"

    ctx.infer_language.side_effect = _mock_infer

    # Files sub-context
    ctx.files_ctx = MagicMock()
    ctx.files_ctx.validator = MagicMock()
    ctx.files_ctx.validator.validate.return_value = MagicMock(status=MagicMock(name="VALID"))

    return ctx


class TestFileContentGenerationPhase:
    """Test suite for Phase 4: File Content Generation."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_context, tmp_path):
        phase = FileContentGenerationPhase(mock_context)

        # Setup Mock Backlog
        mock_context.backlog = [{"id": "T1", "title": "Task 1", "file_path": "main.py", "task_type": "create_file"}]
        mock_context.select_related_files.return_value = {}

        # Mock LLM Client (phase now uses achat for parallel-safe async calls)
        mock_client = MagicMock()
        mock_client.achat = AsyncMock(return_value=(
            {"content": "<thinking_process>Análisis</thinking_process><code_created>def main(): pass</code_created>"},
            {"prompt_tokens": 10, "completion_tokens": 10},
        ))
        mock_context.llm_manager.get_client.return_value = mock_client

        # Mock Validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(status=MagicMock(name="VALID"))
        mock_context.files_ctx.validator = mock_validator

        generated_files = {}
        result_files, result_struct, result_paths = await phase.execute(
            project_description="desc",
            project_name="name",
            project_root=tmp_path,
            readme_content="# Readme",
            initial_structure={},
            generated_files=generated_files,
            file_paths=["main.py"],
        )

        assert "main.py" in result_files
        assert "def main(): pass" in result_files["main.py"]
        mock_context.file_manager.write_file.assert_called()

    def test_validate_file_content(self, mock_context):
        phase = FileContentGenerationPhase(mock_context)
        plan = {"exports": ["calculate"]}

        # Valid content (long enough and contains export)
        valid_content = "def calculate():\n    return 42\n" + "#" * 60
        assert phase._validate_file_content("test.py", valid_content, plan) is True

        # Missing export
        invalid_export = "def wrong():\n    pass\n" + "#" * 60
        assert phase._validate_file_content("test.py", invalid_export, plan) is False

        # Content too short for main file (threshold is 20)
        short_main_content = "def main(): pass"  # 16 chars
        assert phase._validate_file_content("main.py", short_main_content, plan) is False

        # Valid main content
        good_main_content = "def main():\n    print('Hello World')\n" + "#" * 20
        assert phase._validate_file_content("main.py", good_main_content, plan) is True

    def test_infer_language(self, mock_context):
        phase = FileContentGenerationPhase(mock_context)
        assert phase._infer_language("main.py") == "python"
        assert phase._infer_language("app.js") == "javascript"
        assert phase._infer_language("main.go") == "go"
        assert phase._infer_language("unknown.xyz") == "unknown"

    # ------------------------------------------------------------------
    # _compute_levels
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_compute_levels_independent_tasks(self, mock_context):
        """Tasks with no declared dependencies all land in a single level-0 batch."""
        phase = FileContentGenerationPhase(mock_context)
        tasks = [
            {"id": "T1", "dependencies": []},
            {"id": "T2", "dependencies": []},
            {"id": "T3", "dependencies": []},
        ]
        levels = phase._compute_levels(tasks)
        assert len(levels) == 1
        assert len(levels[0]) == 3

    @pytest.mark.unit
    def test_compute_levels_chain_dependency(self, mock_context):
        """T1 → T2 → T3 produces three levels, one task each."""
        phase = FileContentGenerationPhase(mock_context)
        tasks = [
            {"id": "T1", "dependencies": []},
            {"id": "T2", "dependencies": ["T1"]},
            {"id": "T3", "dependencies": ["T2"]},
        ]
        levels = phase._compute_levels(tasks)
        assert len(levels) == 3
        assert levels[0][0]["id"] == "T1"
        assert levels[1][0]["id"] == "T2"
        assert levels[2][0]["id"] == "T3"

    @pytest.mark.unit
    def test_compute_levels_mixed(self, mock_context):
        """T1 and T2 independent; T3 depends on T1; T4 depends on T2 and T3."""
        phase = FileContentGenerationPhase(mock_context)
        tasks = [
            {"id": "T1", "dependencies": []},
            {"id": "T2", "dependencies": []},
            {"id": "T3", "dependencies": ["T1"]},
            {"id": "T4", "dependencies": ["T2", "T3"]},
        ]
        levels = phase._compute_levels(tasks)
        # Level 0: T1, T2 (both independent)
        assert len(levels[0]) == 2
        assert {t["id"] for t in levels[0]} == {"T1", "T2"}
        # Level 1: T3 (depends on T1 which is done)
        assert len(levels[1]) == 1
        assert levels[1][0]["id"] == "T3"
        # Level 2: T4 (depends on T2 and T3, both done)
        assert len(levels[2]) == 1
        assert levels[2][0]["id"] == "T4"
