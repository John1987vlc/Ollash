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
