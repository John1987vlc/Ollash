"""IAgentPhaseV2 — new phase interface for the 8-phase AutoAgent pipeline.

Key difference from IAgentPhase (v1):
- execute(ctx: PhaseContext) -> None  (mutates context in place)
- No 3-tuple return value
- No positional args (project_description, project_name, etc.)

The old IAgentPhase is kept unchanged for DomainAgentOrchestrator backward compatibility.
"""
from abc import ABC, abstractmethod

from backend.agents.auto_agent_phases.phase_context import PhaseContext


class IAgentPhaseV2(ABC):
    """Abstract base class for all v2 AutoAgent pipeline phases."""

    @abstractmethod
    def execute(self, ctx: PhaseContext) -> None:
        """Execute the phase logic. Mutates ctx in place. Returns nothing."""
        pass

    @abstractmethod
    def run(self, ctx: PhaseContext) -> None:
        """Core phase logic. Called by execute(). Raises on unrecoverable failure."""
        pass
