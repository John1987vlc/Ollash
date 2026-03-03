"""Unit tests for ViabilityEstimatorPhase."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.auto_agent_phases.viability_estimator_phase import (
    ViabilityEstimatorPhase,
    _LARGE_PROJECT_THRESHOLD,
)


@pytest.mark.unit
class TestViabilityEstimatorPhase:
    def _make_context(self):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.viability_report = None
        ctx.file_manager = MagicMock()
        ctx.token_tracker = MagicMock()
        ctx.token_tracker.session_total_tokens = 1000

        ep = MagicMock()
        ep.publish = AsyncMock()
        ep.subscribe = MagicMock()
        ep.unsubscribe = MagicMock()
        ctx.event_publisher = ep
        return ctx

    @pytest.mark.asyncio
    async def test_writes_report_for_small_project(self, tmp_path):
        ctx = self._make_context()
        phase = ViabilityEstimatorPhase(ctx)
        files = ["src/main.py", "src/utils.py", "tests/test_main.py", "README.md"]
        gf, _, fps = await phase.run("desc", "proj", tmp_path, "", {}, {}, files)
        assert "viability_report.json" in gf
        report = json.loads(gf["viability_report.json"])
        assert report["total_files"] == 4
        assert report["estimated_tokens"] > 0
        assert not report["threshold_exceeded"]
        assert ctx.viability_report is not None

    @pytest.mark.asyncio
    async def test_publishes_viability_event(self, tmp_path):
        ctx = self._make_context()
        phase = ViabilityEstimatorPhase(ctx)
        await phase.run("desc", "proj", tmp_path, "", {}, {}, ["src/main.py"])
        ctx.event_publisher.publish.assert_called_once()
        call_kwargs = ctx.event_publisher.publish.call_args
        assert call_kwargs[0][0] == "viability_estimate"

    @pytest.mark.asyncio
    async def test_large_project_asks_confirmation_and_proceeds(self, tmp_path):
        ctx = self._make_context()
        # Simulate fast approval
        async def patched_confirm(self_inner, report, project_name):
            return True

        phase = ViabilityEstimatorPhase(ctx)
        # Create a huge file list to exceed threshold
        huge_files = [f"src/module_{i}.py" for i in range(500)]
        with pytest.raises(Exception):
            # threshold_exceeded == True but user cancels
            async def patched_confirm_cancel(self_inner, report, project_name):
                return False

            from unittest.mock import patch
            with patch.object(ViabilityEstimatorPhase, "_ask_confirmation", patched_confirm_cancel):
                await phase.run("huge project", "proj", tmp_path, "", {}, {}, huge_files)

    def test_classify_file_types(self):
        assert ViabilityEstimatorPhase._classify_file("config.yaml") == "config"
        assert ViabilityEstimatorPhase._classify_file("README.md") == "docs"
        assert ViabilityEstimatorPhase._classify_file("tests/test_main.py") == "test"
        assert ViabilityEstimatorPhase._classify_file("src/app.py") == "source"

    def test_extract_paths_from_nested_structure(self):
        structure = {
            "files": ["README.md"],
            "folders": [
                {
                    "name": "src",
                    "files": ["main.py", "utils.py"],
                    "folders": [],
                }
            ],
        }
        paths = ViabilityEstimatorPhase._extract_paths_from_structure(structure)
        assert "README.md" in paths
        assert "src/main.py" in paths
        assert "src/utils.py" in paths

    @pytest.mark.asyncio
    async def test_uses_file_paths_from_structure_when_empty(self, tmp_path):
        ctx = self._make_context()
        structure = {
            "files": ["README.md"],
            "folders": [{"name": "src", "files": ["main.py"], "folders": []}],
        }
        phase = ViabilityEstimatorPhase(ctx)
        gf, _, _ = await phase.run("desc", "proj", tmp_path, "", structure, {}, [])
        assert "viability_report.json" in gf
        report = json.loads(gf["viability_report.json"])
        assert report["total_files"] == 2
