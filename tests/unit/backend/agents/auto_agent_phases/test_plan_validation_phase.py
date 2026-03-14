"""Unit tests for PlanValidationPhase."""

import json
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.plan_validation_phase import PlanValidationPhase

_SAMPLE_PLAN = {
    "src/main.py": {"purpose": "Entry", "main_logic": ["start server"]},
    "src/db.py": {"purpose": "Database", "main_logic": ["connect", "query"]},
}


@pytest.mark.unit
class TestPlanValidationPhase:
    def _make_context(self, critic_verdict="PASS", critic_issues=None):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.logic_plan = dict(_SAMPLE_PLAN)
        ctx.plan_validation_report = None
        ctx.file_manager = MagicMock()

        issues = critic_issues or []
        response_body = json.dumps({"verdict": critic_verdict, "issues": issues})
        ctx.llm_manager.get_client.return_value.chat.return_value = (
            {"content": response_body},
            {},
        )
        ctx.response_parser.extract_json.side_effect = json.loads
        return ctx

    def test_passes_immediately_on_no_issues(self, tmp_path):
        ctx = self._make_context(critic_verdict="PASS")
        phase = PlanValidationPhase(ctx)
        gf, _, _ = phase.run("desc", "proj", tmp_path, "", {}, {}, [])
        assert ctx.plan_validation_report["final_verdict"] == "PASS"
        assert ctx.plan_validation_report["total_rounds"] == 1
        assert "PLAN_VALIDATION_REPORT.json" in gf

    def test_iterates_on_high_issues(self, tmp_path):
        """Critic always fails but after MAX_ROUNDS we stop."""
        high_issue = {"severity": "HIGH", "file": "src/db.py", "description": "SQL injection risk"}
        ctx = self._make_context(
            critic_verdict="FAIL",
            critic_issues=[high_issue],
        )
        # Architect revision returns a non-empty revised plan
        revised = {"src/db.py": {"purpose": "Secure DB", "main_logic": ["parameterized queries"]}}
        ctx.response_parser.extract_json.side_effect = [
            # round 1: critic
            {"verdict": "FAIL", "issues": [high_issue]},
            # round 1: architect
            revised,
            # round 2: critic
            {"verdict": "FAIL", "issues": [high_issue]},
            # round 2: architect
            revised,
            # round 3: critic
            {"verdict": "FAIL", "issues": [high_issue]},
        ]
        phase = PlanValidationPhase(ctx)
        gf, _, _ = phase.run("desc", "proj", tmp_path, "", {}, {}, [])
        assert ctx.plan_validation_report["final_verdict"] == "MAX_ROUNDS_REACHED"
        assert ctx.plan_validation_report["total_rounds"] == PlanValidationPhase.MAX_ROUNDS

    def test_no_logic_plan_skips_phase(self, tmp_path):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.logic_plan = {}
        phase = PlanValidationPhase(ctx)
        gf, struct, fps = phase.run("desc", "proj", tmp_path, "", {}, {}, [])
        # ctx.llm_manager should NOT have been called
        ctx.llm_manager.get_client.assert_not_called()

    def test_report_written_to_disk(self, tmp_path):
        ctx = self._make_context(critic_verdict="PASS")
        phase = PlanValidationPhase(ctx)
        gf, _, _ = phase.run("desc", "proj", tmp_path, "", {}, {}, [])
        report_content = gf.get("PLAN_VALIDATION_REPORT.json", "")
        parsed = json.loads(report_content)
        assert "final_verdict" in parsed
        assert "rounds" in parsed
