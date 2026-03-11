"""Clarification Phase — interactively refines the project description.

Uses an LLM to detect critical ambiguities in the project description
(missing DB, auth strategy, business rules, external APIs, deployment target).
Up to 5 targeted questions are sent to the user via EventPublisher before
planning begins. Answers are stored on PhaseContext so all subsequent phases
can see the enriched description.
"""

import asyncio
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase


class ClarificationPhase(BasePhase):
    """Phase 0: Interactive Requirements Gathering.

    Activated for all model tiers. When the description already contains
    sufficient detail (e.g. DB name, auth mechanism), the LLM returns an
    empty question list and the phase completes instantly.
    """

    phase_id = "0"
    phase_label = "Interactive Clarification"
    _MAX_QUESTIONS = 5
    _TIMEOUT_SECONDS = 300

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
        questions = await self._analyse_completeness(project_description)

        if not questions:
            self.context.logger.info("[Clarification] Description is sufficiently detailed — no questions needed.")
            return generated_files, initial_structure, file_paths

        self.context.logger.info(f"[Clarification] {len(questions)} critical question(s) detected.")

        answers: Dict[str, str] = {}
        for q in questions[: self._MAX_QUESTIONS]:
            answer = await self._ask_user(q)
            if answer:
                answers[q] = answer
                self.context.logger.info(f"  ✓ Q: {q[:80]!r}  A: {answer[:60]!r}")

        if answers:
            qa_block = "\n".join(f"- {q}: {a}" for q, a in answers.items())
            enriched = f"{project_description}\n\n## Clarifications\n{qa_block}"
            self.context.clarification_answers = answers
            self.context.clarified_description = enriched
            # Signal enriched description to AutoAgent via generated_files key
            generated_files["__clarified_description__"] = enriched
            self.context.logger.info(f"[Clarification] Description enriched with {len(answers)} answer(s).")

        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _analyse_completeness(self, project_description: str) -> List[str]:
        """Return up to 5 critical questions if the description is incomplete."""
        system_prompt = (
            "You are a senior software requirements analyst. "
            "Evaluate whether the project description below is sufficiently detailed "
            "to start building production software. "
            "Identify up to 5 CRITICAL missing pieces such as: "
            "database engine, authentication mechanism, external API dependencies, "
            "business rules, deployment target, or performance requirements. "
            "Return a JSON array of concise questions (plain strings). "
            "Return an EMPTY ARRAY [] if the description is already detailed enough. "
            "Output only the JSON array, no prose."
        )
        user_prompt = f"## Project Description\n{project_description}"

        try:
            response_data, _ = self.context.llm_manager.get_client("planner").chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options_override={"temperature": 0.1},
            )
            raw = response_data.get("content", "")
            parsed = self.context.response_parser.extract_json(raw)
            if isinstance(parsed, list):
                return [str(q).strip() for q in parsed if q]
        except Exception as exc:
            self.context.logger.warning(f"[Clarification] Completeness analysis failed (non-fatal): {exc}")
        return []

    async def _ask_user(self, question: str) -> str:
        """Dispatch one clarification question to the user."""
        req_id = str(uuid.uuid4())[:8]
        event_publisher = self.context.event_publisher

        # F31: Check if there's actually someone listening to our request
        # If no one is subscribed to clarification_request, it's likely a non-interactive CLI run.
        if not event_publisher.has_subscribers("clarification_request"):
            self.context.logger.info(
                f"[Clarification] No active UI/Subscribers detected. Skipping question: {question[:50]}..."
            )
            return ""

        event = asyncio.Event()
        answer_holder: Dict[str, str] = {"answer": ""}

        def _on_response(event_type: str, event_data: Dict) -> None:
            if event_data.get("request_id") == req_id:
                answer_holder["answer"] = str(event_data.get("answer", ""))
                event.set()

        try:
            event_publisher.subscribe("clarification_response", _on_response)
            await event_publisher.publish(
                "clarification_request",
                request_id=req_id,
                question=question,
            )
            self.context.logger.info(f"[Clarification] Waiting for answer (id={req_id}): {question[:80]!r}")
            try:
                await asyncio.wait_for(event.wait(), timeout=self._TIMEOUT_SECONDS)
                return answer_holder["answer"].strip()
            except asyncio.TimeoutError:
                self.context.logger.warning(
                    f"[Clarification] Question timed out (id={req_id}). Proceeding without answer."
                )
                return ""
        except Exception as exc:
            self.context.logger.debug(f"[Clarification] _ask_user error: {exc}")
            return ""
        finally:
            try:
                event_publisher.unsubscribe("clarification_response", _on_response)
            except Exception:
                pass
