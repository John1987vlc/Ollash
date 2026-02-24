"""
ActiveOrchestrators — Thread-safe singleton registry of running DomainAgentOrchestrators.

The HIL blueprint (``hil_bp.py``) uses this registry to look up the live
orchestrator for a project so it can call ``dag.mark_unblocked(task_id, answer)``
when the user responds to a HITL request.

Design:
    - Simple dict protected by a threading.Lock (not asyncio.Lock because the
      Flask blueprint routes run in a WSGI thread, not the asyncio event loop).
    - Orchestrators register themselves at the start of ``run()`` and deregister
      on completion or error.

Usage::

    # In DomainAgentOrchestrator.run():
    ActiveOrchestrators.register(project_name, self)
    try:
        ...
    finally:
        ActiveOrchestrators.deregister(project_name)

    # In hil_bp.py:
    orchestrator = ActiveOrchestrators.get(project_name)
    if orchestrator:
        dag = orchestrator.get_dag()
        await dag.mark_unblocked(task_id, answer)
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from backend.agents.domain_agent_orchestrator import DomainAgentOrchestrator


class ActiveOrchestrators:
    """Thread-safe global registry of running DomainAgentOrchestrator instances."""

    _lock: threading.Lock = threading.Lock()
    _registry: Dict[str, "DomainAgentOrchestrator"] = {}

    @classmethod
    def register(cls, project_name: str, orchestrator: "DomainAgentOrchestrator") -> None:
        """Register an orchestrator for the given project."""
        with cls._lock:
            cls._registry[project_name] = orchestrator

    @classmethod
    def deregister(cls, project_name: str) -> None:
        """Remove an orchestrator from the registry."""
        with cls._lock:
            cls._registry.pop(project_name, None)

    @classmethod
    def get(cls, project_name: str) -> Optional["DomainAgentOrchestrator"]:
        """Return the live orchestrator for *project_name*, or None."""
        with cls._lock:
            return cls._registry.get(project_name)

    @classmethod
    def list_active(cls) -> Dict[str, "DomainAgentOrchestrator"]:
        """Return a shallow copy of the registry."""
        with cls._lock:
            return dict(cls._registry)
