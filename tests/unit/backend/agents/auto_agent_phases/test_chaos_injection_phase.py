"""Unit tests for ChaosInjectionPhase — Feature 4."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _make_context(chaos_enabled=False, injection_rate=1.0):
    ctx = MagicMock()
    ctx.config = {
        "chaos_engineering": {
            "enabled": chaos_enabled,
            "injection_rate": injection_rate,
        }
    }
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.event_publisher.publish = MagicMock()
    ctx.file_manager = MagicMock()
    ctx.infer_language = MagicMock(return_value="python")
    return ctx


@pytest.mark.unit
class TestChaosInjectionPhase:
    def _run(self, phase, generated_files):
        return phase.run(
            project_description="test",
            project_name="test_project",
            project_root=Path("/tmp/test"),
            readme_content="",
            initial_structure={},
            generated_files=generated_files,
            file_paths=list(generated_files.keys()),
        )

    def test_phase_skips_when_disabled(self):
        from backend.agents.auto_agent_phases.chaos_injection_phase import ChaosInjectionPhase

        ctx = _make_context(chaos_enabled=False)
        phase = ChaosInjectionPhase(context=ctx)
        files = {"app.py": "import os\ndef foo():\n    x = 1\n"}
        result_files, _, _ = self._run(phase, files)
        # Files should be unchanged
        assert result_files["app.py"] == files["app.py"]
        # No chaos events published when disabled
        chaos_calls = [c for c in ctx.event_publisher.publish_sync.call_args_list if c[0][0] == "chaos_fault_injected"]
        assert len(chaos_calls) == 0

    def test_phase_publishes_event_per_injected_file(self):
        from backend.agents.auto_agent_phases.chaos_injection_phase import ChaosInjectionPhase

        ctx = _make_context(chaos_enabled=True, injection_rate=1.0)
        phase = ChaosInjectionPhase(context=ctx)
        files = {"app.py": "import os\nimport sys\ndef foo():\n    my_var = 1\n"}
        self._run(phase, files)
        # At least one chaos event should have been published (phase uses publish_sync)
        calls = [c for c in ctx.event_publisher.publish_sync.call_args_list if c[0][0] == "chaos_fault_injected"]
        assert len(calls) >= 1

    def test_phase_skips_empty_content(self):
        from backend.agents.auto_agent_phases.chaos_injection_phase import ChaosInjectionPhase

        ctx = _make_context(chaos_enabled=True, injection_rate=1.0)
        phase = ChaosInjectionPhase(context=ctx)
        files = {"app.py": ""}
        result_files, _, _ = self._run(phase, files)
        chaos_calls = [c for c in ctx.event_publisher.publish_sync.call_args_list if c[0][0] == "chaos_fault_injected"]
        assert len(chaos_calls) == 0

    def test_phase_skips_unknown_language(self):
        from backend.agents.auto_agent_phases.chaos_injection_phase import ChaosInjectionPhase

        ctx = _make_context(chaos_enabled=True, injection_rate=1.0)
        ctx.infer_language.return_value = "unknown"
        phase = ChaosInjectionPhase(context=ctx)
        files = {"file.bin": "binary data"}
        result_files, _, _ = self._run(phase, files)
        chaos_calls = [c for c in ctx.event_publisher.publish_sync.call_args_list if c[0][0] == "chaos_fault_injected"]
        assert len(chaos_calls) == 0
