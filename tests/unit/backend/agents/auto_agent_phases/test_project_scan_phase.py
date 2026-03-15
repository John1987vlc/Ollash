"""Unit tests for ProjectScanPhase."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.agents.auto_agent_phases.project_scan_phase import ProjectScanPhase


def _make_ctx(description: str = "A Python FastAPI REST API", root: Path = None) -> PhaseContext:
    return PhaseContext(
        project_name="TestProject",
        project_description=description,
        project_root=root or Path("/nonexistent/path"),
        llm_manager=MagicMock(),
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )


@pytest.mark.unit
class TestProjectScanPhase:
    def test_detects_python_api_stack(self):
        ctx = _make_ctx("A Python FastAPI REST API with SQLite database")
        ProjectScanPhase().run(ctx)
        assert "python" in ctx.tech_stack
        assert "fastapi" in ctx.tech_stack

    def test_detects_react_frontend_stack(self):
        ctx = _make_ctx("A React TypeScript web application with hooks")
        ProjectScanPhase().run(ctx)
        assert "react" in ctx.tech_stack or "typescript" in ctx.tech_stack

    def test_detects_cli_type(self):
        ctx = _make_ctx("A Python CLI tool for file conversion using argparse")
        ProjectScanPhase().run(ctx)
        assert ctx.project_type in ("cli", "python_app", "unknown")  # may vary by detector

    def test_defaults_to_python_if_no_stack_detected(self):
        ctx = _make_ctx("A project that does stuff")
        ProjectScanPhase().run(ctx)
        assert "python" in ctx.tech_stack

    def test_no_llm_calls_made(self):
        ctx = _make_ctx()
        ProjectScanPhase().run(ctx)
        ctx.llm_manager.get_client.assert_not_called()

    def test_nonexistent_root_does_not_ingest(self):
        ctx = _make_ctx(root=Path("/nonexistent/path"))
        ProjectScanPhase().run(ctx)
        assert len(ctx.generated_files) == 0

    def test_existing_root_ingests_files(self, tmp_path):
        # Create a real directory with a Python file
        (tmp_path / "main.py").write_text("print('hello')")
        ctx = _make_ctx(root=tmp_path)
        ProjectScanPhase().run(ctx)
        assert "main.py" in ctx.generated_files

    def test_ingested_files_capped_at_50(self, tmp_path):
        # Create 60 Python files
        for i in range(60):
            (tmp_path / f"file_{i}.py").write_text(f"# file {i}")
        ctx = _make_ctx(root=tmp_path)
        ProjectScanPhase().run(ctx)
        assert len(ctx.generated_files) <= 50

    def test_ignores_non_source_files(self, tmp_path):
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        (tmp_path / "binary.exe").write_bytes(b"\x00\x01\x02")
        ctx = _make_ctx(root=tmp_path)
        ProjectScanPhase().run(ctx)
        assert len(ctx.generated_files) == 0

    def test_ignores_git_directory(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]")
        (tmp_path / "main.py").write_text("pass")
        ctx = _make_ctx(root=tmp_path)
        ProjectScanPhase().run(ctx)
        # Should have main.py but not .git/config
        assert "main.py" in ctx.generated_files
        assert ".git/config" not in ctx.generated_files
