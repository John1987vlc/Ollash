"""Unit tests for PatchPhase — M1, M9, M10 improvements."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.patch_phase import PatchPhase, _CONTENT_INCLUDE_MAX_CHARS
from backend.agents.auto_agent_phases.phase_context import PhaseContext


def _make_ctx(model_name: str = "qwen3-coder:30b") -> PhaseContext:
    mock_client = MagicMock()
    mock_client.model = model_name
    mock_llm = MagicMock()
    mock_llm.get_client.return_value = mock_client
    return PhaseContext(
        project_name="TestProject",
        project_description="A FastAPI web app with SQLite",
        project_root=Path("/tmp/test_patch"),
        llm_manager=mock_llm,
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
    )


# ----------------------------------------------------------------
# M1 — Content inclusion threshold raised to 25k
# ----------------------------------------------------------------


@pytest.mark.unit
def test_content_include_max_chars_is_25k():
    """M1: threshold must be 25_000 (was 8_000)."""
    assert _CONTENT_INCLUDE_MAX_CHARS == 25_000


@pytest.mark.unit
def test_should_include_content_with_25k_chars():
    """M1: 5 files × ~4k chars each (≤25k total) → should_include_content returns True."""
    ctx = _make_ctx()
    # 5 files of ~4k chars each = ~20k total < 25k limit
    for i in range(5):
        ctx.generated_files[f"file{i}.py"] = "x" * 4_000
    assert PatchPhase._should_include_content(ctx) is True


@pytest.mark.unit
def test_should_not_include_content_above_threshold():
    """M1: total chars > 25k → should_include_content returns False."""
    ctx = _make_ctx()
    for i in range(5):
        ctx.generated_files[f"file{i}.py"] = "x" * 6_000  # 30k total
    assert PatchPhase._should_include_content(ctx) is False


@pytest.mark.unit
def test_should_not_include_content_too_many_files():
    """More than 6 files → should_include_content returns False regardless of size."""
    ctx = _make_ctx()
    for i in range(7):
        ctx.generated_files[f"file{i}.py"] = "small"
    assert PatchPhase._should_include_content(ctx) is False


# ----------------------------------------------------------------
# M9 — _build_patch_context
# ----------------------------------------------------------------


@pytest.mark.unit
def test_build_patch_context_html_small_includes_content():
    """M9: HTML file ≤5000 chars → context includes the full HTML."""
    ctx = _make_ctx()
    html_content = "<html><body><p>Hello</p></body></html>"
    result = PatchPhase._build_patch_context(ctx, "index.html", html_content)
    assert "COMPLETE HTML:" in result
    assert html_content in result


@pytest.mark.unit
def test_build_patch_context_html_large_no_content():
    """M9: HTML file > 5000 chars → falls back to project description."""
    ctx = _make_ctx()
    large_html = "<html>" + "x" * 5_001 + "</html>"
    result = PatchPhase._build_patch_context(ctx, "index.html", large_html)
    assert "COMPLETE HTML:" not in result
    assert "FastAPI web app" in result


@pytest.mark.unit
def test_build_patch_context_non_html():
    """M9: Non-HTML file always returns project description."""
    ctx = _make_ctx()
    result = PatchPhase._build_patch_context(ctx, "app.py", "def main(): pass")
    assert "COMPLETE HTML:" not in result
    assert "FastAPI web app" in result


# ----------------------------------------------------------------
# M10 — _check_python_connection_bugs
# ----------------------------------------------------------------


@pytest.mark.unit
def test_detects_use_after_close():
    """M10: conn.close() followed by cursor.execute() → USE_AFTER_CLOSE error."""
    ctx = _make_ctx()
    ctx.generated_files["app.py"] = (
        "def cancel_booking(id):\n"
        "    conn = sqlite3.connect('db')\n"
        "    cursor = conn.cursor()\n"
        "    conn.close()\n"
        "    cursor.execute('DELETE FROM bookings WHERE id = ?', (id,))\n"
        "    conn.commit()\n"
    )
    errors = PatchPhase._check_python_connection_bugs(ctx)
    assert any("USE_AFTER_CLOSE" in e["error"] for e in errors), "Expected USE_AFTER_CLOSE error"


@pytest.mark.unit
def test_no_error_with_context_manager():
    """M10: Using 'with sqlite3.connect() as conn:' → no error."""
    ctx = _make_ctx()
    ctx.generated_files["app.py"] = (
        "def get_bookings():\n"
        "    with sqlite3.connect('db') as conn:\n"
        "        cursor = conn.cursor()\n"
        "        cursor.execute('SELECT * FROM bookings')\n"
        "        return cursor.fetchall()\n"
    )
    errors = PatchPhase._check_python_connection_bugs(ctx)
    use_after = [e for e in errors if "USE_AFTER_CLOSE" in e["error"]]
    assert len(use_after) == 0


@pytest.mark.unit
def test_detects_db_init_only_in_main():
    """M10: init_db() only called in __main__ guard → INIT_DB_ONLY_IN_MAIN error."""
    ctx = _make_ctx()
    ctx.generated_files["app.py"] = (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "\n"
        "def init_db():\n"
        "    pass\n"
        "\n"
        "@app.get('/items')\n"
        "def get_items():\n"
        "    return []\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    init_db()\n"
        "    import uvicorn\n"
        "    uvicorn.run(app)\n"
    )
    errors = PatchPhase._check_python_connection_bugs(ctx)
    assert any("INIT_DB_ONLY_IN_MAIN" in e["error"] for e in errors), "Expected INIT_DB_ONLY_IN_MAIN error"


@pytest.mark.unit
def test_no_init_db_error_with_startup_event():
    """M10: init_db() called in @app.on_event('startup') → no error."""
    ctx = _make_ctx()
    ctx.generated_files["app.py"] = (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "\n"
        "def init_db():\n"
        "    pass\n"
        "\n"
        "@app.on_event('startup')\n"
        "async def startup():\n"
        "    init_db()\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    import uvicorn\n"
        "    uvicorn.run(app)\n"
    )
    errors = PatchPhase._check_python_connection_bugs(ctx)
    init_errors = [e for e in errors if "INIT_DB_ONLY_IN_MAIN" in e["error"]]
    assert len(init_errors) == 0


@pytest.mark.unit
def test_no_connection_bugs_in_non_python_files():
    """M10: Only .py files are checked — JS/HTML not scanned."""
    ctx = _make_ctx()
    ctx.generated_files["index.html"] = "<div>conn.close()</div>"
    ctx.generated_files["app.js"] = "conn.close(); cursor.execute();"
    errors = PatchPhase._check_python_connection_bugs(ctx)
    assert len(errors) == 0
