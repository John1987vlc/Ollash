"""Unit tests for PhaseContext (v2 — new 8-phase dataclass)."""
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.blueprint_models import BlueprintOutput, FilePlanModel
from backend.agents.auto_agent_phases.phase_context import PhaseContext


def _make_ctx(model_name: str = "qwen3.5:4b") -> PhaseContext:
    mock_client = MagicMock()
    mock_client.model = model_name
    mock_llm = MagicMock()
    mock_llm.get_client.return_value = mock_client
    return PhaseContext(
        project_name="TestProject",
        project_description="A test project",
        project_root=Path("/tmp/test_project"),
        llm_manager=mock_llm,
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )


@pytest.mark.unit
class TestPhaseContextModelSize:
    def test_is_small_with_4b_model(self):
        ctx = _make_ctx("qwen3.5:4b")
        assert ctx.is_small() is True

    def test_is_small_with_7b_model(self):
        ctx = _make_ctx("llama3:7b")
        assert ctx.is_small() is True

    def test_is_small_with_8b_model(self):
        ctx = _make_ctx("custom-coder:8b")
        assert ctx.is_small() is True

    def test_is_small_returns_false_for_9b(self):
        ctx = _make_ctx("deepseek-coder:9b")
        assert ctx.is_small() is False

    def test_is_small_returns_false_for_30b(self):
        ctx = _make_ctx("qwen3-coder:30b")
        assert ctx.is_small() is False

    def test_is_micro_with_0_8b(self):
        ctx = _make_ctx("qwen3.5:0.8b")
        assert ctx.is_micro() is True

    def test_is_micro_returns_false_for_4b(self):
        ctx = _make_ctx("qwen3.5:4b")
        assert ctx.is_micro() is False

    def test_unknown_model_returns_large(self):
        ctx = _make_ctx("unknown-model-no-size")
        assert ctx.is_small() is False  # 999.0 > 8.0

    def test_get_client_exception_returns_large(self):
        ctx = _make_ctx()
        ctx.llm_manager.get_client.side_effect = Exception("no client")
        assert ctx.is_small() is False


@pytest.mark.unit
class TestPhaseContextMetrics:
    def test_record_tokens_accumulates(self):
        ctx = _make_ctx()
        ctx.record_tokens("4", 100, 50)
        ctx.record_tokens("4", 200, 80)
        usage = ctx.metrics["token_usage"]["4"]
        assert usage["prompt"] == 300
        assert usage["completion"] == 130

    def test_total_tokens_sums_all_phases(self):
        ctx = _make_ctx()
        ctx.record_tokens("1", 100, 20)
        ctx.record_tokens("2", 500, 200)
        ctx.record_tokens("4", 1000, 400)
        assert ctx.total_tokens() == 2220

    def test_total_tokens_zero_initially(self):
        ctx = _make_ctx()
        assert ctx.total_tokens() == 0

    def test_phase_timer(self):
        ctx = _make_ctx()
        ctx.start_phase_timer("4")
        time.sleep(0.01)
        elapsed = ctx.end_phase_timer("4")
        assert elapsed >= 0.005  # at least 5ms
        assert ctx.metrics["phase_timings"]["4"] >= 0.005

    def test_multiple_phases_tracked(self):
        ctx = _make_ctx()
        ctx.start_phase_timer("1")
        ctx.end_phase_timer("1")
        ctx.start_phase_timer("2")
        ctx.end_phase_timer("2")
        assert "1" in ctx.metrics["phase_timings"]
        assert "2" in ctx.metrics["phase_timings"]


@pytest.mark.unit
class TestFilePlanModel:
    def test_valid_file_plan_parses(self):
        data = {
            "path": "src/main.py",
            "purpose": "Entry point",
            "exports": ["main"],
            "imports": [],
            "key_logic": "Calls core logic",
            "priority": 1,
        }
        model = FilePlanModel.model_validate(data)
        assert model.path == "src/main.py"
        assert model.priority == 1

    def test_priority_default_is_10(self):
        model = FilePlanModel.model_validate({"path": "x.py", "purpose": "test"})
        assert model.priority == 10

    def test_priority_out_of_range_fails(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FilePlanModel.model_validate({"path": "x.py", "purpose": "test", "priority": 25})


@pytest.mark.unit
class TestBlueprintOutput:
    def test_max_20_files_enforced(self):
        from pydantic import ValidationError
        files = [{"path": f"file{i}.py", "purpose": "test"} for i in range(21)]
        with pytest.raises(ValidationError):
            BlueprintOutput.model_validate({
                "project_type": "cli",
                "tech_stack": ["python"],
                "files": files,
            })

    def test_valid_blueprint_parses(self):
        data = {
            "project_type": "api",
            "tech_stack": ["python", "fastapi"],
            "files": [
                {"path": "main.py", "purpose": "entry", "priority": 1},
                {"path": "models.py", "purpose": "models", "priority": 1},
            ],
        }
        bp = BlueprintOutput.model_validate(data)
        assert bp.project_type == "api"
        assert len(bp.files) == 2
