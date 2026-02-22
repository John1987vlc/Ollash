"""Unit tests for DependencyReconciler."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.utils.core.analysis.scanners.dependency_reconciler import DependencyReconciler


@pytest.fixture
def mock_scanner():
    scanner = MagicMock()
    scanner.scan_all_imports.return_value = {
        "python": [],
        "javascript": [],
        "go": [],
        "rust": [],
    }
    return scanner


@pytest.fixture
def reconciler(mock_scanner):
    return DependencyReconciler(dependency_scanner=mock_scanner, logger=MagicMock())


# ---------------------------------------------------------------------------
# reconcile() — primary path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReconcilePrimaryPath:
    def test_delegates_to_scanner(self, reconciler, mock_scanner):
        files = {"requirements.txt": "flask\n"}
        mock_scanner.reconcile_dependencies.return_value = files

        result = reconciler.reconcile(files, Path("."), "3.11")

        mock_scanner.reconcile_dependencies.assert_called_once_with(files, Path("."))
        assert result == files

    def test_falls_back_on_scanner_error(self, reconciler, mock_scanner):
        mock_scanner.reconcile_dependencies.side_effect = RuntimeError("boom")
        files: dict = {}

        result = reconciler.reconcile(files, Path("."), "3.11")

        # Fallback executed without error; empty files stay empty
        assert result == {}


# ---------------------------------------------------------------------------
# _reconcile_python_requirements
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReconcilePythonRequirements:
    def test_skips_when_no_requirements_file(self, reconciler):
        files = {"src/app.py": "import flask"}
        result = reconciler._reconcile_python_requirements(files, Path("."), "3.11")
        assert result == files

    def test_keeps_reasonable_requirements(self, reconciler, mock_scanner):
        mock_scanner.scan_all_imports.return_value = {"python": ["flask"]}
        files = {"requirements.txt": "flask\n"}

        result = reconciler._reconcile_python_requirements(files, Path("."), "3.11")

        # Only 1 entry — should keep it as-is
        assert result["requirements.txt"] == "flask\n"

    def test_regenerates_bloated_requirements(self, reconciler, mock_scanner, tmp_path):
        mock_scanner.scan_all_imports.return_value = {"python": ["flask"]}
        bloated = "\n".join(f"pkg{i}" for i in range(35))
        files = {"requirements.txt": bloated}

        result = reconciler._reconcile_python_requirements(files, tmp_path, "3.11")

        assert "flask" in result["requirements.txt"]
        assert len(result["requirements.txt"].splitlines()) < 35


# ---------------------------------------------------------------------------
# _reconcile_package_json
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReconcilePackageJson:
    def test_skips_when_no_package_json(self, reconciler):
        files = {"src/app.js": "const express = require('express')"}
        result = reconciler._reconcile_package_json(files, Path("."))
        assert result == files

    def test_skips_invalid_json(self, reconciler):
        files = {"package.json": "not-json"}
        result = reconciler._reconcile_package_json(files, Path("."))
        assert result["package.json"] == "not-json"

    def test_keeps_reasonable_package_json(self, reconciler, mock_scanner):
        mock_scanner.scan_all_imports.return_value = {"javascript": ["express"]}
        pkg = json.dumps({"name": "app", "dependencies": {"express": "^4.0.0"}})
        files = {"package.json": pkg}

        result = reconciler._reconcile_package_json(files, Path("."))

        assert json.loads(result["package.json"])["dependencies"] == {"express": "^4.0.0"}

    def test_trims_bloated_package_json(self, reconciler, mock_scanner, tmp_path):
        scanned = ["express"]
        mock_scanner.scan_all_imports.return_value = {"javascript": scanned}
        big_deps = {f"pkg{i}": "*" for i in range(40)}
        pkg = json.dumps({"name": "app", "dependencies": big_deps})
        files = {"package.json": pkg}

        result = reconciler._reconcile_package_json(files, tmp_path)

        trimmed = json.loads(result["package.json"])["dependencies"]
        assert list(trimmed.keys()) == ["express"]


# ---------------------------------------------------------------------------
# _reconcile_go_mod
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReconcileGoMod:
    def test_skips_when_no_go_mod(self, reconciler):
        files = {"main.go": "package main"}
        result = reconciler._reconcile_go_mod(files, Path("."))
        assert result == files

    def test_keeps_reasonable_go_mod(self, reconciler, mock_scanner):
        mock_scanner.scan_all_imports.return_value = {"go": ["github.com/gin-gonic/gin"]}
        go_mod = "module example.com/app\n\ngo 1.21\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.0\n)\n"
        files = {"go.mod": go_mod}

        result = reconciler._reconcile_go_mod(files, Path("."))

        assert result["go.mod"] == go_mod


# ---------------------------------------------------------------------------
# _reconcile_cargo_toml
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReconcileCargoToml:
    def test_skips_when_no_cargo_toml(self, reconciler):
        files = {"src/main.rs": "fn main() {}"}
        result = reconciler._reconcile_cargo_toml(files, Path("."))
        assert result == files

    def test_keeps_reasonable_cargo_toml(self, reconciler, mock_scanner):
        mock_scanner.scan_all_imports.return_value = {"rust": ["serde"]}
        cargo = '[package]\nname = "app"\n\n[dependencies]\nserde = "1.0"\n'
        files = {"Cargo.toml": cargo}

        result = reconciler._reconcile_cargo_toml(files, Path("."))

        assert result["Cargo.toml"] == cargo


# ---------------------------------------------------------------------------
# _save_file
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSaveFile:
    def test_creates_file_and_parents(self, tmp_path):
        target = tmp_path / "nested" / "dir" / "file.txt"
        DependencyReconciler._save_file(target, "hello")

        assert target.exists()
        assert target.read_text() == "hello"
