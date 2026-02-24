"""
HITLPauseException — Signals that an agent needs human input to continue.

Any domain agent can raise this exception when it encounters ambiguity or
exhausts its autonomous decision-making capacity. The DomainAgentOrchestrator
catches it in ``_dispatch_task()`` and transitions the DAG node to
``TaskStatus.WAITING_FOR_USER`` without marking the task as failed.

The DAG continues executing all branches that do not depend on this node.
Once the user responds (via ``POST /api/hil/respond``), the orchestrator
calls ``dag.mark_unblocked()`` and the node re-enters the execution queue.

Usage (inside any domain agent's ``run()`` method)::

    if ambiguous_decision:
        raise HITLPauseException(
            question="Should the API use PostgreSQL or MongoDB?",
            context={"options": ["PostgreSQL", "MongoDB"], "task_id": node.id},
        )
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class HITLPauseException(Exception):
    """
    Raised by a domain agent to pause execution and request human input.

    Attributes:
        question: The natural-language question displayed to the user.
        context:  Optional metadata (choices, task_id, etc.) forwarded in the
                  ``hitl_requested`` SSE event so the frontend can render
                  rich UI (e.g. radio buttons instead of free-text input).
    """

    def __init__(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(question)
        self.question = question
        self.context: Dict[str, Any] = context or {}

    def __repr__(self) -> str:
        return f"HITLPauseException(question={self.question!r})"
