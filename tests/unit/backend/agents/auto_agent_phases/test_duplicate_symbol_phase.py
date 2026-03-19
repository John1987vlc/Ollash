"""Unit tests for DuplicateSymbolPhase (Sprint 19 — phase 4d)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.duplicate_symbol_phase import DuplicateSymbolPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


def _make_ctx(model_name: str = "qwen3-coder:30b") -> PhaseContext:
    mock_client = MagicMock()
    mock_client.model = model_name
    mock_llm = MagicMock()
    mock_llm.get_client.return_value = mock_client
    ctx = PhaseContext(
        project_name="TestProject",
        project_description="A poker game",
        project_root=Path("/tmp/test_dup_sym"),
        llm_manager=mock_llm,
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )
    ctx.blueprint = []
    return ctx


# ----------------------------------------------------------------
# JS — no duplicates
# ----------------------------------------------------------------


@pytest.mark.unit
def test_js_no_duplicates():
    """File with unique symbols → no changes, empty js_cleaned dict."""
    ctx = _make_ctx()
    ctx.generated_files = {"game.js": "function init() {}\nfunction update() {}\nfunction render() {}"}

    write_calls = []
    phase = DuplicateSymbolPhase()
    phase._write_file = lambda ctx, path, content: write_calls.append((path, content))
    phase.run(ctx)

    assert ctx.metrics["duplicate_symbols"]["js_cleaned"] == {}
    assert write_calls == []


# ----------------------------------------------------------------
# JS — duplicate function removed
# ----------------------------------------------------------------


@pytest.mark.unit
def test_js_duplicate_function():
    """Two 'function init' declarations → second removed."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "game.js": (
            "function init() {\n"
            "  console.log('full init');\n"
            "}\n"
            "\n"
            "function update() {}\n"
            "\n"
            "function init() {\n"
            "  // stub\n"
            "}\n"
        )
    }

    write_calls = []
    phase = DuplicateSymbolPhase()
    phase._write_file = lambda ctx, path, content: write_calls.append((path, content))
    phase.run(ctx)

    assert "init" in ctx.metrics["duplicate_symbols"]["js_cleaned"].get("game.js", [])
    assert write_calls  # file was rewritten
    # The written content should NOT contain the stub second occurrence
    written_content = write_calls[0][1]
    assert written_content.count("function init") == 1


# ----------------------------------------------------------------
# JS — duplicate window.* assignment removed
# ----------------------------------------------------------------


@pytest.mark.unit
def test_js_duplicate_window_assign():
    """window.game = ... declared twice → second removed."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "main.js": (
            "window.game = function() { return 42; };\n"
            "window.other = 1;\n"
            "window.game = function() {};\n"  # stub duplicate
        )
    }

    write_calls = []
    phase = DuplicateSymbolPhase()
    phase._write_file = lambda ctx, path, content: write_calls.append((path, content))
    phase.run(ctx)

    js_cleaned = ctx.metrics["duplicate_symbols"]["js_cleaned"]
    assert "main.js" in js_cleaned
    written_content = write_calls[0][1]
    assert written_content.count("window.game") == 1


# ----------------------------------------------------------------
# JS — conditional guard prevents removal
# ----------------------------------------------------------------


@pytest.mark.unit
def test_js_guard_skipped():
    """Second occurrence guarded by typeof check → NOT removed."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "util.js": (
            "function helper() { return 1; }\n"
            "\n"
            "if (typeof helper === 'undefined') {\n"
            "function helper() { return 2; }\n"
            "}\n"
        )
    }

    write_calls = []
    phase = DuplicateSymbolPhase()
    phase._write_file = lambda ctx, path, content: write_calls.append((path, content))
    phase.run(ctx)

    # No write — the guarded occurrence was preserved
    assert write_calls == []


# ----------------------------------------------------------------
# Python deduplication
# ----------------------------------------------------------------


@pytest.mark.unit
def test_py_duplicate_function():
    """Two 'def process_data' in .py → deduplicate_python_content applied."""
    ctx = _make_ctx()
    content = (
        "def process_data(x):\n"
        "    return x * 2\n"
        "\n"
        "def other():\n"
        "    pass\n"
        "\n"
        "def process_data(x):\n"  # duplicate
        "    pass\n"
    )
    ctx.generated_files = {"utils.py": content}

    write_calls = []
    phase = DuplicateSymbolPhase()
    phase._write_file = lambda ctx, path, c: write_calls.append((path, c))
    phase.run(ctx)

    # File should be rewritten
    assert write_calls
    written = write_calls[0][1]
    # deduplicate_python_content keeps the LAST definition
    assert written.count("def process_data") == 1


@pytest.mark.unit
def test_py_already_deduplicated():
    """File in ctx.metrics['deduplication_applied'] → skipped."""
    ctx = _make_ctx()
    content = "def foo():\n    pass\ndef foo():\n    return 1\n"
    ctx.generated_files = {"app.py": content}
    ctx.metrics["deduplication_applied"] = {"app.py": True}

    write_calls = []
    phase = DuplicateSymbolPhase()
    phase._write_file = lambda ctx, path, c: write_calls.append((path, c))
    phase.run(ctx)

    # Should be skipped — no write
    assert write_calls == []


# ----------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------


@pytest.mark.unit
def test_metrics_recorded():
    """ctx.metrics['duplicate_symbols'] always has js_cleaned and py_cleaned keys."""
    ctx = _make_ctx()
    ctx.generated_files = {"index.js": "function foo() {}"}
    DuplicateSymbolPhase().run(ctx)
    m = ctx.metrics["duplicate_symbols"]
    assert "js_cleaned" in m
    assert "py_cleaned" in m


# ----------------------------------------------------------------
# Non-fatal on exception
# ----------------------------------------------------------------


@pytest.mark.unit
def test_non_fatal_on_exception():
    """An arbitrary exception inside run() is caught; phase completes without raising."""
    ctx = _make_ctx()
    ctx.generated_files = None  # will cause TypeError when iterating

    # Should not raise
    DuplicateSymbolPhase().run(ctx)


# ----------------------------------------------------------------
# _write_file called when duplicate removed
# ----------------------------------------------------------------


@pytest.mark.unit
def test_cleaned_file_written_to_disk():
    """When a JS duplicate is removed, _write_file is called with the cleaned content."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "app.js": ("function setup() { return 1; }\nfunction run() {}\nfunction setup() { /* stub */ }\n")
    }

    written = {}
    phase = DuplicateSymbolPhase()
    phase._write_file = lambda ctx, path, content: written.update({path: content})
    phase.run(ctx)

    assert "app.js" in written
    assert written["app.js"].count("function setup") == 1
