"""Unit tests for ScaffoldPhase."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.phase_context import FilePlan, PhaseContext
from backend.agents.auto_agent_phases.scaffold_phase import ScaffoldPhase


def _make_ctx(tmp_path: Path) -> PhaseContext:
    ctx = PhaseContext(
        project_name="TestProject",
        project_description="A test project",
        project_root=tmp_path,
        llm_manager=MagicMock(),
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )
    return ctx


def _add_plan(ctx: PhaseContext, path: str, purpose: str = "test") -> None:
    ctx.blueprint.append(FilePlan(path=path, purpose=purpose))


@pytest.mark.unit
class TestScaffoldPhase:
    def test_creates_python_stub(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _add_plan(ctx, "src/main.py", "Entry point")
        ScaffoldPhase().run(ctx)
        assert (tmp_path / "src" / "main.py").exists()
        content = (tmp_path / "src" / "main.py").read_text()
        assert "Entry point" in content

    def test_creates_typescript_stub(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _add_plan(ctx, "src/index.ts", "TypeScript entry")
        ScaffoldPhase().run(ctx)
        assert (tmp_path / "src" / "index.ts").exists()

    def test_creates_html_stub(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _add_plan(ctx, "index.html", "Main page")
        ScaffoldPhase().run(ctx)
        content = (tmp_path / "index.html").read_text()
        assert "<!DOCTYPE html>" in content

    def test_skips_existing_files(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        ctx.generated_files["main.py"] = "# existing content"
        _add_plan(ctx, "main.py")
        (tmp_path / "main.py").write_text("# existing content")
        ScaffoldPhase().run(ctx)
        # File should not be overwritten — content stays the same
        assert (tmp_path / "main.py").read_text() == "# existing content"

    def test_creates_parent_directories(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _add_plan(ctx, "src/deeply/nested/module.py")
        ScaffoldPhase().run(ctx)
        assert (tmp_path / "src" / "deeply" / "nested" / "module.py").exists()

    def test_no_llm_calls(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _add_plan(ctx, "main.py")
        ScaffoldPhase().run(ctx)
        ctx.llm_manager.get_client.assert_not_called()

    def test_generated_files_populated(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _add_plan(ctx, "main.py")
        _add_plan(ctx, "utils.py")
        ScaffoldPhase().run(ctx)
        assert "main.py" in ctx.generated_files
        assert "utils.py" in ctx.generated_files

    def test_dockerfile_stub(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _add_plan(ctx, "Dockerfile", "Docker image")
        ScaffoldPhase().run(ctx)
        content = (tmp_path / "Dockerfile").read_text()
        assert "FROM python" in content or "FROM" in content

    def test_json_stub(self, tmp_path):
        ctx = _make_ctx(tmp_path)
        _add_plan(ctx, "config.json", "Configuration")
        ScaffoldPhase().run(ctx)
        content = (tmp_path / "config.json").read_text()
        assert content.strip() in ("{}", "{\n}")
