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


# ----------------------------------------------------------------
# M5 — JS fetch() vs backend routes
# ----------------------------------------------------------------


@pytest.mark.unit
def test_detects_missing_api_route():
    """M5: JS calls /api/login but backend only has /admin/login → error detected."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": "<html></html>",
        "static/app.js": "fetch('/api/login', {method: 'POST'})",
        "app.py": "@app.post('/admin/login')\ndef login(): pass",
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_js_fetch_vs_routes(ctx)
    assert any(e["error_type"] == "missing_api_route" for e in errors), (
        "Expected missing_api_route error for /api/login vs /admin/login"
    )


@pytest.mark.unit
def test_no_error_when_route_exists():
    """M5: JS calls /api/bookings, backend has @app.get('/api/bookings') → no error."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "static/app.js": "fetch('/api/bookings')",
        "app.py": "@app.get('/api/bookings')\ndef list_bookings(): pass",
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_js_fetch_vs_routes(ctx)
    route_errors = [e for e in errors if e["error_type"] == "missing_api_route"]
    assert len(route_errors) == 0


@pytest.mark.unit
def test_normalize_route_path_numeric_segment():
    """M5: Numeric path segments normalized to {param}."""
    result = CrossFileValidationPhase._normalize_route_path("/api/bookings/123")
    assert result == "/api/bookings/{param}"


@pytest.mark.unit
def test_normalize_route_path_named_param():
    """M5: Named FastAPI path params normalized to {param}."""
    result = CrossFileValidationPhase._normalize_route_path("/api/bookings/{booking_id}")
    assert result == "/api/bookings/{param}"


@pytest.mark.unit
def test_normalize_route_path_trailing_slash_stripped():
    """M5: Trailing slashes are stripped."""
    result = CrossFileValidationPhase._normalize_route_path("/api/bookings/")
    assert result == "/api/bookings"


@pytest.mark.unit
def test_no_errors_when_no_backend_routes():
    """M5: No @app.get/post decorators in Python files → skip check (avoid false positives)."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "static/app.js": "fetch('/api/data')",
        "models.py": "class User:\n    pass",
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_js_fetch_vs_routes(ctx)
    assert len(errors) == 0, "No backend routes found → should skip without errors"


@pytest.mark.unit
def test_no_error_when_parameterized_route_matches():
    """M5: JS calls /api/bookings/42, backend has /api/bookings/{id} → normalized match."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "static/app.js": "fetch(`/api/bookings/${id}`)",  # template literal — skipped by regex
        "app.js": "fetch('/api/bookings/42')",
        "app.py": "@app.get('/api/bookings/{booking_id}')\ndef get_booking(): pass",
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_js_fetch_vs_routes(ctx)
    route_errors = [e for e in errors if e["error_type"] == "missing_api_route"]
    assert len(route_errors) == 0


# ----------------------------------------------------------------
# M6 — HTML form fields vs Pydantic models
# ----------------------------------------------------------------


@pytest.mark.unit
def test_detects_form_field_missing_from_model():
    """M6: HTML form has name='client_name', Pydantic model has 'name' → mismatch."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": (
            '<form action="/api/bookings" method="post"><input name="client_name"><input name="service"></form>'
        ),
        "app.py": ("class BookingCreate(BaseModel):\n    name: str\n    service: str\n"),
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_form_fields_vs_models(ctx)
    assert any(e["error_type"] == "form_field_mismatch" for e in errors), (
        "Expected form_field_mismatch for 'client_name' not in Pydantic model"
    )


@pytest.mark.unit
def test_no_error_when_fields_match():
    """M6: All HTML form fields match Pydantic model fields → no error."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": (
            '<form action="/api/bookings" method="post">'
            '<input name="name">'
            '<input name="service">'
            '<input name="date">'
            "</form>"
        ),
        "app.py": ("class BookingCreate(BaseModel):\n    name: str\n    service: str\n    date: str\n"),
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_form_fields_vs_models(ctx)
    mismatch_errors = [e for e in errors if e["error_type"] == "form_field_mismatch"]
    assert len(mismatch_errors) == 0


@pytest.mark.unit
def test_form_fields_ignores_csrf_token():
    """M6: csrf_token is excluded from mismatch checks."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": (
            '<form action="/api/login" method="post"><input name="csrf_token" value="x"><input name="username"></form>'
        ),
        "app.py": ("class LoginRequest(BaseModel):\n    username: str\n    password: str\n"),
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_form_fields_vs_models(ctx)
    # csrf_token should be ignored; username is present in model → no mismatch
    csrf_errors = [e for e in errors if "csrf_token" in e.get("description", "")]
    assert len(csrf_errors) == 0


@pytest.mark.unit
def test_form_fields_only_checks_api_action_forms():
    """M6: Forms without action='/api/...' are ignored."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "index.html": ('<form action="/search"><input name="completely_missing_field"></form>'),
        "app.py": "class SearchQuery(BaseModel):\n    q: str\n",
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_form_fields_vs_models(ctx)
    mismatch_errors = [e for e in errors if e["error_type"] == "form_field_mismatch"]
    assert len(mismatch_errors) == 0, "Non-/api/ forms should not be checked"


# ----------------------------------------------------------------
# Fix 5 — C# class reference consistency
# ----------------------------------------------------------------


@pytest.mark.unit
def test_csharp_detects_undefined_dbcontext_name():
    """Controller references 'CrmBasicoContext' but only 'CrmDbContext' is defined."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "Data/CrmDbContext.cs": "public class CrmDbContext : DbContext {}",
        "Controllers/ContactoController.cs": (
            "private readonly CrmBasicoContext _context;\n"
            "public ContactoController(CrmBasicoContext context) {}"
        ),
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_csharp_class_references(ctx)
    undefined = [e for e in errors if "CrmBasicoContext" in e["description"]]
    assert len(undefined) >= 1


@pytest.mark.unit
def test_csharp_no_error_when_type_matches():
    """Controller uses the correct DbContext name → no errors."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "Data/CrmDbContext.cs": "public class CrmDbContext : DbContext {}",
        "Controllers/ContactoController.cs": (
            "private readonly CrmDbContext _context;\n"
        ),
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_csharp_class_references(ctx)
    assert errors == []


@pytest.mark.unit
def test_csharp_bcl_types_not_flagged():
    """Known .NET BCL types like List, Task, IEnumerable must not be flagged."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "Services/ContactoService.cs": (
            "public class ContactoService {\n"
            "    private readonly List<string> _names = new List<string>();\n"
            "    public async Task<IEnumerable<string>> GetAll() => _names;\n"
            "}\n"
        ),
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_csharp_class_references(ctx)
    assert errors == []


@pytest.mark.unit
def test_csharp_interface_definition_not_flagged():
    """A class implementing a locally-defined interface must not be reported."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "Services/ContactoService.cs": (
            "public interface IContactoService {}\n"
            "public class ContactoService : IContactoService {}\n"
        ),
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_csharp_class_references(ctx)
    assert errors == []


@pytest.mark.unit
def test_csharp_deduplicates_errors_per_file():
    """Same undefined type referenced multiple times → reported only once per file."""
    ctx = _make_ctx()
    ctx.generated_files = {
        "Data/CrmDbContext.cs": "public class CrmDbContext {}",
        "Controllers/LeadController.cs": (
            "private readonly WrongContext _ctx;\n"
            "public LeadController(WrongContext ctx) {}\n"
            "private WrongContext _other;\n"
        ),
    }
    phase = CrossFileValidationPhase()
    errors = phase._check_csharp_class_references(ctx)
    wrong_ctx_errors = [e for e in errors if "WrongContext" in e["description"]]
    assert len(wrong_ctx_errors) == 1
