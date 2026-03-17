"""Unit tests for BlueprintPhase."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.blueprint_phase import BlueprintPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


def _make_ctx(model_name: str = "qwen3.5:4b") -> PhaseContext:
    mock_client = MagicMock()
    mock_client.model = model_name
    mock_llm = MagicMock()
    mock_llm.get_client.return_value = mock_client
    return PhaseContext(
        project_name="TestProject",
        project_description="A Python FastAPI REST API",
        project_root=Path("/tmp/test"),
        llm_manager=mock_llm,
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )


_VALID_BLUEPRINT = {
    "project_type": "api",
    "tech_stack": ["python", "fastapi"],
    "files": [
        {
            "path": "models.py",
            "purpose": "SQLAlchemy models",
            "exports": ["User"],
            "imports": [],
            "key_logic": "User model",
            "priority": 1,
        },
        {
            "path": "main.py",
            "purpose": "FastAPI entry",
            "exports": ["app"],
            "imports": ["models.py"],
            "key_logic": "App creation",
            "priority": 2,
        },
    ],
}


def _mock_llm_response(ctx: PhaseContext, json_data: dict) -> None:
    """Configure llm_manager to return json_data as LLM response."""
    response_obj = {"message": {"content": json.dumps(json_data)}, "prompt_eval_count": 100, "eval_count": 200}
    ctx.llm_manager.get_client.return_value.chat.return_value = (response_obj, None)


@pytest.mark.unit
class TestBlueprintPhase:
    def test_valid_blueprint_populates_ctx(self):
        ctx = _make_ctx()
        _mock_llm_response(ctx, _VALID_BLUEPRINT)
        BlueprintPhase().run(ctx)
        assert len(ctx.blueprint) == 2
        assert ctx.project_type == "api"
        assert "python" in ctx.tech_stack

    def test_blueprint_sorted_by_priority(self):
        ctx = _make_ctx()
        blueprint = dict(_VALID_BLUEPRINT)
        blueprint["files"] = [
            {"path": "main.py", "purpose": "entry", "priority": 3},
            {"path": "models.py", "purpose": "models", "priority": 1},
            {"path": "routes.py", "purpose": "routes", "priority": 2},
        ]
        _mock_llm_response(ctx, blueprint)
        BlueprintPhase().run(ctx)
        priorities = [fp.priority for fp in ctx.blueprint]
        assert priorities == sorted(priorities)

    def test_ctx_project_type_updated_from_blueprint(self):
        ctx = _make_ctx()
        ctx.project_type = "unknown"
        _mock_llm_response(ctx, _VALID_BLUEPRINT)
        BlueprintPhase().run(ctx)
        assert ctx.project_type == "api"

    def test_retries_on_invalid_json(self):
        ctx = _make_ctx()
        # First call returns invalid JSON, second returns valid
        valid_json = json.dumps(_VALID_BLUEPRINT)
        invalid_response = {"message": {"content": "not json at all"}, "prompt_eval_count": 10, "eval_count": 10}
        valid_response = {"message": {"content": valid_json}, "prompt_eval_count": 100, "eval_count": 200}
        ctx.llm_manager.get_client.return_value.chat.side_effect = [
            (invalid_response, None),
            (valid_response, None),
        ]
        BlueprintPhase().run(ctx)
        assert len(ctx.blueprint) == 2

    def test_max_20_files_rejected(self):
        ctx = _make_ctx()
        blueprint = {
            "project_type": "api",
            "tech_stack": ["python"],
            "files": [{"path": f"file{i}.py", "purpose": "test", "priority": 1} for i in range(21)],
        }
        response = {"message": {"content": json.dumps(blueprint)}, "prompt_eval_count": 10, "eval_count": 10}
        ctx.llm_manager.get_client.return_value.chat.return_value = (response, None)
        from backend.utils.core.exceptions import PipelinePhaseError

        with pytest.raises(PipelinePhaseError):
            BlueprintPhase().run(ctx)

    def test_event_published_on_success(self):
        ctx = _make_ctx()
        _mock_llm_response(ctx, _VALID_BLUEPRINT)
        BlueprintPhase().run(ctx)
        ctx.event_publisher.publish_sync.assert_called_with(
            "blueprint_ready",
            files=pytest.approx(
                [
                    {"path": "models.py", "purpose": "SQLAlchemy models"},
                    {"path": "main.py", "purpose": "FastAPI entry"},
                ],
                abs=1e-3,
            ),
            project_type="api",
            tech_stack=["python", "fastapi"],
        )


# ----------------------------------------------------------------
# M2 — _dynamic_max_files: python_app / api → 7 files on small models
# ----------------------------------------------------------------


@pytest.mark.unit
def test_dynamic_max_files_api_returns_7_for_small_model():
    """M2: project_type='api' on a small model (≤8B) should return 7."""
    ctx = _make_ctx(model_name="qwen3.5:4b")
    ctx.project_type = "api"
    result = BlueprintPhase._dynamic_max_files(ctx)
    assert result == 7


@pytest.mark.unit
def test_dynamic_max_files_python_app_returns_7_for_small_model():
    """M2: project_type='python_app' on a small model should return 7."""
    ctx = _make_ctx(model_name="qwen3.5:4b")
    ctx.project_type = "python_app"
    result = BlueprintPhase._dynamic_max_files(ctx)
    assert result == 7


@pytest.mark.unit
def test_dynamic_max_files_web_app_returns_7_for_small_model():
    """M2: project_type='web_app' on a small model should return 7."""
    ctx = _make_ctx(model_name="qwen3.5:4b")
    ctx.project_type = "web_app"
    result = BlueprintPhase._dynamic_max_files(ctx)
    assert result == 7


@pytest.mark.unit
def test_dynamic_max_files_cli_still_5():
    """M2: CLI projects on small model still return 5 (not in multi_file_types)."""
    ctx = _make_ctx(model_name="qwen3.5:4b")
    ctx.project_type = "cli"
    result = BlueprintPhase._dynamic_max_files(ctx)
    assert result == 5


# ----------------------------------------------------------------
# M3 — _ensure_mandatory_files: auto-adds static/style.css
# ----------------------------------------------------------------


@pytest.mark.unit
def test_ensure_mandatory_files_adds_css():
    """M3: CSS in stack + HTML in blueprint + no CSS planned → auto-add style.css."""
    from backend.agents.auto_agent_phases.phase_context import FilePlan

    ctx = _make_ctx()
    ctx.tech_stack = ["python", "fastapi", "html", "css"]
    ctx.blueprint = [
        FilePlan(path="index.html", purpose="Main page", exports=[], imports=[], key_logic="", priority=2),
    ]
    BlueprintPhase._ensure_mandatory_files(ctx)
    paths = [fp.path for fp in ctx.blueprint]
    assert "static/style.css" in paths


@pytest.mark.unit
def test_ensure_mandatory_files_no_duplicate():
    """M3: CSS already planned → _ensure_mandatory_files must not add a second one."""
    from backend.agents.auto_agent_phases.phase_context import FilePlan

    ctx = _make_ctx()
    ctx.tech_stack = ["html", "css"]
    ctx.blueprint = [
        FilePlan(path="index.html", purpose="Main", exports=[], imports=[], key_logic="", priority=2),
        FilePlan(path="static/style.css", purpose="Styles", exports=[], imports=[], key_logic="", priority=1),
    ]
    BlueprintPhase._ensure_mandatory_files(ctx)
    css_files = [fp for fp in ctx.blueprint if fp.path.endswith(".css")]
    assert len(css_files) == 1, "Should not add duplicate CSS"


@pytest.mark.unit
def test_ensure_mandatory_files_no_css_if_no_html():
    """M3: CSS in stack but no HTML → do NOT add CSS (no HTML to reference it)."""
    from backend.agents.auto_agent_phases.phase_context import FilePlan

    ctx = _make_ctx()
    ctx.tech_stack = ["python", "css"]
    ctx.blueprint = [
        FilePlan(path="app.py", purpose="Entry", exports=[], imports=[], key_logic="", priority=1),
    ]
    BlueprintPhase._ensure_mandatory_files(ctx)
    css_files = [fp for fp in ctx.blueprint if fp.path.endswith(".css")]
    assert len(css_files) == 0


# ----------------------------------------------------------------
# M4 — _build_mandatory_hints
# ----------------------------------------------------------------


@pytest.mark.unit
def test_build_mandatory_hints_fastapi_html():
    """M4: FastAPI + HTML in large model → hints include StaticFiles + startup."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.tech_stack = ["python", "fastapi", "sqlite", "html"]
    ctx.project_type = "python_app"
    hints = BlueprintPhase._build_mandatory_hints(ctx)
    assert "StaticFiles" in hints
    assert "startup" in hints


@pytest.mark.unit
def test_build_mandatory_hints_empty_for_small():
    """M4: Small model → no hints (budget constraint)."""
    ctx = _make_ctx(model_name="qwen3.5:4b")
    ctx.tech_stack = ["python", "fastapi", "sqlite", "html"]
    ctx.project_type = "python_app"
    hints = BlueprintPhase._build_mandatory_hints(ctx)
    assert hints == ""


@pytest.mark.unit
def test_build_mandatory_hints_empty_without_fastapi():
    """M4: Large model but no FastAPI in stack → no hints."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.tech_stack = ["python", "flask", "html"]
    ctx.project_type = "python_app"
    hints = BlueprintPhase._build_mandatory_hints(ctx)
    assert hints == ""


# ----------------------------------------------------------------
# Fix 2 — _enforce_described_files auto-injection
# ----------------------------------------------------------------


@pytest.mark.unit
def test_enforce_described_files_injects_missing():
    """Files named in description but absent from blueprint are auto-injected."""
    from backend.agents.auto_agent_phases.phase_context import FilePlan

    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.project_description = "Must have Services/ContactoService.cs and Models/Lead.cs"
    ctx.blueprint = [
        FilePlan(path="Program.cs", purpose="entry", exports=[], imports=[], key_logic="", priority=1),
    ]
    BlueprintPhase._enforce_described_files(ctx)

    paths = [fp.path for fp in ctx.blueprint]
    assert "Services/ContactoService.cs" in paths
    assert "Models/Lead.cs" in paths


@pytest.mark.unit
def test_enforce_described_files_no_false_positives_for_planned_files():
    """Files already in blueprint are NOT re-injected."""
    from backend.agents.auto_agent_phases.phase_context import FilePlan

    ctx = _make_ctx()
    ctx.project_description = "Include Program.cs as the entry point"
    ctx.blueprint = [
        FilePlan(path="Program.cs", purpose="entry", exports=[], imports=[], key_logic="", priority=1),
    ]
    original_len = len(ctx.blueprint)
    BlueprintPhase._enforce_described_files(ctx)
    assert len(ctx.blueprint) == original_len


@pytest.mark.unit
def test_enforce_described_files_cap_for_small_model():
    """Small model (≤8B): at most 3 files are injected even if more are missing."""
    ctx = _make_ctx(model_name="qwen3.5:4b")
    ctx.project_description = "Files: a/a.cs b/b.cs c/c.cs d/d.cs e/e.cs f/f.cs"
    ctx.blueprint = []
    BlueprintPhase._enforce_described_files(ctx)

    injected = [fp for fp in ctx.blueprint]
    assert len(injected) <= 3


@pytest.mark.unit
def test_enforce_described_files_no_cap_for_large_model():
    """Large model (>8B): all missing files are injected."""
    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.project_description = "Files: a/a.cs b/b.cs c/c.cs d/d.cs e/e.cs"
    ctx.blueprint = []
    BlueprintPhase._enforce_described_files(ctx)

    assert len(ctx.blueprint) == 5


@pytest.mark.unit
def test_enforce_described_files_priority_after_existing():
    """Injected files get priority > max existing priority."""
    from backend.agents.auto_agent_phases.phase_context import FilePlan

    ctx = _make_ctx(model_name="qwen3-coder:30b")
    ctx.project_description = "Include Services/MyService.cs"
    ctx.blueprint = [
        FilePlan(path="Program.cs", purpose="entry", exports=[], imports=[], key_logic="", priority=5),
    ]
    BlueprintPhase._enforce_described_files(ctx)

    injected = next(fp for fp in ctx.blueprint if "MyService" in fp.path)
    assert injected.priority > 5
