"""Unit tests for ComponentTreePhase."""

import json
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.component_tree_phase import ComponentTreePhase

_SAMPLE_TREE = {
    "components": [
        {"name": "App", "parent": None, "props": [], "state": ["user"], "responsibility": "Root"},
        {"name": "Header", "parent": "App", "props": ["title"], "state": [], "responsibility": "Navigation"},
        {"name": "Footer", "parent": "App", "props": [], "state": [], "responsibility": "Links"},
    ],
    "state_management": {
        "type": "Context",
        "stores": [{"name": "AuthContext", "state_keys": ["user", "token"]}],
    },
}


@pytest.mark.unit
class TestComponentTreePhase:
    def _make_context(self, framework="react"):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.component_tree = None
        ctx.file_manager = MagicMock()
        ctx.module_system = "esm"

        tech = MagicMock()
        tech.framework = framework
        ctx.tech_stack_info = tech

        ptype = MagicMock()
        ptype.project_type = "frontend"
        ctx.project_type_info = ptype

        ctx.llm_manager.get_client.return_value.chat.return_value = (
            {"content": json.dumps(_SAMPLE_TREE)},
            {},
        )
        ctx.response_parser.extract_json.side_effect = json.loads
        return ctx

    @pytest.mark.asyncio
    async def test_generates_for_react_project(self, tmp_path):
        ctx = self._make_context(framework="react")
        phase = ComponentTreePhase(ctx)
        gf, _, fps = await phase.run("React SPA", "myapp", tmp_path, "", {}, {}, ["src/App.tsx", "src/Header.tsx"])
        assert "component_tree.md" in gf
        assert "Component Tree" in gf["component_tree.md"]
        assert ctx.component_tree is not None

    @pytest.mark.asyncio
    async def test_skips_non_frontend_project(self, tmp_path):
        ctx = self._make_context(framework="django")
        # Override project type to backend
        ctx.project_type_info.project_type = "backend"
        phase = ComponentTreePhase(ctx)
        gf, _, _ = await phase.run("Django API", "api", tmp_path, "", {}, {}, [])
        assert "component_tree.md" not in gf
        assert ctx.component_tree is None

    def test_render_markdown_contains_all_components(self):
        md = ComponentTreePhase._render_markdown(_SAMPLE_TREE, "MyApp", "react")
        assert "App" in md
        assert "Header" in md
        assert "Footer" in md
        assert "AuthContext" in md

    def test_render_markdown_state_management_section(self):
        md = ComponentTreePhase._render_markdown(_SAMPLE_TREE, "MyApp", "vue")
        assert "State Management" in md
        assert "Context" in md
        assert "user" in md

    @pytest.mark.asyncio
    async def test_llm_failure_returns_unchanged(self, tmp_path):
        ctx = self._make_context(framework="react")
        ctx.llm_manager.get_client.return_value.chat.side_effect = RuntimeError("LLM down")
        ctx.response_parser.extract_json.side_effect = RuntimeError("parse failed")
        phase = ComponentTreePhase(ctx)
        gf, _, _ = await phase.run("React app", "app", tmp_path, "", {}, {}, ["src/App.tsx"])
        assert "component_tree.md" not in gf
