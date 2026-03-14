"""Unit tests for phase_groups.py — parallel phase grouping in AutoAgent pipeline."""

import pytest
from unittest.mock import MagicMock

from backend.agents.auto_agent_phases.phase_groups import (
    PhaseGroup,
    build_phase_groups,
    PARALLEL_VALIDATION_PHASES,
    PARALLEL_INFRA_PHASES,
    PARALLEL_ANALYSIS_PHASES,
)
from backend.interfaces.iagent_phase import IAgentPhase


def _make_phase(name: str) -> IAgentPhase:
    """Create a mock phase whose class name is *name*."""
    phase = MagicMock(spec=IAgentPhase)
    phase.__class__ = type(name, (object,), {})
    return phase


# ---------------------------------------------------------------------------
# build_phase_groups
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_phase_groups_validation_parallel():
    """Two consecutive validation phases become one parallel PhaseGroup."""
    phases = [_make_phase(n) for n in sorted(PARALLEL_VALIDATION_PHASES)]
    result = build_phase_groups(phases)

    assert len(result) == 1
    group = result[0]
    assert isinstance(group, PhaseGroup)
    assert group.parallel is True
    assert group.name == "Validation"
    assert len(group.phases) == 2


@pytest.mark.unit
def test_build_phase_groups_infra_parallel():
    """Two consecutive infra phases become one parallel PhaseGroup."""
    phases = [_make_phase(n) for n in sorted(PARALLEL_INFRA_PHASES)]
    result = build_phase_groups(phases)

    assert len(result) == 1
    group = result[0]
    assert isinstance(group, PhaseGroup)
    assert group.parallel is True
    assert group.name == "Infrastructure"


@pytest.mark.unit
def test_build_phase_groups_analysis_parallel():
    """Three consecutive analysis phases become one parallel PhaseGroup."""
    phases = [_make_phase(n) for n in sorted(PARALLEL_ANALYSIS_PHASES)]
    result = build_phase_groups(phases)

    assert len(result) == 1
    group = result[0]
    assert isinstance(group, PhaseGroup)
    assert group.parallel is True
    assert group.name == "Analysis"
    assert len(group.phases) == 3


@pytest.mark.unit
def test_build_phase_groups_single_phase_passthrough():
    """A phase that matches no group set is returned as-is (not wrapped)."""
    phase = _make_phase("ReadmeGenerationPhase")
    result = build_phase_groups([phase])

    assert len(result) == 1
    assert result[0] is phase  # same object, not wrapped in a PhaseGroup


@pytest.mark.unit
def test_build_phase_groups_single_validation_no_group():
    """A single validation phase alone is NOT wrapped (needs ≥2 for a group)."""
    phase = _make_phase(next(iter(PARALLEL_VALIDATION_PHASES)))
    result = build_phase_groups([phase])

    assert len(result) == 1
    assert not isinstance(result[0], PhaseGroup)


@pytest.mark.unit
def test_build_phase_groups_mixed_sequence():
    """Validation phases are grouped; surrounding non-matching phases are left alone."""
    phases = [
        _make_phase("ReadmeGenerationPhase"),
        *[_make_phase(n) for n in sorted(PARALLEL_VALIDATION_PHASES)],
        _make_phase("FinalReviewPhase"),
    ]
    result = build_phase_groups(phases)

    assert len(result) == 3
    assert not isinstance(result[0], PhaseGroup)  # ReadmeGenerationPhase
    assert isinstance(result[1], PhaseGroup)  # Validation group
    assert result[1].parallel is True
    assert not isinstance(result[2], PhaseGroup)  # FinalReviewPhase
