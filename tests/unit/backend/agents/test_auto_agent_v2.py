"""Unit tests for the new 8-phase AutoAgent."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.auto_agent import AutoAgent
from backend.utils.core.exceptions import PipelinePhaseError


def _make_agent(tmp_path: Path) -> AutoAgent:
    return AutoAgent(
        llm_manager=MagicMock(),
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
        generated_projects_dir=tmp_path / "projects",
    )


@pytest.mark.unit
class TestAutoAgent:
    def test_run_calls_phases_in_order(self, tmp_path):
        """Phases should execute in the defined order."""
        agent = _make_agent(tmp_path)
        executed: list = []

        class FakePhase:
            def __init__(self, name):
                self.name = name
            def execute(self, ctx):
                executed.append(self.name)

        # Patch _load_phases to return controlled phases
        fake_classes = {name: type(name, (), {"__init__": lambda self: None, "execute": lambda self, ctx: executed.append(name)})
                        for name in AutoAgent.SMALL_PHASE_ORDER}

        with patch("backend.agents.auto_agent._load_phases", return_value=fake_classes):
            with patch.object(type(agent), "__init__", lambda s, **kw: None):
                # Directly mock is_small on ctx
                with patch("backend.agents.auto_agent.PhaseContext") as MockCtx:
                    mock_ctx = MagicMock()
                    mock_ctx.is_small.return_value = True
                    mock_ctx.errors = []
                    mock_ctx.generated_files = {}
                    mock_ctx.total_tokens.return_value = 0
                    MockCtx.return_value = mock_ctx

                    agent.run("A test project", "test_project")
                    # For small model, TestRunPhase is skipped
                    assert "TestRunPhase" not in executed

    def test_small_model_uses_small_phase_order(self, tmp_path):
        """Small models skip TestRunPhase."""
        agent = _make_agent(tmp_path)

        with patch("backend.agents.auto_agent._load_phases") as mock_load:
            with patch("backend.agents.auto_agent.PhaseContext") as MockCtx:
                mock_ctx = MagicMock()
                mock_ctx.is_small.return_value = True
                mock_ctx.errors = []
                mock_ctx.generated_files = {}
                mock_ctx.total_tokens.return_value = 0
                MockCtx.return_value = mock_ctx

                fake_phase = MagicMock()
                fake_phase_cls = MagicMock(return_value=fake_phase)
                mock_load.return_value = {name: fake_phase_cls for name in AutoAgent.FULL_PHASE_ORDER}

                agent.run("A test project", "test_project")

                # Count how many times execute was called
                # For SMALL_PHASE_ORDER (7 phases) vs FULL_PHASE_ORDER (8 phases)
                assert fake_phase.execute.call_count == len(AutoAgent.SMALL_PHASE_ORDER)

    def test_phase_error_continues_pipeline(self, tmp_path):
        """A PipelinePhaseError in one phase does not stop other phases."""
        agent = _make_agent(tmp_path)
        executed: list = []

        with patch("backend.agents.auto_agent._load_phases") as mock_load:
            with patch("backend.agents.auto_agent.PhaseContext") as MockCtx:
                mock_ctx = MagicMock()
                mock_ctx.is_small.return_value = True
                mock_ctx.errors = []
                mock_ctx.generated_files = {}
                mock_ctx.total_tokens.return_value = 0
                MockCtx.return_value = mock_ctx

                call_count = [0]

                class PhaseWithError:
                    def execute(self, ctx):
                        call_count[0] += 1
                        if call_count[0] == 1:
                            raise PipelinePhaseError("1", "test error")

                class NormalPhase:
                    def execute(self, ctx):
                        call_count[0] += 1

                phase_map = {}
                phase_names = AutoAgent.SMALL_PHASE_ORDER
                # First phase raises, rest are normal
                phase_map[phase_names[0]] = PhaseWithError
                for name in phase_names[1:]:
                    phase_map[name] = NormalPhase
                mock_load.return_value = phase_map

                agent.run("A test project", "test_project")
                # All phases should have been called
                assert call_count[0] == len(AutoAgent.SMALL_PHASE_ORDER)
                # Error should be logged
                assert len(mock_ctx.errors) == 1

    def test_project_root_created_if_missing(self, tmp_path):
        agent = _make_agent(tmp_path)
        custom_root = tmp_path / "my_project"
        assert not custom_root.exists()

        with patch("backend.agents.auto_agent._load_phases") as mock_load:
            with patch("backend.agents.auto_agent.PhaseContext") as MockCtx:
                mock_ctx = MagicMock()
                mock_ctx.is_small.return_value = True
                mock_ctx.errors = []
                mock_ctx.generated_files = {}
                mock_ctx.total_tokens.return_value = 0
                MockCtx.return_value = mock_ctx

                fake_phase_cls = MagicMock()
                fake_phase_cls.return_value.execute = MagicMock()
                mock_load.return_value = {name: fake_phase_cls for name in AutoAgent.FULL_PHASE_ORDER}

                result = agent.run("test", "my_project", project_root=custom_root)
                assert result == custom_root

    def test_generate_structure_only(self, tmp_path):
        """generate_structure_only runs only scan + blueprint."""
        agent = _make_agent(tmp_path)

        executed: list = []

        with patch("backend.agents.auto_agent._load_phases") as mock_load:
            with patch("backend.agents.auto_agent.PhaseContext") as MockCtx:
                mock_ctx = MagicMock()
                mock_ctx.is_small.return_value = True
                mock_ctx.project_type = "api"
                mock_ctx.tech_stack = ["python"]
                mock_ctx.blueprint = []
                MockCtx.return_value = mock_ctx

                def make_phase(name):
                    cls = MagicMock()
                    cls.return_value.execute = MagicMock(side_effect=lambda ctx: executed.append(name))
                    return cls

                phase_map = {name: make_phase(name) for name in AutoAgent.FULL_PHASE_ORDER}
                mock_load.return_value = phase_map

                result = agent.generate_structure_only("A test project", "test_project")

                assert "ProjectScanPhase" in executed
                assert "BlueprintPhase" in executed
                assert "CodeFillPhase" not in executed
                assert isinstance(result, dict)
                assert "files" in result
