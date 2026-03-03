"""Unit tests for TestPlanningPhase (TDD skeleton generator)."""

from unittest.mock import MagicMock

import pytest

# Import under alias to prevent pytest from treating the class as a test collector
from backend.agents.auto_agent_phases.test_planning_phase import TestPlanningPhase as TDDPlanningPhase  # noqa: N814


@pytest.mark.unit
class TestTDDPlanningPhase:
    def _make_context(self, logic_plan=None):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.test_skeletons = {}
        ctx.file_manager = MagicMock()
        ctx.logic_plan = logic_plan or {
            "src/main.py": {
                "purpose": "Entry point",
                "exports": ["main", "create_app"],
            },
            "src/utils.py": {
                "purpose": "Utilities",
                "exports": ["parse_config"],
            },
        }
        ctx.llm_manager.get_client.return_value.chat.return_value = (
            {"content": "def test_placeholder():\n    pass\n"},
            {},
        )
        ctx.response_parser = MagicMock()
        return ctx

    @pytest.mark.asyncio
    async def test_creates_test_skeletons(self, tmp_path):
        ctx = self._make_context()
        phase = TDDPlanningPhase(ctx)
        gf, _, fps = await phase.run("Flask app", "myapp", tmp_path, "", {}, {}, [])
        # Should have written at least one skeleton
        assert len(ctx.test_skeletons) >= 1

    @pytest.mark.asyncio
    async def test_skips_config_files(self, tmp_path):
        ctx = self._make_context(
            logic_plan={
                "requirements.txt": {"purpose": "deps", "exports": []},
                "pyproject.toml": {"purpose": "config", "exports": []},
            }
        )
        phase = TDDPlanningPhase(ctx)
        await phase.run("app", "proj", tmp_path, "", {}, {}, [])
        assert len(ctx.test_skeletons) == 0

    @pytest.mark.asyncio
    async def test_skips_existing_test_file(self, tmp_path):
        ctx = self._make_context(logic_plan={"src/main.py": {"purpose": "main", "exports": []}})
        phase = TDDPlanningPhase(ctx)
        # Pre-populate the test file
        test_path = "tests/test_main.py"
        gf = {test_path: "# already has tests\n\ndef test_existing(): pass"}
        gf_out, _, _ = await phase.run("app", "proj", tmp_path, "", {}, gf, [test_path])
        # The existing test must not be overwritten
        assert gf_out[test_path].startswith("# already has tests")

    def test_minimal_skeleton_python(self):
        sk = TDDPlanningPhase._minimal_skeleton("src/calc.py", ["add", "subtract"], "python")
        assert "def test_add" in sk
        assert "def test_subtract" in sk
        assert "pass" in sk

    def test_minimal_skeleton_javascript(self):
        sk = TDDPlanningPhase._minimal_skeleton("src/calc.js", ["add"], "javascript")
        assert "describe(" in sk
        assert "test(" in sk

    def test_filter_source_files_excludes_tests(self):
        files = [
            "src/app.py",
            "tests/test_app.py",
            "src/utils.ts",
            "README.md",
            "package.json",
        ]
        filtered = TDDPlanningPhase._filter_source_files(files)
        assert "src/app.py" in filtered
        assert "src/utils.ts" in filtered
        assert "tests/test_app.py" not in filtered
        assert "README.md" not in filtered
        assert "package.json" not in filtered
