"""Plan Validation Phase — Architect vs Critic multi-agent debate.

After LogicPlanningPhase (and ApiContractPhase / TestPlanningPhase) this phase
instantiates two LLM roles:
  • **Critic** — reviews ``context.logic_plan`` for security vulnerabilities,
    performance bottlenecks, missing error handling, and architectural anti-patterns.
  • **Architect** — revises the plan to address the Critic's HIGH-severity findings.

The debate loops up to ``MAX_ROUNDS`` times.  If the Critic passes (no HIGH issues)
or if max rounds are reached, the validated plan replaces ``context.logic_plan``
and is written to ``PLAN_VALIDATION_REPORT.json``.

Only active on the **full** tier; skipped on slim/nano via ``_build_adaptive_phases``.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase


class PlanValidationPhase(BasePhase):
    """Phase 2.9: Architect vs Critic plan debate (full tier only)."""

    phase_id = "2.9"
    phase_label = "Plan Validation (Architect vs Critic)"
    MAX_ROUNDS = 3

    async def run(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],
        file_paths: List[str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        logic_plan = self.context.logic_plan
        if not logic_plan:
            self.context.logger.info(
                "[PlanValidation] No logic plan available — skipping."
            )
            return generated_files, initial_structure, file_paths

        current_plan = dict(logic_plan)
        report: Dict[str, Any] = {
            "rounds": [],
            "final_verdict": "pending",
            "total_rounds": 0,
        }

        for round_idx in range(1, self.MAX_ROUNDS + 1):
            self.context.logger.info(
                f"[PlanValidation] Round {round_idx}/{self.MAX_ROUNDS} — Critic reviewing plan..."
            )

            critique = await self._critic_review(current_plan, project_description)
            high_issues = [i for i in critique.get("issues", []) if i.get("severity") == "HIGH"]

            report["rounds"].append(
                {
                    "round": round_idx,
                    "issues_found": len(critique.get("issues", [])),
                    "high_severity": len(high_issues),
                    "verdict": critique.get("verdict", "UNKNOWN"),
                }
            )

            if not high_issues or critique.get("verdict") == "PASS":
                self.context.logger.info(
                    f"[PlanValidation] Critic PASSED on round {round_idx} "
                    f"({len(critique.get('issues', []))} total issue(s), 0 HIGH)."
                )
                report["final_verdict"] = "PASS"
                break

            self.context.logger.info(
                f"[PlanValidation] Critic found {len(high_issues)} HIGH issue(s) — asking Architect to revise."
            )

            revised_plan = await self._architect_revise(current_plan, high_issues, project_description)
            if revised_plan:
                current_plan = revised_plan
            else:
                self.context.logger.warning(
                    "[PlanValidation] Architect revision returned empty — keeping current plan."
                )

            if round_idx == self.MAX_ROUNDS:
                report["final_verdict"] = "MAX_ROUNDS_REACHED"
                self.context.logger.warning(
                    "[PlanValidation] Max rounds reached — proceeding with best available plan."
                )

        report["total_rounds"] = len(report["rounds"])

        # Update context with validated plan
        self.context.logic_plan = current_plan
        self.context.plan_validation_report = report

        # Write report to disk
        report_json = json.dumps(report, indent=2)
        self._write_file(
            project_root,
            "PLAN_VALIDATION_REPORT.json",
            report_json,
            generated_files,
            file_paths,
        )

        self.context.logger.info(
            f"[PlanValidation] Done. Verdict: {report['final_verdict']}. "
            f"Report saved to PLAN_VALIDATION_REPORT.json."
        )
        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _critic_review(
        self, logic_plan: Dict[str, Any], project_description: str
    ) -> Dict[str, Any]:
        """Invoke the Critic LLM to review the plan."""
        plan_summary = json.dumps(
            {k: {"purpose": v.get("purpose", ""), "main_logic": v.get("main_logic", [])}
             for k, v in list(logic_plan.items())[:25]},
            indent=2,
        )
        system_prompt = (
            "You are a senior security and architecture critic. "
            "Review the implementation plan below for: "
            "1) Security vulnerabilities (injection, insecure auth, data exposure), "
            "2) Performance bottlenecks (N+1 queries, missing pagination), "
            "3) Architectural anti-patterns (god objects, circular deps, tight coupling), "
            "4) Missing error handling. "
            "Return JSON: "
            '{"verdict": "PASS" | "FAIL", "issues": [{"severity": "HIGH"|"MEDIUM"|"LOW", '
            '"file": "...", "description": "..."}]}. '
            "Output ONLY the JSON object."
        )
        user_prompt = (
            f"## Project: {project_description[:800]}\n\n"
            f"## Plan:\n{plan_summary}"
        )

        default = {"verdict": "PASS", "issues": []}
        try:
            response_data, _ = self.context.llm_manager.get_client("planner").chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options_override={"temperature": 0.1},
            )
            parsed = self.context.response_parser.extract_json(
                response_data.get("content", "")
            )
            if isinstance(parsed, dict):
                return parsed
        except Exception as exc:
            self.context.logger.warning(f"[PlanValidation] Critic call failed: {exc}")
        return default

    async def _architect_revise(
        self,
        logic_plan: Dict[str, Any],
        high_issues: List[Dict[str, Any]],
        project_description: str,
    ) -> Dict[str, Any]:
        """Invoke the Architect LLM to revise the plan given HIGH-severity issues."""
        plan_json = json.dumps(logic_plan, indent=2)
        issues_json = json.dumps(high_issues, indent=2)

        system_prompt = (
            "You are a senior software architect. You have received a list of HIGH-severity "
            "issues with the implementation plan. Revise the plan to address all issues. "
            "Return ONLY the revised plan as a JSON object with the same structure "
            "(keys are file paths, values are plan dicts)."
        )
        user_prompt = (
            f"## Project: {project_description[:500]}\n\n"
            f"## HIGH-Severity Issues:\n{issues_json}\n\n"
            f"## Current Plan:\n{plan_json[:6000]}\n\n"
            "Return the revised plan JSON:"
        )

        try:
            response_data, _ = self.context.llm_manager.get_client("planner").chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options_override={"temperature": 0.2},
            )
            parsed = self.context.response_parser.extract_json(
                response_data.get("content", "")
            )
            if isinstance(parsed, dict) and parsed:
                return parsed
        except Exception as exc:
            self.context.logger.warning(f"[PlanValidation] Architect revision failed: {exc}")
        return {}
