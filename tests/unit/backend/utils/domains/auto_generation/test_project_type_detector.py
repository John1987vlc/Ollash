"""Unit tests for ProjectTypeDetector.

Tests cover:
- Detection of frontend_web, python_app, react_app, go_service, rust_project, node_backend
- Unknown fallback when confidence < 0.10
- README content boosts detection accuracy
- Extension whitelist correctness
- get_forbidden_extensions_text helper
"""

import pytest

from backend.utils.domains.auto_generation.project_type_detector import (
    ProjectTypeDetector,
    ProjectTypeInfo,
)


# ---------------------------------------------------------------------------
# Tests: detect()
# ---------------------------------------------------------------------------


class TestProjectTypeDetectorDetect:
    @pytest.mark.unit
    def test_pure_html_css_js_description_detects_frontend_web(self):
        info = ProjectTypeDetector.detect("pure HTML/CSS/JS/SVG Texas Hold'em poker game")
        assert info.project_type == "frontend_web"
        assert ".py" not in info.allowed_extensions
        assert ".html" in info.allowed_extensions
        assert ".js" in info.allowed_extensions
        assert ".css" in info.allowed_extensions
        assert ".svg" in info.allowed_extensions

    @pytest.mark.unit
    def test_no_backend_keyword_detects_frontend_web(self):
        info = ProjectTypeDetector.detect("A landing page with animations, no backend, no server")
        assert info.project_type == "frontend_web"

    @pytest.mark.unit
    def test_vanilla_js_detects_frontend_web(self):
        info = ProjectTypeDetector.detect("todo app built in vanilla JS with CSS")
        assert info.project_type == "frontend_web"

    @pytest.mark.unit
    def test_python_flask_detects_python_app(self):
        info = ProjectTypeDetector.detect("REST API built with Python Flask and SQLAlchemy")
        assert info.project_type == "python_app"
        assert ".py" in info.allowed_extensions

    @pytest.mark.unit
    def test_django_detects_python_app(self):
        info = ProjectTypeDetector.detect("E-commerce platform using Django with PostgreSQL")
        assert info.project_type == "python_app"

    @pytest.mark.unit
    def test_fastapi_detects_python_app(self):
        info = ProjectTypeDetector.detect("FastAPI microservice with async endpoints")
        assert info.project_type == "python_app"

    @pytest.mark.unit
    def test_react_description_detects_react_app(self):
        info = ProjectTypeDetector.detect("Single-page application built with React and JSX")
        assert info.project_type == "react_app"
        assert ".jsx" in info.allowed_extensions

    @pytest.mark.unit
    def test_nextjs_detects_react_app(self):
        info = ProjectTypeDetector.detect("Blog built with Next.js and Vite")
        assert info.project_type == "react_app"

    @pytest.mark.unit
    def test_typescript_detects_typescript_app(self):
        info = ProjectTypeDetector.detect("Angular app using TypeScript with tsconfig")
        assert info.project_type == "typescript_app"
        assert ".ts" in info.allowed_extensions

    @pytest.mark.unit
    def test_golang_detects_go_service(self):
        info = ProjectTypeDetector.detect("golang REST API microservice")
        assert info.project_type == "go_service"
        assert ".go" in info.allowed_extensions
        assert ".py" not in info.allowed_extensions

    @pytest.mark.unit
    def test_go_mod_keyword_detects_go_service(self):
        info = ProjectTypeDetector.detect("Go service with go.mod and gorilla mux")
        assert info.project_type == "go_service"

    @pytest.mark.unit
    def test_rust_cargo_detects_rust_project(self):
        info = ProjectTypeDetector.detect("Command-line tool in Rust using Cargo")
        assert info.project_type == "rust_project"
        assert ".rs" in info.allowed_extensions

    @pytest.mark.unit
    def test_express_detects_node_backend(self):
        info = ProjectTypeDetector.detect("Node.js Express REST API with middleware")
        assert info.project_type == "node_backend"

    @pytest.mark.unit
    def test_vague_description_returns_unknown(self):
        info = ProjectTypeDetector.detect("Build something great and innovative")
        assert info.project_type == "unknown"
        assert info.confidence < 0.10
        # Universal extensions should include common types
        assert ".py" in info.allowed_extensions
        assert ".js" in info.allowed_extensions

    @pytest.mark.unit
    def test_empty_description_returns_unknown(self):
        info = ProjectTypeDetector.detect("")
        assert info.project_type == "unknown"
        assert info.confidence == 0.0
        assert len(info.allowed_extensions) > 0

    @pytest.mark.unit
    def test_readme_content_boosts_detection(self):
        """A brief description + detailed README should still detect the right type."""
        brief_desc = "My project"
        readme = (
            "## Tech Stack\n- HTML5\n- CSS3\n- Vanilla JavaScript\n- SVG animations\n"
            "This is a pure frontend SPA with no backend."
        )
        info = ProjectTypeDetector.detect(brief_desc, readme)
        assert info.project_type == "frontend_web"

    @pytest.mark.unit
    def test_confidence_in_valid_range(self):
        info = ProjectTypeDetector.detect("React single-page application with JSX hooks and Vite")
        assert 0.0 <= info.confidence <= 1.0

    @pytest.mark.unit
    def test_detected_keywords_populated(self):
        info = ProjectTypeDetector.detect("golang REST API go service with go.mod")
        assert len(info.detected_keywords) > 0

    @pytest.mark.unit
    def test_detected_keywords_empty_for_unknown(self):
        info = ProjectTypeDetector.detect("")
        assert info.detected_keywords == []

    @pytest.mark.unit
    def test_return_type_is_project_type_info(self):
        info = ProjectTypeDetector.detect("Python Flask API")
        assert isinstance(info, ProjectTypeInfo)

    @pytest.mark.unit
    def test_allowed_extensions_is_frozenset(self):
        info = ProjectTypeDetector.detect("HTML CSS JavaScript SPA page")
        assert isinstance(info.allowed_extensions, frozenset)

    @pytest.mark.unit
    def test_frontend_web_does_not_allow_python(self):
        info = ProjectTypeDetector.detect("pure HTML CSS JavaScript no backend no server")
        assert ".py" not in info.allowed_extensions
        assert ".pyi" not in info.allowed_extensions

    @pytest.mark.unit
    def test_go_service_does_not_allow_python(self):
        info = ProjectTypeDetector.detect("golang microservice REST API go.mod")
        assert ".py" not in info.allowed_extensions


# ---------------------------------------------------------------------------
# Tests: get_forbidden_extensions_text()
# ---------------------------------------------------------------------------


class TestGetForbiddenExtensionsText:
    @pytest.mark.unit
    def test_frontend_has_python_in_forbidden(self):
        info = ProjectTypeDetector.detect("pure HTML CSS JavaScript no backend")
        forbidden_text = ProjectTypeDetector.get_forbidden_extensions_text(info.allowed_extensions)
        assert ".py" in forbidden_text

    @pytest.mark.unit
    def test_python_app_has_no_forbidden(self):
        """Python projects allow .py, so .py should not appear in the forbidden list."""
        info = ProjectTypeDetector.detect("Python Flask REST API application")
        forbidden_text = ProjectTypeDetector.get_forbidden_extensions_text(info.allowed_extensions)
        assert ".py" not in forbidden_text

    @pytest.mark.unit
    def test_returns_string(self):
        info = ProjectTypeDetector.detect("HTML CSS JavaScript SPA")
        result = ProjectTypeDetector.get_forbidden_extensions_text(info.allowed_extensions)
        assert isinstance(result, str)

    @pytest.mark.unit
    def test_empty_string_when_all_common_allowed(self):
        """When all common forbidden extensions are allowed, forbidden text should be empty."""
        # Include all extensions from _COMMON_FORBIDDEN_FOR_FRONTEND
        all_allowed = frozenset({".py", ".go", ".rs", ".java", ".cpp", ".c", ".rb"})
        result = ProjectTypeDetector.get_forbidden_extensions_text(all_allowed)
        assert result == ""
