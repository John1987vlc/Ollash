"""Unit tests for ProjectPlanner E7 extension methods."""

import pytest
from unittest.mock import MagicMock, patch

_PLANNER_MODULE = "backend.utils.domains.auto_generation.planning.project_planner"


def _make_planner():
    """Build a ProjectPlanner with a mocked LLM client."""
    from backend.utils.domains.auto_generation.planning.project_planner import ProjectPlanner

    mock_llm = MagicMock()
    mock_llm.chat.return_value = (
        {"message": {"content": "GENERATED_CONTENT"}},
        {},
    )
    logger = MagicMock()
    return ProjectPlanner(llm_client=mock_llm, logger=logger), mock_llm


@pytest.mark.unit
class TestProjectPlannerExtended:
    """Tests for generate_changelog_entry, generate_roadmap, update_readme_summary."""

    # ------------------------------------------------------------------
    # generate_changelog_entry
    # ------------------------------------------------------------------

    def test_generate_changelog_entry_calls_llm(self):
        planner, mock_llm = _make_planner()
        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.changelog_entry_prompt", return_value=("sys", "usr")):
            result = planner.generate_changelog_entry(
                project_name="MyApp",
                changes=["Added login", "Fixed auth bug"],
            )
        mock_llm.chat.assert_called_once()
        assert result == "GENERATED_CONTENT"

    def test_generate_changelog_entry_passes_project_name_in_prompt(self):
        planner, mock_llm = _make_planner()

        def fake_prompt(project_name, changes, version=""):
            return ("sys", f"Project: {project_name}")

        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.changelog_entry_prompt", side_effect=fake_prompt):
            planner.generate_changelog_entry(project_name="SpecialProject", changes=["x"])
        call_args = mock_llm.chat.call_args
        messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "SpecialProject" in user_msg

    def test_generate_changelog_entry_includes_changes_in_prompt(self):
        planner, mock_llm = _make_planner()

        def fake_prompt(project_name, changes, version=""):
            return ("sys", f"Changes: {' '.join(changes)}")

        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.changelog_entry_prompt", side_effect=fake_prompt):
            planner.generate_changelog_entry(project_name="P", changes=["feature A", "fix B"])
        call_args = mock_llm.chat.call_args
        messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "feature A" in user_msg
        assert "fix B" in user_msg

    def test_generate_changelog_entry_uses_provided_version(self):
        planner, mock_llm = _make_planner()

        def fake_prompt(project_name, changes, version=""):
            return ("sys", f"Version: {version}")

        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.changelog_entry_prompt", side_effect=fake_prompt):
            planner.generate_changelog_entry(project_name="P", changes=["x"], version="2.3.0")
        call_args = mock_llm.chat.call_args
        messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "2.3.0" in user_msg

    # ------------------------------------------------------------------
    # generate_roadmap
    # ------------------------------------------------------------------

    def test_generate_roadmap_calls_llm(self):
        planner, mock_llm = _make_planner()
        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.roadmap_prompt", return_value=("sys", "usr")):
            result = planner.generate_roadmap(
                project_name="MyApp",
                improvement_gaps={"security": ["fix auth"]},
            )
        mock_llm.chat.assert_called_once()
        assert result == "GENERATED_CONTENT"

    def test_generate_roadmap_includes_gap_categories_in_prompt(self):
        planner, mock_llm = _make_planner()

        def fake_prompt(project_name, improvement_gaps, tech_hints=None):
            return ("sys", f"Gaps: {list(improvement_gaps.keys())}")

        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.roadmap_prompt", side_effect=fake_prompt):
            planner.generate_roadmap(
                project_name="P",
                improvement_gaps={"testing": ["add coverage"], "security": ["use HTTPS"]},
            )
        call_args = mock_llm.chat.call_args
        messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "testing" in user_msg
        assert "security" in user_msg

    def test_generate_roadmap_includes_tech_hints_when_provided(self):
        planner, mock_llm = _make_planner()
        mock_stack = MagicMock()
        mock_stack.prompt_hints = ["Flask 2.3 - use Blueprints"]

        def fake_prompt(project_name, improvement_gaps, tech_hints=None):
            hints = tech_hints or []
            return ("sys", f"Tech: {' '.join(hints)}")

        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.roadmap_prompt", side_effect=fake_prompt):
            planner.generate_roadmap(project_name="P", improvement_gaps={}, tech_stack_info=mock_stack)
        call_args = mock_llm.chat.call_args
        messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "Flask" in user_msg

    def test_generate_roadmap_works_without_tech_stack(self):
        planner, mock_llm = _make_planner()
        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.roadmap_prompt", return_value=("sys", "usr")):
            result = planner.generate_roadmap(project_name="P", improvement_gaps={"a": ["b"]})
        assert result == "GENERATED_CONTENT"

    # ------------------------------------------------------------------
    # update_readme_summary
    # ------------------------------------------------------------------

    def test_update_readme_summary_calls_llm(self):
        planner, mock_llm = _make_planner()
        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.readme_summary_update_prompt", return_value=("sys", "usr")):
            result = planner.update_readme_summary(
                existing_readme="# MyProject\n\nSome content.\n",
                cycle_summary="Auto-cycle 2024-01-01: added login",
            )
        mock_llm.chat.assert_called_once()
        assert result == "GENERATED_CONTENT"

    def test_update_readme_summary_passes_existing_readme_in_prompt(self):
        planner, mock_llm = _make_planner()

        def fake_prompt(existing_readme, cycle_summary):
            return ("sys", f"Readme: {existing_readme}")

        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.readme_summary_update_prompt", side_effect=fake_prompt):
            planner.update_readme_summary(
                existing_readme="# Special README\n\nContent here.\n",
                cycle_summary="some summary",
            )
        call_args = mock_llm.chat.call_args
        messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "Special README" in user_msg

    def test_update_readme_summary_passes_cycle_summary_in_prompt(self):
        planner, mock_llm = _make_planner()

        def fake_prompt(existing_readme, cycle_summary):
            return ("sys", f"Summary: {cycle_summary}")

        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.readme_summary_update_prompt", side_effect=fake_prompt):
            planner.update_readme_summary(
                existing_readme="# Readme\n",
                cycle_summary="UNIQUE_CYCLE_SUMMARY_XYZ",
            )
        call_args = mock_llm.chat.call_args
        messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "UNIQUE_CYCLE_SUMMARY_XYZ" in user_msg

    # ------------------------------------------------------------------
    # DOC_OPTIONS usage (low temperature)
    # ------------------------------------------------------------------

    def test_doc_methods_use_low_temperature_options(self):
        planner, mock_llm = _make_planner()
        with patch(f"{_PLANNER_MODULE}.AutoGenPrompts.changelog_entry_prompt", return_value=("sys", "usr")):
            planner.generate_changelog_entry(project_name="P", changes=["x"])
        call_args = mock_llm.chat.call_args
        # options_override is always passed as a keyword argument
        options = call_args[1].get("options_override", {}) or {}
        assert options.get("temperature", 1.0) <= 0.4
