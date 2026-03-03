"""Unit tests for ClarificationPhase."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.auto_agent_phases.clarification_phase import ClarificationPhase


@pytest.mark.unit
class TestClarificationPhase:
    def _make_context(self, llm_response=None, questions=None):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.clarification_answers = {}
        ctx.clarified_description = ""

        # event_publisher mock: subscribe/unsubscribe/publish
        ep = MagicMock()
        ep.subscribe = MagicMock()
        ep.unsubscribe = MagicMock()
        ep.publish = AsyncMock()
        ctx.event_publisher = ep

        # LLM mock
        raw_response = "[]" if questions is None else (
            f'[{", ".join(repr(q) for q in questions)}]'
        )
        if llm_response is not None:
            raw_response = llm_response
        ctx.llm_manager.get_client.return_value.chat.return_value = (
            {"content": raw_response},
            {},
        )
        ctx.response_parser.extract_json.side_effect = lambda x: eval(x) if x.startswith("[") else None
        return ctx

    @pytest.mark.asyncio
    async def test_no_questions_returned(self):
        """Phase completes instantly when LLM returns empty question list."""
        ctx = self._make_context(llm_response="[]")
        phase = ClarificationPhase(ctx)
        gf, struct, fps = await phase.run("Build a REST API with FastAPI", "myapp", Path("/tmp"), "", {}, {}, [])
        assert gf == {}
        assert ctx.clarification_answers == {}

    @pytest.mark.asyncio
    async def test_questions_timeout_gracefully(self):
        """Questions that time out do NOT enrich the description — phase continues."""
        ctx = self._make_context(questions=["What database?"])

        # Make the event never fire → asyncio.wait_for times out immediately
        async def fake_wait(coro, timeout):
            raise asyncio.TimeoutError

        phase = ClarificationPhase(ctx)
        phase._TIMEOUT_SECONDS = 0.001
        with patch("asyncio.wait_for", side_effect=fake_wait):
            gf, _, _ = await phase.run("desc", "proj", Path("/tmp"), "", {}, {}, [])

        assert "__clarified_description__" not in gf

    @pytest.mark.asyncio
    async def test_enriched_description_stored(self):
        """When the user answers, the enriched description is stored on context."""
        ctx = self._make_context(questions=["Which DB?"])

        # Simulate instant response via event
        async def fake_wait(coro, timeout):
            pass  # event resolves immediately

        original_ask = ClarificationPhase._ask_user

        async def patched_ask(self_inner, question):
            return "PostgreSQL"

        phase = ClarificationPhase(ctx)
        with patch.object(ClarificationPhase, "_ask_user", patched_ask):
            gf, _, _ = await phase.run("Build an app", "proj", Path("/tmp"), "", {}, {}, [])

        assert ctx.clarification_answers == {"Which DB?": "PostgreSQL"}
        assert "Clarifications" in ctx.clarified_description
        assert "__clarified_description__" in gf

    @pytest.mark.asyncio
    async def test_llm_failure_does_not_raise(self):
        """If the LLM call raises, the phase returns unchanged outputs."""
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.clarification_answers = {}
        ctx.clarified_description = ""
        ctx.event_publisher.publish = AsyncMock()
        ctx.llm_manager.get_client.return_value.chat.side_effect = RuntimeError("LLM down")
        ctx.response_parser.extract_json.return_value = None

        phase = ClarificationPhase(ctx)
        gf, _, fps = await phase.run("desc", "proj", Path("/tmp"), "", {}, {}, [])
        # Should not raise; output unchanged
        assert gf == {}

    @pytest.mark.asyncio
    async def test_max_questions_cap(self):
        """Never asks more than _MAX_QUESTIONS questions."""
        long_list = [f"Q{i}" for i in range(10)]

        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.clarification_answers = {}
        ctx.clarified_description = ""
        ctx.event_publisher.publish = AsyncMock()
        ctx.event_publisher.subscribe = MagicMock()
        ctx.event_publisher.unsubscribe = MagicMock()
        ctx.llm_manager.get_client.return_value.chat.return_value = (
            {"content": str(long_list)},
            {},
        )
        ctx.response_parser.extract_json.return_value = long_list

        asked: list = []

        async def patched_ask(self_inner, q):
            asked.append(q)
            return "answer"

        phase = ClarificationPhase(ctx)
        with patch.object(ClarificationPhase, "_ask_user", patched_ask):
            await phase.run("desc", "proj", Path("/tmp"), "", {}, {}, [])

        assert len(asked) <= phase._MAX_QUESTIONS
