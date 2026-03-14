"""Unit tests for WebSmokeTestPhase (Fix 4)."""

import json
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.auto_agent_phases.web_smoke_test_phase import (
    WebSmokeTestPhase,
    _free_port,
    _playwright_importable,
)


@pytest.fixture
def context():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.event_publisher.publish_sync = MagicMock()
    ctx.file_refiner = MagicMock()
    ctx.file_refiner.refine_file = MagicMock(return_value="")
    ctx.file_manager = MagicMock()
    return ctx


@pytest.fixture
def phase(context):
    return WebSmokeTestPhase(context=context)


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def html_files() -> Dict[str, str]:
    return {"index.html": "<html><head></head><body><button id='deal-btn'>Deal</button></body></html>"}


@pytest.mark.unit
class TestWebSmokeTestPhaseSkipGuards:
    """Phase skips when conditions are not met."""

    def test_skips_when_playwright_not_installed(self, phase, project_root):
        """Phase skips gracefully when playwright is not available."""
        with (
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase.shutil.which", return_value=None),
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase._playwright_importable", return_value=False),
        ):
            files = {"app.py": "print('hello')"}
            result_files, _, _ = phase.run(
                project_description="test",
                project_name="test",
                project_root=project_root,
                readme_content="",
                initial_structure={},
                generated_files=files,
                file_paths=list(files),
            )
        assert result_files == files
        phase.context.logger.info.assert_called()

    def test_skips_for_non_web_project(self, phase, project_root):
        """Phase skips when no HTML files are present."""
        with (
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase.shutil.which", return_value="playwright"),
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase._playwright_importable", return_value=True),
        ):
            files = {"app.py": "def main(): pass"}
            result_files, _, _ = phase.run(
                project_description="test",
                project_name="test",
                project_root=project_root,
                readme_content="",
                initial_structure={},
                generated_files=files,
                file_paths=list(files),
            )
        assert result_files == files


@pytest.mark.unit
class TestWebSmokeTestPhasePassScenario:
    """Phase passes when browser reports no errors and finds visible elements."""

    def test_smoke_pass_no_repair(self, phase, project_root, html_files):
        """Smoke test passes → repair is NOT triggered."""
        playwright_result = json.dumps({"errors": [], "visible_elements": 3})

        with (
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase.shutil.which", return_value="playwright"),
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase._playwright_importable", return_value=True),
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase.subprocess.Popen") as mock_popen,
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase.subprocess.run") as mock_run,
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase.time.sleep"),
        ):
            mock_popen.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_popen.return_value.terminate = MagicMock()
            mock_popen.return_value.wait = MagicMock()
            mock_run.return_value.stdout = playwright_result
            mock_run.return_value.returncode = 0

            result_files, _, _ = phase.run(
                project_description="poker game",
                project_name="poker",
                project_root=project_root,
                readme_content="",
                initial_structure={},
                generated_files=html_files,
                file_paths=list(html_files),
            )

        # Files unchanged on success
        assert result_files == html_files
        # Refiner was never called
        phase.context.file_refiner.refine_file.assert_not_called()


@pytest.mark.unit
class TestWebSmokeTestPhaseRepairScenario:
    """Phase triggers repair when browser reports console errors."""

    def test_smoke_fail_triggers_repair(self, phase, project_root):
        """Smoke test fails → refine_file called for the referenced JS file."""
        js_content = "document.getElementById('wrong-id');"
        files = {
            "index.html": "<html><body><div id='game'></div></body></html>",
            "src/game.js": js_content,
        }
        playwright_result = json.dumps(
            {
                "errors": ["ReferenceError: Cannot read property of null (src/game.js:1)"],
                "visible_elements": 0,
            }
        )
        repaired = "document.getElementById('game');"
        phase.context.file_refiner.refine_file = MagicMock(return_value=repaired)

        with (
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase.shutil.which", return_value="playwright"),
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase._playwright_importable", return_value=True),
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase.subprocess.Popen") as mock_popen,
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase.subprocess.run") as mock_run,
            patch("backend.agents.auto_agent_phases.web_smoke_test_phase.time.sleep"),
        ):
            mock_popen.return_value.terminate = MagicMock()
            mock_popen.return_value.wait = MagicMock()
            mock_run.return_value.stdout = playwright_result
            mock_run.return_value.returncode = 0

            result_files, _, _ = phase.run(
                project_description="poker",
                project_name="poker",
                project_root=project_root,
                readme_content="",
                initial_structure={},
                generated_files=files,
                file_paths=list(files),
            )

        phase.context.file_refiner.refine_file.assert_called_once()
        assert result_files["src/game.js"] == repaired


@pytest.mark.unit
class TestWebSmokeTestPhaseHelpers:
    """Tests for module-level helper utilities."""

    def test_free_port_returns_integer(self):
        port = _free_port()
        assert isinstance(port, int)
        assert 1024 < port < 65536

    def test_playwright_importable_returns_bool(self):
        result = _playwright_importable()
        assert isinstance(result, bool)

    def test_pick_index_html_prefers_index(self, phase):
        html_files = ["src/about.html", "index.html", "game.html"]
        assert phase._pick_index_html(html_files) == "index.html"

    def test_pick_index_html_fallback(self, phase):
        html_files = ["game.html"]
        assert phase._pick_index_html(html_files) == "game.html"
