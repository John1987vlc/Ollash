"""Unit tests for F1 — InterfaceScaffoldingPhase."""

import pytest
from unittest.mock import MagicMock

from backend.agents.auto_agent_phases.interface_scaffolding_phase import InterfaceScaffoldingPhase


@pytest.fixture
def context():
    ctx = MagicMock()
    ctx.logic_plan = {}
    ctx.event_publisher.publish = MagicMock()
    return ctx


@pytest.fixture
def phase(context):
    return InterfaceScaffoldingPhase(context=context)


@pytest.mark.unit
class TestStubPathFor:
    def _norm(self, p):
        return p.replace("\\", "/") if p else p

    def test_py_gives_pyi(self, phase):
        assert self._norm(phase._stub_path_for("src/utils.py")) == "src/utils.pyi"

    def test_ts_gives_dts(self, phase):
        assert self._norm(phase._stub_path_for("src/api.ts")) == "src/api.d.ts"

    def test_tsx_gives_dts(self, phase):
        assert self._norm(phase._stub_path_for("components/App.tsx")) == "components/App.d.ts"

    def test_js_returns_none(self, phase):
        assert phase._stub_path_for("src/helper.js") is None

    def test_go_returns_none(self, phase):
        assert phase._stub_path_for("main.go") is None


@pytest.mark.unit
class TestPythonStub:
    def test_function_export_generates_def(self, phase):
        stub = phase._python_stub(["validate_email"], {})
        assert "def validate_email" in stub
        assert "-> Any" in stub

    def test_class_export_generates_class(self, phase):
        stub = phase._python_stub(["UserManager"], {})
        assert "class UserManager:" in stub
        assert "..." in stub

    def test_empty_exports_generates_minimal_header(self, phase):
        stub = phase._python_stub([], {})
        assert "Auto-generated stub" in stub

    def test_imports_hint_included(self, phase):
        stub = phase._python_stub(["foo"], {"imports": ["from os import path"]})
        assert "from os import path" in stub


@pytest.mark.unit
class TestTypeScriptStub:
    def test_function_export_generates_declare_function(self, phase):
        stub = phase._typescript_stub(["fetchData"], {})
        assert "export declare function fetchData" in stub

    def test_class_export_generates_declare_class(self, phase):
        stub = phase._typescript_stub(["ApiClient"], {})
        assert "export declare class ApiClient" in stub


@pytest.mark.unit
class TestRunPhase:
    def test_no_logic_plan_skips(self, phase, context, tmp_path):
        context.logic_plan = {}
        gf, structure, fp = phase.run(
            project_description="test",
            project_name="test",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={},
            file_paths=[],
        )
        # No stubs generated
        assert all(not k.endswith(".pyi") for k in gf)

    def test_generates_pyi_for_py_with_exports(self, phase, context, tmp_path):
        context.logic_plan = {
            "src/utils.py": {
                "exports": ["helper_func"],
                "imports": [],
            }
        }
        gf, _, fp = phase.run(
            project_description="test",
            project_name="test",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={},
            file_paths=["src/utils.py"],
        )
        # Normalize path separators for cross-platform comparison
        gf_norm = {k.replace("\\", "/"): v for k, v in gf.items()}
        assert "src/utils.pyi" in gf_norm
        assert "def helper_func" in gf_norm["src/utils.pyi"]

    def test_skips_file_with_no_exports(self, phase, context, tmp_path):
        context.logic_plan = {"src/empty.py": {"exports": [], "imports": []}}
        gf, _, fp = phase.run(
            project_description="test",
            project_name="test",
            project_root=tmp_path,
            readme_content="",
            initial_structure={},
            generated_files={},
            file_paths=[],
        )
        assert "src/empty.pyi" not in gf
