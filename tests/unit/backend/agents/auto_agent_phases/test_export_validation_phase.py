"""Unit tests for ExportValidationPhase (Sprint 19 — phase 4c)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.auto_agent_phases.export_validation_phase import ExportValidationPhase
from backend.agents.auto_agent_phases.phase_context import FilePlan, PhaseContext


def _make_ctx(model_name: str = "qwen3-coder:30b") -> PhaseContext:
    mock_client = MagicMock()
    mock_client.model = model_name
    mock_llm = MagicMock()
    mock_llm.get_client.return_value = mock_client
    return PhaseContext(
        project_name="TestProject",
        project_description="A chess game",
        project_root=Path("/tmp/test_export_val"),
        llm_manager=mock_llm,
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )


def _plan(path: str, exports=None) -> FilePlan:
    return FilePlan(
        path=path,
        purpose=f"Test {path}",
        exports=exports or [],
        imports=[],
        key_logic="test logic",
        priority=1,
    )


# ----------------------------------------------------------------
# Skip logic for config/doc files
# ----------------------------------------------------------------


@pytest.mark.unit
def test_skip_json_files():
    """.json files are not checked for exports."""
    ctx = _make_ctx()
    ctx.blueprint = [_plan("package.json", exports=["initGame"])]
    ctx.generated_files = {"package.json": '{"name": "test"}'}  # no initGame — but should be skipped
    ExportValidationPhase().run(ctx)
    assert ctx.metrics["export_validation"]["missing"] == []


@pytest.mark.unit
def test_skip_yaml_files():
    """.yaml files are not checked for exports."""
    ctx = _make_ctx()
    ctx.blueprint = [_plan("config.yaml", exports=["setupDB"])]
    ctx.generated_files = {"config.yaml": "db: sqlite"}
    ExportValidationPhase().run(ctx)
    assert ctx.metrics["export_validation"]["missing"] == []


@pytest.mark.unit
def test_skip_md_files():
    """README.md is not checked for exports."""
    ctx = _make_ctx()
    ctx.blueprint = [_plan("README.md", exports=["install"])]
    ctx.generated_files = {"README.md": "# My project"}
    ExportValidationPhase().run(ctx)
    assert ctx.metrics["export_validation"]["missing"] == []


# ----------------------------------------------------------------
# Happy path — all exports present
# ----------------------------------------------------------------


@pytest.mark.unit
def test_no_missing_exports():
    """All declared exports exist → missing list is empty."""
    ctx = _make_ctx()
    ctx.blueprint = [_plan("game.js", exports=["initGame", "startRound"])]
    ctx.generated_files = {"game.js": "function initGame() {}\nfunction startRound() {}"}
    ExportValidationPhase().run(ctx)
    result = ctx.metrics["export_validation"]
    assert result["missing"] == []
    assert result["repaired"] == 0


# ----------------------------------------------------------------
# Missing exports detected
# ----------------------------------------------------------------


@pytest.mark.unit
def test_detects_missing_export():
    """An export in blueprint but absent from file content is listed as missing."""
    ctx = _make_ctx()
    ctx.blueprint = [_plan("game.js", exports=["initGame", "calculatePot"])]
    ctx.generated_files = {"game.js": "function initGame() { return 1; }"}
    ExportValidationPhase().run(ctx)
    result = ctx.metrics["export_validation"]
    assert any("calculatePot" in m for m in result["missing"])


# ----------------------------------------------------------------
# Small-model path: writes to cross_file_errors
# ----------------------------------------------------------------


@pytest.mark.unit
def test_small_model_writes_cross_file_errors():
    """Small models (≤8B) write missing exports to cross_file_errors instead of injecting."""
    ctx = _make_ctx(model_name="qwen3.5:4b")
    ctx.blueprint = [_plan("ai.js", exports=["makeMove"])]
    ctx.generated_files = {"ai.js": "function placeholder() {}"}
    with patch(
        "backend.agents.auto_agent_phases.export_validation_phase.ExportValidationPhase._inject_missing_exports"
    ) as mock_inject:
        ExportValidationPhase().run(ctx)
    assert any(e["error_type"] == "missing_export" for e in ctx.cross_file_errors)
    # Small models should NOT call _inject_missing_exports (they write to cross_file_errors instead)
    mock_inject.assert_not_called()


# ----------------------------------------------------------------
# Large-model path: calls CodePatcher.inject_missing_function
# ----------------------------------------------------------------


@pytest.mark.unit
def test_large_model_calls_inject_missing_function():
    """Large models call CodePatcher.inject_missing_function for missing exports."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.blueprint = [_plan("ui.js", exports=["renderCards"])]
    ctx.generated_files = {"ui.js": "function placeholder() {}"}

    with patch(
        "backend.agents.auto_agent_phases.export_validation_phase.ExportValidationPhase._inject_missing_exports"
    ) as mock_inject:
        mock_inject.return_value = 1
        ExportValidationPhase().run(ctx)
        mock_inject.assert_called_once()


@pytest.mark.unit
def test_injection_updates_generated_files():
    """When injection succeeds and returns content with the name, _write_file is called."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.blueprint = [_plan("ui.js", exports=["renderCards"])]
    original = "function placeholder() {}"
    injected = "function placeholder() {}\nfunction renderCards() { return []; }"
    ctx.generated_files = {"ui.js": original}

    with patch("backend.utils.domains.auto_generation.utilities.code_patcher.CodePatcher") as MockPatcher:
        patcher_instance = MockPatcher.return_value
        patcher_instance.inject_missing_function.return_value = injected

        write_calls = []
        phase = ExportValidationPhase()
        phase._write_file = lambda ctx, path, content: write_calls.append((path, content))
        phase._run_export_validation(ctx)

    assert any("ui.js" in path for path, _ in write_calls)


@pytest.mark.unit
def test_injection_rejected_when_name_missing():
    """If injected content doesn't contain the target name, no write happens; error goes to cross_file_errors."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.blueprint = [_plan("ui.js", exports=["renderCards"])]
    ctx.generated_files = {"ui.js": "function placeholder() {}"}

    with patch("backend.utils.domains.auto_generation.utilities.code_patcher.CodePatcher") as MockPatcher:
        patcher_instance = MockPatcher.return_value
        # Injection returns content WITHOUT the target symbol
        patcher_instance.inject_missing_function.return_value = "function placeholder() {}\nfunction other() {}"

        write_calls = []
        phase = ExportValidationPhase()
        phase._write_file = lambda ctx, path, content: write_calls.append((path, content))
        phase._run_export_validation(ctx)

    # No write should have happened
    assert write_calls == []
    # Error should be pushed to cross_file_errors
    assert any(e["error_type"] == "missing_export" for e in ctx.cross_file_errors)


# ----------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------


@pytest.mark.unit
def test_metrics_recorded():
    """ctx.metrics['export_validation'] always has checked, missing, repaired keys."""
    ctx = _make_ctx()
    ctx.blueprint = [_plan("app.py", exports=["main"])]
    ctx.generated_files = {"app.py": "def main(): pass"}
    ExportValidationPhase().run(ctx)
    m = ctx.metrics["export_validation"]
    assert "checked" in m
    assert "missing" in m
    assert "repaired" in m


# ----------------------------------------------------------------
# Non-fatal on exception
# ----------------------------------------------------------------


@pytest.mark.unit
def test_non_fatal_on_exception():
    """If CodePatcher raises an exception the phase completes without raising."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.blueprint = [_plan("ui.js", exports=["renderCards"])]
    ctx.generated_files = {"ui.js": "function placeholder() {}"}

    with patch(
        "backend.utils.domains.auto_generation.utilities.code_patcher.CodePatcher",
        side_effect=RuntimeError("CodePatcher boom"),
    ):
        # Should not raise
        ExportValidationPhase().run(ctx)
