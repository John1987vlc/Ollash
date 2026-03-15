"""Unit tests for CrossFileValidationPhase."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.cross_file_validation_phase import CrossFileValidationPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


def _make_ctx(model_name: str = "qwen3-coder:30b") -> PhaseContext:
    mock_client = MagicMock()
    mock_client.model = model_name
    mock_llm = MagicMock()
    mock_llm.get_client.return_value = mock_client
    return PhaseContext(
        project_name="TestGame",
        project_description="A chess game in HTML/JS/CSS",
        project_root=Path("/tmp/test_crossfile"),
        llm_manager=mock_llm,
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )


# ----------------------------------------------------------------
# HTML ↔ JS ID contract
# ----------------------------------------------------------------


@pytest.mark.unit
def test_detects_id_mismatch_gebi():
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": '<div id="board"></div>',
        "game.js": 'document.getElementById("chess-board")',
    }
    CrossFileValidationPhase().run(ctx)
    total = ctx.metrics["cross_file_errors_found"]
    fixed = ctx.metrics["cross_file_errors_auto_fixed"]
    assert total >= 1, "Should detect at least one ID mismatch"
    # Either auto-fixed or pushed to cross_file_errors
    assert fixed + len(ctx.cross_file_errors) >= 1


@pytest.mark.unit
def test_auto_fixes_similar_id(tmp_path):
    """'chess-board' has high similarity to 'board' → auto-fix should update HTML."""
    ctx = _make_ctx()
    ctx.project_root = tmp_path
    ctx.generated_files = {
        "index.html": '<div id="board"></div>',
        "game.js": 'document.getElementById("chess-board")',
    }
    # Patch _write_file to update generated_files in memory without touching disk
    phase = CrossFileValidationPhase()
    written: dict = {}

    def fake_write(ctx_, rel, content):
        ctx_.generated_files[rel] = content
        written[rel] = content

    phase._write_file = fake_write

    phase.run(ctx)

    assert ctx.metrics["cross_file_errors_auto_fixed"] == 1
    # HTML should now have id="chess-board"
    html = ctx.generated_files.get("index.html", "")
    assert 'id="chess-board"' in html


@pytest.mark.unit
def test_no_errors_for_matching_ids():
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": '<div id="chess-board"></div>',
        "game.js": 'document.getElementById("chess-board")',
    }
    CrossFileValidationPhase().run(ctx)
    assert ctx.metrics["cross_file_errors_found"] == 0
    assert len(ctx.cross_file_errors) == 0


@pytest.mark.unit
def test_no_errors_for_querySelector_match():
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": '<div id="game-container"></div>',
        "app.js": 'document.querySelector("#game-container")',
    }
    CrossFileValidationPhase().run(ctx)
    assert ctx.metrics["cross_file_errors_found"] == 0


@pytest.mark.unit
def test_unfixable_id_goes_to_cross_file_errors():
    """IDs that are too dissimilar cannot be auto-fixed — they go to cross_file_errors."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": '<div id="container"></div>',
        "game.js": 'document.getElementById("completely-different-xyz")',
    }
    CrossFileValidationPhase().run(ctx)
    assert ctx.metrics["cross_file_errors_auto_fixed"] == 0
    assert len(ctx.cross_file_errors) >= 1
    err = ctx.cross_file_errors[0]
    assert err["error_type"] == "id_mismatch"


@pytest.mark.unit
def test_handles_empty_generated_files():
    """Phase must not raise when generated_files is empty."""
    ctx = _make_ctx()
    ctx.generated_files = {}
    CrossFileValidationPhase().run(ctx)  # must not raise


@pytest.mark.unit
def test_handles_no_js_files():
    """HTML only — no JS → no ID mismatch errors."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": '<div id="board"></div>',
        "style.css": ".board { color: red; }",
    }
    CrossFileValidationPhase().run(ctx)
    # No ID mismatch errors expected (no JS)
    id_errors = [e for e in ctx.cross_file_errors if e.get("error_type") == "id_mismatch"]
    assert len(id_errors) == 0


# ----------------------------------------------------------------
# HTML ↔ CSS class contract
# ----------------------------------------------------------------


@pytest.mark.unit
def test_detects_missing_css_class():
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": '<div class="game-board"></div>',
        "style.css": ".other-class { color: red; }",
        "app.js": "",
    }
    CrossFileValidationPhase().run(ctx)
    css_errors = [e for e in ctx.cross_file_errors if e.get("error_type") == "missing_css_class"]
    assert len(css_errors) >= 1
    assert "game-board" in css_errors[0]["description"]


@pytest.mark.unit
def test_no_css_error_when_class_defined():
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": '<div class="game-board"></div>',
        "style.css": ".game-board { display: flex; }",
        "app.js": "",
    }
    CrossFileValidationPhase().run(ctx)
    css_errors = [e for e in ctx.cross_file_errors if e.get("error_type") == "missing_css_class"]
    assert len(css_errors) == 0


# ----------------------------------------------------------------
# Python relative imports
# ----------------------------------------------------------------


@pytest.mark.unit
def test_detects_missing_python_import_name():
    ctx = _make_ctx()
    ctx.generated_files = {
        "src/main.py": "from .utils import missing_function\n",
        "src/utils.py": "def existing_function(): pass\n",
    }
    CrossFileValidationPhase().run(ctx)
    py_errors = [e for e in ctx.cross_file_errors if e.get("error_type") == "missing_import_name"]
    assert len(py_errors) >= 1
    assert "missing_function" in py_errors[0]["description"]


@pytest.mark.unit
def test_no_python_error_when_name_exists():
    ctx = _make_ctx()
    ctx.generated_files = {
        "src/main.py": "from .utils import helper\n",
        "src/utils.py": "def helper(): pass\n",
    }
    CrossFileValidationPhase().run(ctx)
    py_errors = [e for e in ctx.cross_file_errors if e.get("error_type") == "missing_import_name"]
    assert len(py_errors) == 0


# ----------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------


@pytest.mark.unit
def test_metrics_are_always_set():
    """cross_file_errors_found and auto_fixed should be set even with no errors."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": '<div id="x"></div>',
        "game.js": 'document.getElementById("x")',
    }
    CrossFileValidationPhase().run(ctx)
    assert "cross_file_errors_found" in ctx.metrics
    assert "cross_file_errors_auto_fixed" in ctx.metrics


@pytest.mark.unit
def test_internal_tracking_keys_stripped_from_cross_file_errors():
    """_js_ref and _html_ids must not appear in ctx.cross_file_errors."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": '<div id="container"></div>',
        "game.js": 'document.getElementById("xyz-completely-different")',
    }
    CrossFileValidationPhase().run(ctx)
    for err in ctx.cross_file_errors:
        for key in err:
            assert not key.startswith("_"), f"Internal key '{key}' leaked into cross_file_errors"
