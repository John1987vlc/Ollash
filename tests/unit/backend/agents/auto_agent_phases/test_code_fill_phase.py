"""Unit tests for CodeFillPhase — M7, M8 improvements."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.code_fill_phase import CodeFillPhase, _STUB_PATTERNS
from backend.agents.auto_agent_phases.phase_context import FilePlan, PhaseContext


def _make_ctx(model_name: str = "qwen3-coder:30b") -> PhaseContext:
    mock_client = MagicMock()
    mock_client.model = model_name
    mock_llm = MagicMock()
    mock_llm.get_client.return_value = mock_client
    return PhaseContext(
        project_name="TestProject",
        project_description="A FastAPI web app",
        project_root=Path("/tmp/test_codefill"),
        llm_manager=mock_llm,
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )


def _plan(path: str, imports: list | None = None) -> FilePlan:
    return FilePlan(
        path=path,
        purpose=f"Test file {path}",
        exports=[],
        imports=imports or [],
        key_logic="test",
        priority=1,
    )


# ----------------------------------------------------------------
# M7 — _is_fastapi_entry_point
# ----------------------------------------------------------------


@pytest.mark.unit
def test_is_fastapi_entry_point_app_py():
    """M7: app.py in a FastAPI project → True."""
    ctx = _make_ctx()
    ctx.tech_stack = ["python", "fastapi", "sqlite"]
    assert CodeFillPhase._is_fastapi_entry_point(ctx, "app.py") is True


@pytest.mark.unit
def test_is_fastapi_entry_point_main_py():
    """M7: main.py in a FastAPI project → True."""
    ctx = _make_ctx()
    ctx.tech_stack = ["fastapi", "html"]
    assert CodeFillPhase._is_fastapi_entry_point(ctx, "main.py") is True


@pytest.mark.unit
def test_is_fastapi_entry_point_false_for_models_py():
    """M7: models.py in a FastAPI project → False (not an entry point)."""
    ctx = _make_ctx()
    ctx.tech_stack = ["python", "fastapi"]
    assert CodeFillPhase._is_fastapi_entry_point(ctx, "models.py") is False


@pytest.mark.unit
def test_is_fastapi_entry_point_false_without_fastapi():
    """M7: app.py in a Flask project → False (no FastAPI in stack)."""
    ctx = _make_ctx()
    ctx.tech_stack = ["python", "flask"]
    assert CodeFillPhase._is_fastapi_entry_point(ctx, "app.py") is False


@pytest.mark.unit
def test_is_fastapi_entry_point_nested_path():
    """M7: Works on a path like 'backend/app.py'."""
    ctx = _make_ctx()
    ctx.tech_stack = ["fastapi"]
    assert CodeFillPhase._is_fastapi_entry_point(ctx, "backend/app.py") is True


# ----------------------------------------------------------------
# M7 — _build_fastapi_mandatory_block
# ----------------------------------------------------------------


@pytest.mark.unit
def test_build_fastapi_mandatory_block_html_sqlite():
    """M7: With HTML and SQLite → block includes StaticFiles, startup, context manager."""
    block = CodeFillPhase._build_fastapi_mandatory_block(has_html=True, has_sqlite=True)
    assert "StaticFiles" in block
    assert "startup" in block
    assert "with sqlite3.connect" in block
    assert "/api/" in block  # list endpoint hint


@pytest.mark.unit
def test_build_fastapi_mandatory_block_html_no_sqlite():
    """M7: With HTML but no SQLite → block includes StaticFiles, no startup hint."""
    block = CodeFillPhase._build_fastapi_mandatory_block(has_html=True, has_sqlite=False)
    assert "StaticFiles" in block
    assert "startup" not in block


@pytest.mark.unit
def test_build_fastapi_mandatory_block_no_html():
    """M7: No HTML → no StaticFiles hint."""
    block = CodeFillPhase._build_fastapi_mandatory_block(has_html=False, has_sqlite=False)
    assert "StaticFiles" not in block
    assert "/api/" in block  # list endpoint hint still present


# ----------------------------------------------------------------
# M8 — _is_shared_js
# ----------------------------------------------------------------


@pytest.mark.unit
def test_is_shared_js_two_html_importers():
    """M8: JS imported by 2 HTML files → True."""
    ctx = _make_ctx()
    ctx.blueprint = [
        _plan("index.html", imports=["static/app.js"]),
        _plan("admin.html", imports=["static/app.js"]),
        _plan("static/app.js"),
    ]
    assert CodeFillPhase._is_shared_js(ctx, "static/app.js") is True


@pytest.mark.unit
def test_is_shared_js_false_single_importer():
    """M8: JS imported by only 1 HTML file → False."""
    ctx = _make_ctx()
    ctx.blueprint = [
        _plan("index.html", imports=["static/app.js"]),
        _plan("static/app.js"),
    ]
    assert CodeFillPhase._is_shared_js(ctx, "static/app.js") is False


@pytest.mark.unit
def test_is_shared_js_false_no_html():
    """M8: No HTML files in blueprint → False."""
    ctx = _make_ctx()
    ctx.blueprint = [
        _plan("models.py"),
        _plan("static/app.js"),
    ]
    assert CodeFillPhase._is_shared_js(ctx, "static/app.js") is False


@pytest.mark.unit
def test_is_shared_js_false_for_non_js():
    """M8: Non-JS file → always False."""
    ctx = _make_ctx()
    ctx.blueprint = [
        _plan("index.html", imports=["style.css"]),
        _plan("admin.html", imports=["style.css"]),
    ]
    assert CodeFillPhase._is_shared_js(ctx, "style.css") is False


@pytest.mark.unit
def test_is_shared_js_matches_by_filename():
    """M8: import listed as bare filename (not full path) → still detected."""
    ctx = _make_ctx()
    ctx.blueprint = [
        _plan("index.html", imports=["app.js"]),
        _plan("admin.html", imports=["app.js"]),
        _plan("static/app.js"),
    ]
    # The JS is at 'static/app.js' but HTML imports list 'app.js' (bare name match)
    assert CodeFillPhase._is_shared_js(ctx, "static/app.js") is True


# ----------------------------------------------------------------
# M7/M8 — _is_browser_js now includes python_app / api
# ----------------------------------------------------------------


@pytest.mark.unit
def test_is_browser_js_python_app():
    """Updated: python_app project with .js file → browser JS."""
    ctx = _make_ctx()
    ctx.project_type = "python_app"
    assert CodeFillPhase._is_browser_js(ctx, "static/app.js") is True


@pytest.mark.unit
def test_is_browser_js_api():
    """Updated: api project with .js file → browser JS."""
    ctx = _make_ctx()
    ctx.project_type = "api"
    assert CodeFillPhase._is_browser_js(ctx, "static/app.js") is True


# ----------------------------------------------------------------
# I4 — _STUB_PATTERNS: 5 new patterns
# ----------------------------------------------------------------


def _long_content(snippet: str) -> str:
    """Pad content to >30 lines so the 30-line guard doesn't suppress detection."""
    padding = "\n".join(f"# line {i}" for i in range(35))
    return padding + "\n" + snippet


@pytest.mark.unit
def test_stub_detection_ellipsis():
    """I4: bare ellipsis on its own line is detected as stub."""
    content = _long_content("def func():\n    ...\n")
    assert bool(_STUB_PATTERNS.search(content))


@pytest.mark.unit
def test_stub_detection_bare_pass():
    """I4: bare pass on its own line is detected as stub."""
    content = _long_content("def func():\n    pass\n")
    assert bool(_STUB_PATTERNS.search(content))


@pytest.mark.unit
def test_stub_detection_return_none():
    """I4: 'return None' as sole function body is detected as stub."""
    content = _long_content("def func():\n    return None\n")
    assert bool(_STUB_PATTERNS.search(content))


@pytest.mark.unit
def test_stub_detection_placeholder_comment():
    """I4: # Placeholder comment is detected as stub."""
    content = _long_content("def func():\n    # Placeholder implementation\n    pass\n")
    assert bool(_STUB_PATTERNS.search(content))


@pytest.mark.unit
def test_stub_detection_not_implemented_constant():
    """I4: NotImplemented constant (not exception) is detected as stub."""
    content = _long_content("def func():\n    return NotImplemented\n")
    assert bool(_STUB_PATTERNS.search(content))


@pytest.mark.unit
def test_stub_detection_short_file_not_flagged():
    """I4: The 30-line guard suppresses detection on tiny files."""
    short_content = "def func():\n    pass\n"
    # Only 2 lines — well under the 30-line guard threshold
    phase = CodeFillPhase()
    assert phase._detect_stubs(short_content, "main.py") is False
