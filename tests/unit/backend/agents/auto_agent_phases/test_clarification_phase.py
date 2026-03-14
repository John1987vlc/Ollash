"""Unit tests for ClarificationPhase."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.auto_agent_phases.clarification_phase import ClarificationPhase


@pytest.mark.unit
class TestClarificationPhase:
    def _make_context(self, llm_response=None, questions=None):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.clarification_answers = {}
        ctx.clarified_description = ""

        # event_publisher mock: subscribe/unsubscribe/publish_sync
        ep = MagicMock()
        ep.subscribe = MagicMock()
        ep.unsubscribe = MagicMock()
        ep.publish_sync = MagicMock()
        ep.has_subscribers.return_value = True
        ctx.event_publisher = ep

        # LLM mock
        import json

        raw_response = "[]" if questions is None else json.dumps(questions)
        if llm_response is not None:
            raw_response = llm_response
        ctx.llm_manager.get_client.return_value.chat.return_value = (
            {"content": raw_response},
            {},
        )
        ctx.response_parser.extract_json.side_effect = lambda x: json.loads(x) if x.startswith("[") else None
        return ctx

    def test_no_questions_returned(self):
        """Phase completes instantly when LLM returns empty question list."""
        ctx = self._make_context(llm_response="[]")
        phase = ClarificationPhase(ctx)
        gf, struct, fps = phase.run("Build a REST API with FastAPI", "myapp", Path("/tmp"), "", {}, {}, [])
        assert gf == {}
        assert ctx.clarification_answers == {}

    def test_questions_skip_when_no_subscribers(self):
        """Questions are skipped if no active subscribers are detected."""
        ctx = self._make_context(questions=["What database?"])
        ctx.event_publisher.has_subscribers.return_value = False

        phase = ClarificationPhase(ctx)
        gf, _, _ = phase.run("desc", "proj", Path("/tmp"), "", {}, {}, [])

        assert "__clarified_description__" not in gf
        assert ctx.clarification_answers == {}

    def test_enriched_description_stored(self):
        """When the user answers, the enriched description is stored on context."""
        ctx = self._make_context(questions=["Which DB?"])

        def patched_ask(self_inner, question):
            return "PostgreSQL"

        phase = ClarificationPhase(ctx)
        with patch.object(ClarificationPhase, "_ask_user", patched_ask):
            gf, _, _ = phase.run("Build an app", "proj", Path("/tmp"), "", {}, {}, [])

        assert ctx.clarification_answers == {"Which DB?": "PostgreSQL"}
        assert "Clarifications" in ctx.clarified_description
        assert "__clarified_description__" in gf

    def test_llm_failure_does_not_raise(self):
        """If the LLM call raises, the phase returns unchanged outputs."""
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.clarification_answers = {}
        ctx.clarified_description = ""
        ctx.event_publisher.publish_sync = MagicMock()
        ctx.llm_manager.get_client.return_value.chat.side_effect = RuntimeError("LLM down")
        ctx.response_parser.extract_json.return_value = None

        phase = ClarificationPhase(ctx)
        gf, _, fps = phase.run("desc", "proj", Path("/tmp"), "", {}, {}, [])
        # Should not raise; output unchanged
        assert gf == {}

    def test_max_questions_cap(self):
        """Never asks more than _MAX_QUESTIONS questions."""
        long_list = [f"Q{i}" for i in range(10)]

        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.clarification_answers = {}
        ctx.clarified_description = ""
        ctx.event_publisher.publish_sync = MagicMock()
        ctx.event_publisher.subscribe = MagicMock()
        ctx.event_publisher.unsubscribe = MagicMock()
        ctx.event_publisher.has_subscribers.return_value = True
        ctx.llm_manager.get_client.return_value.chat.return_value = (
            {"content": str(long_list)},
            {},
        )
        ctx.response_parser.extract_json.return_value = long_list

        asked: list = []

        def patched_ask(self_inner, q):
            asked.append(q)
            return "answer"

        phase = ClarificationPhase(ctx)
        with patch.object(ClarificationPhase, "_ask_user", patched_ask):
            phase.run("desc", "proj", Path("/tmp"), "", {}, {}, [])

        assert len(asked) <= phase._MAX_QUESTIONS
