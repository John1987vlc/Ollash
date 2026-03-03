"""Unit tests for DependencyPrecheckPhase."""
import json
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.dependency_precheck_phase import DependencyPrecheckPhase


@pytest.mark.unit
class TestDependencyPrecheckPhase:
    def _make_context(self, conflicts=None):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.logic_plan = {
            "app/main.py": {"imports": ["flask", "sqlalchemy"]},
        }
        ctx.file_manager = MagicMock()

        tech = MagicMock()
        tech.primary_language = "python"
        tech.runtime_version = "3.12"
        tech.framework = "flask"
        ctx.tech_stack_info = tech

        issues = conflicts or []
        resp = json.dumps({"conflicts": issues})
        ctx.llm_manager.get_client.return_value.chat.return_value = ({"content": resp}, {})
        ctx.response_parser.extract_json.side_effect = json.loads
        return ctx

    @pytest.mark.asyncio
    async def test_no_deps_skips_phase(self, tmp_path):
        ctx = self._make_context()
        ctx.logic_plan = {}  # no imports
        phase = DependencyPrecheckPhase(ctx)
        gf, _, _ = await phase.run("desc", "proj", tmp_path, "", {}, {}, [])
        ctx.llm_manager.get_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_conflicts_writes_report(self, tmp_path):
        ctx = self._make_context(conflicts=[])
        phase = DependencyPrecheckPhase(ctx)
        gf, _, fps = await phase.run(
            "Flask app", "app", tmp_path, "", {}, {"requirements.txt": "flask==2.3.0"}, ["requirements.txt"]
        )
        assert "dependency_precheck_report.json" in gf
        report = json.loads(gf["dependency_precheck_report.json"])
        assert report["conflicts"] == []

    @pytest.mark.asyncio
    async def test_high_conflict_triggers_autofix(self, tmp_path):
        conflict = {
            "severity": "HIGH",
            "package": "flask",
            "description": "Incompatible with Python 3.12",
            "fix_suggestion": "upgrade to flask==3.0.0",
        }
        ctx = self._make_context(conflicts=[conflict])

        fixed_resp = json.dumps({
            "conflicts": [conflict],
        })
        fix_resp = json.dumps({
            "fixed_manifests": {"requirements.txt": "flask==3.0.0\n"}
        })
        # First call: check, second call: fix
        ctx.llm_manager.get_client.return_value.chat.side_effect = [
            ({"content": fixed_resp}, {}),
            ({"content": fix_resp}, {}),
        ]
        ctx.response_parser.extract_json.side_effect = [
            {"conflicts": [conflict]},
            {"fixed_manifests": {"requirements.txt": "flask==3.0.0\n"}},
        ]

        phase = DependencyPrecheckPhase(ctx)
        gf, _, _ = await phase.run(
            "Flask app", "app", tmp_path, "", {}, {"requirements.txt": "flask==2.0.0"}, ["requirements.txt"]
        )
        # Auto-fix should have updated requirements.txt
        assert gf.get("requirements.txt", "") == "flask==3.0.0\n"

    def test_collect_declared_deps_from_generated_files(self, tmp_path):
        ctx = MagicMock()
        ctx.logic_plan = {}
        phase = DependencyPrecheckPhase(ctx)
        gf = {"requirements.txt": "flask==2.3.0\n"}
        fps = ["requirements.txt"]
        result = phase._collect_declared_deps(gf, fps, tmp_path)
        assert "requirements.txt" in result
        assert "flask==2.3.0" in result["requirements.txt"]

    def test_collect_inferred_from_logic_plan(self, tmp_path):
        ctx = MagicMock()
        ctx.logic_plan = {
            "app/main.py": {"imports": ["flask", "sqlalchemy"]},
        }
        phase = DependencyPrecheckPhase(ctx)
        result = phase._collect_declared_deps({}, [], tmp_path)
        assert "__inferred_imports__" in result
