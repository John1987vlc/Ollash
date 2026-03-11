"""Unit tests for AutoAgent dynamic rescue planning (Mejora 6b).

Tests cover:
- _request_rescue_plan: LLM success, LLM failure, invalid JSON
- RescuePhase.execute: event publishing and passthrough of generated data
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

from backend.agents.auto_agent import RescuePhase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_phase_context():
    ctx = MagicMock()
    ctx.logger.info = MagicMock()
    ctx.event_publisher.publish = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# RescuePhase tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRescuePhase:
    def test_phase_id_includes_index(self):
        ctx = _make_phase_context()
        rp = RescuePhase(ctx, step="Fix context", action="Re-read files", step_index=2)
        assert rp.phase_id == "rescue_2"

    def test_phase_label_truncated(self):
        ctx = _make_phase_context()
        long_step = "A" * 100
        rp = RescuePhase(ctx, step=long_step, action="act", step_index=1)
        # Label includes first 60 chars of step
        assert len(rp.phase_label) <= 80  # "Rescue Step 1: " + 60 chars

    def test_execute_publishes_rescue_event(self):
        ctx = _make_phase_context()
        rp = RescuePhase(ctx, step="Validate imports", action="Check dependencies", step_index=1)

        generated_files = {"src/main.py": "# code"}
        initial_structure = {"files": ["src/main.py"]}

        result = asyncio.get_event_loop().run_until_complete(
            rp.execute(
                project_description="desc",
                project_name="test",
                project_root=Path("/tmp/test"),
                readme_content="",
                initial_structure=initial_structure,
                generated_files=generated_files,
                file_paths=["src/main.py"],
            )
        )

        ctx.event_publisher.publish.assert_called_once()
        call_kwargs = ctx.event_publisher.publish.call_args
        assert call_kwargs[0][0] == "rescue_step_executed"

    def test_execute_returns_unchanged_generated_files(self):
        ctx = _make_phase_context()
        rp = RescuePhase(ctx, step="s", action="a", step_index=1)

        generated_files = {"x.py": "content"}
        gf, structure, fps = asyncio.get_event_loop().run_until_complete(
            rp.execute(
                project_description="",
                project_name="",
                project_root=Path("/tmp"),
                readme_content="",
                initial_structure={},
                generated_files=generated_files,
                file_paths=[],
            )
        )

        assert gf is generated_files
        assert gf["x.py"] == "content"

    def test_execute_extracts_file_paths_from_kwargs(self):
        ctx = _make_phase_context()
        rp = RescuePhase(ctx, step="s", action="a", step_index=1)

        gf, _, fps = asyncio.get_event_loop().run_until_complete(
            rp.execute(
                project_description="",
                project_name="",
                project_root=Path("/tmp"),
                readme_content="",
                initial_structure={},
                generated_files={},
                file_paths=["a.py", "b.py"],
            )
        )
        assert fps == ["a.py", "b.py"]


# ---------------------------------------------------------------------------
# AutoAgent._request_rescue_plan tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRequestRescuePlan:
    """Tests for AutoAgent._request_rescue_plan via a minimal mock of AutoAgent."""

    def _make_agent(self, llm_response_raw: str = "", raise_exc: bool = False):
        """Build a minimal object that has the _request_rescue_plan method."""
        from backend.agents.auto_agent import AutoAgent

        agent = MagicMock(spec=AutoAgent)
        agent.phase_context = _make_phase_context()
        agent.logger = MagicMock()
        agent.logger.info = MagicMock()
        agent.logger.warning = MagicMock()

        mock_client = MagicMock()
        if raise_exc:
            mock_client.chat.side_effect = RuntimeError("LLM down")
        else:
            mock_client.chat.return_value = (
                {"message": {"content": llm_response_raw}},
                None,
            )
        agent.llm_manager = MagicMock()
        agent.llm_manager.get_client.return_value = mock_client

        # Bind the real method
        agent._request_rescue_plan = AutoAgent._request_rescue_plan.__get__(agent)
        return agent

    def test_success_returns_three_rescue_phases(self):
        raw = (
            '[{"step": "Check imports", "action": "Verify all imports present"},'
            ' {"step": "Reduce context", "action": "Trim context window"},'
            ' {"step": "Retry coder", "action": "Reattempt file generation"}]'
        )
        agent = self._make_agent(llm_response_raw=raw)
        phases = asyncio.get_event_loop().run_until_complete(agent._request_rescue_plan("SomePhase", "SomeError"))
        assert len(phases) == 3
        assert all(isinstance(p, RescuePhase) for p in phases)

    def test_success_sets_step_index(self):
        raw = '[{"step": "A", "action": "a"}, {"step": "B", "action": "b"}, {"step": "C", "action": "c"}]'
        agent = self._make_agent(llm_response_raw=raw)
        phases = asyncio.get_event_loop().run_until_complete(agent._request_rescue_plan("P", "E"))
        assert [p._step_index for p in phases] == [1, 2, 3]

    def test_llm_failure_returns_empty_list(self):
        agent = self._make_agent(raise_exc=True)
        phases = asyncio.get_event_loop().run_until_complete(agent._request_rescue_plan("P", "E"))
        assert phases == []

    def test_invalid_json_returns_empty_list(self):
        agent = self._make_agent(llm_response_raw="NOT JSON AT ALL")
        phases = asyncio.get_event_loop().run_until_complete(agent._request_rescue_plan("P", "E"))
        assert phases == []

    def test_non_list_json_returns_empty_list(self):
        agent = self._make_agent(llm_response_raw='{"step": "one", "action": "do it"}')
        phases = asyncio.get_event_loop().run_until_complete(agent._request_rescue_plan("P", "E"))
        assert phases == []

    def test_caps_at_three_steps(self):
        """Even if LLM returns more than 3 items, only 3 phases are created."""
        raw = (
            '[{"step": "A", "action": "a"},'
            ' {"step": "B", "action": "b"},'
            ' {"step": "C", "action": "c"},'
            ' {"step": "D", "action": "d"},'
            ' {"step": "E", "action": "e"}]'
        )
        agent = self._make_agent(llm_response_raw=raw)
        phases = asyncio.get_event_loop().run_until_complete(agent._request_rescue_plan("P", "E"))
        assert len(phases) <= 3
