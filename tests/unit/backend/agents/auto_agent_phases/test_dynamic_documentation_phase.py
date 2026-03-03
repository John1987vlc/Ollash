"""Unit tests for DynamicDocumentationPhase (E7)."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


def _make_context(tmp_path: Path) -> MagicMock:
    """Build a minimal mock PhaseContext."""
    ctx = MagicMock()
    ctx.logic_plan = {}
    ctx.tech_stack_info = None
    ctx.file_manager = MagicMock()
    ctx.file_manager.write_file = MagicMock(return_value="ok")
    ctx.project_planner = MagicMock()
    ctx.project_planner.generate_changelog_entry = AsyncMock(
        return_value="## [Auto-2024-01-01]\n\n### Changed\n- stuff\n"
    )
    ctx.project_planner.generate_roadmap = AsyncMock(return_value="# Roadmap\n\n## Current Focus\n- improve stuff\n")
    ctx.project_planner.update_readme_summary = AsyncMock(
        return_value="# MyProject\n\n## Last Auto-Update\n- updated\n"
    )
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.event_publisher.publish = AsyncMock()
    return ctx


@pytest.mark.unit
class TestDynamicDocumentationPhase:
    """Tests for DynamicDocumentationPhase.execute()."""

    @pytest.mark.asyncio
    async def test_execute_writes_changelog(self, tmp_path):
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase

        ctx = _make_context(tmp_path)
        phase = DynamicDocumentationPhase(context=ctx)

        files = {"README.md": "# Test\n"}
        result_files, _, _ = await phase.execute(
            project_description="A test project",
            project_name="TestProj",
            project_root=tmp_path,
            readme_content="# TestProj\n",
            initial_structure={},
            generated_files=files,
        )

        assert "CHANGELOG.md" in result_files
        ctx.project_planner.generate_changelog_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_writes_roadmap_when_gaps_present(self, tmp_path):
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase

        ctx = _make_context(tmp_path)
        phase = DynamicDocumentationPhase(context=ctx)

        initial_structure = {"improvement_gaps": {"security": ["fix auth"], "testing": ["add tests"]}}
        result_files, _, _ = await phase.execute(
            project_description="A test project",
            project_name="TestProj",
            project_root=tmp_path,
            readme_content="# TestProj\n",
            initial_structure=initial_structure,
            generated_files={},
        )

        assert "ROADMAP.md" in result_files
        ctx.project_planner.generate_roadmap.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_skips_roadmap_when_no_gaps(self, tmp_path):
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase

        ctx = _make_context(tmp_path)
        phase = DynamicDocumentationPhase(context=ctx)

        result_files, _, _ = await phase.execute(
            project_description="A test project",
            project_name="TestProj",
            project_root=tmp_path,
            readme_content="# TestProj\n",
            initial_structure={},  # no improvement_gaps key
            generated_files={},
        )

        assert "ROADMAP.md" not in result_files
        ctx.project_planner.generate_roadmap.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_updates_readme(self, tmp_path):
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase

        ctx = _make_context(tmp_path)
        phase = DynamicDocumentationPhase(context=ctx)

        result_files, _, _ = await phase.execute(
            project_description="desc",
            project_name="Proj",
            project_root=tmp_path,
            readme_content="# Original\n",
            initial_structure={},
            generated_files={"README.md": "# Original\n"},
        )

        assert "README.md" in result_files
        ctx.project_planner.update_readme_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_survives_changelog_error(self, tmp_path):
        """A LLM error in generate_changelog_entry must NOT crash the phase."""
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase

        ctx = _make_context(tmp_path)
        ctx.project_planner.generate_changelog_entry.side_effect = RuntimeError("LLM down")
        phase = DynamicDocumentationPhase(context=ctx)

        # Should not raise
        result_files, _, _ = await phase.execute(
            project_description="desc",
            project_name="Proj",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={},
        )

        ctx.logger.warning.assert_called()
        assert "CHANGELOG.md" not in result_files

    @pytest.mark.asyncio
    async def test_execute_returns_unchanged_files_on_all_errors(self, tmp_path):
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase

        ctx = _make_context(tmp_path)
        ctx.project_planner.generate_changelog_entry.side_effect = RuntimeError("err1")
        ctx.project_planner.generate_roadmap.side_effect = RuntimeError("err2")
        ctx.project_planner.update_readme_summary.side_effect = RuntimeError("err3")
        phase = DynamicDocumentationPhase(context=ctx)

        original_files = {"src/app.py": "x = 1\n"}
        result_files, _, _ = await phase.execute(
            project_description="desc",
            project_name="Proj",
            project_root=tmp_path,
            readme_content="",
            initial_structure={"improvement_gaps": {"a": ["b"]}},
            generated_files=dict(original_files),
        )

        # Original files preserved, new doc files not added
        assert result_files.get("src/app.py") == "x = 1\n"
        assert "CHANGELOG.md" not in result_files
        assert "ROADMAP.md" not in result_files

    # ------------------------------------------------------------------
    # _collect_cycle_changes
    # ------------------------------------------------------------------

    def test_collect_cycle_changes_uses_logic_plan(self, tmp_path):
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase

        ctx = _make_context(tmp_path)
        ctx.logic_plan = {
            "src/app.py": {"description": "Added login endpoint"},
            "src/models.py": {"purpose": "New User model"},
        }
        phase = DynamicDocumentationPhase(context=ctx)
        changes = phase._collect_cycle_changes()

        assert any("login endpoint" in c for c in changes)
        assert any("User model" in c for c in changes)

    def test_collect_cycle_changes_falls_back_when_empty(self, tmp_path):
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase

        ctx = _make_context(tmp_path)
        ctx.logic_plan = {}
        phase = DynamicDocumentationPhase(context=ctx)
        changes = phase._collect_cycle_changes()

        assert len(changes) >= 1

    # ------------------------------------------------------------------
    # _prepend_entry
    # ------------------------------------------------------------------

    def test_prepend_entry_adds_header_to_empty_changelog(self):
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase

        result = DynamicDocumentationPhase._prepend_entry("", "## [Auto-2024] - 2024-01-01\n\n### Changed\n- x\n")
        assert "# Changelog" in result
        assert "Auto-2024" in result

    def test_prepend_entry_inserts_before_existing_entry(self):
        from backend.agents.auto_agent_phases.dynamic_documentation_phase import DynamicDocumentationPhase

        existing = "# Changelog\n\n## [v1.0] - 2023-01-01\n\n### Changed\n- old\n"
        result = DynamicDocumentationPhase._prepend_entry(existing, "## [v2.0] - 2024-01-01\n\n### Added\n- new\n")
        assert result.index("v2.0") < result.index("v1.0")
