"""AutoAgent phases package — 8-phase pipeline optimized for 4B models.

Phases are imported lazily (inside AutoAgent.run()) to keep module load cost low.
This __init__.py only exports what external code needs at import time.
"""

from backend.agents.auto_agent_phases.phase_context import FilePlan, PhaseContext
from backend.agents.auto_agent_phases.base_phase import BasePhase

__all__ = ["FilePlan", "PhaseContext", "BasePhase"]
