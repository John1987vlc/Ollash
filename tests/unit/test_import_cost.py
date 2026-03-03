"""Regression tests: importing core modules must not load heavy packages.

These tests run in a subprocess so they get a clean sys.modules and cannot
be affected by other test fixtures that may have already imported chromadb
or SQLAlchemy.
"""

import subprocess
import sys

import pytest


def _check(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )


@pytest.mark.unit
def test_phase_context_does_not_load_chromadb():
    """Importing phase_context must not load chromadb (866 modules)."""
    result = _check(
        "import backend.agents.auto_agent_phases.phase_context; "
        "import sys; "
        "assert 'chromadb' not in sys.modules, "
        "f'chromadb loaded by phase_context: {[m for m in sys.modules if \"chromadb\" in m][:5]}'"
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.unit
def test_rag_context_selector_does_not_load_chromadb_at_import():
    """Importing RAGContextSelector must not load chromadb until __init__ is called."""
    result = _check(
        "from backend.utils.core.analysis.scanners.rag_context_selector import RAGContextSelector; "
        "import sys; "
        "assert 'chromadb' not in sys.modules, "
        "f'chromadb loaded at import time: {[m for m in sys.modules if \"chromadb\" in m][:5]}'"
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.unit
def test_phase_context_module_count_under_threshold():
    """Importing phase_context should load fewer than 100 modules (was 1567)."""
    result = _check(
        "import sys; "
        "before = set(sys.modules); "
        "import backend.agents.auto_agent_phases.phase_context; "
        "count = len(set(sys.modules) - before); "
        "assert count < 100, f'phase_context loaded {count} modules (threshold: 100)'"
    )
    assert result.returncode == 0, result.stderr
