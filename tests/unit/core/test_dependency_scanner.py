"""Unit tests for Dependency Scanner module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.utils.core.scanners.dependency_scanner import (
    PythonDependencyScanner,
    NodeDependencyScanner,
    GoDependencyScanner,
    RustDependencyScanner,
    DependencyScanner,
)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock()


class TestPythonDependencyScanner:
    """Tests for PythonDependencyScanner."""

    def test_scan_simple_imports(self, mock_logger):
        """Test scanning basic import statements."""
        scanner = PythonDependencyScanner(logger=mock_logger)
        files = {"main.py": "import os\nimport requests"}
        imports = scanner.scan_imports(files)
        assert "requests" in imports
        assert "os" not in imports

    def test_scan_from_imports(self, mock_logger):
        """Test scanning 'from ... import ...' statements."""
        scanner = PythonDependencyScanner(logger=mock_logger)
        files = {"app.py": "from flask import Flask"}
        imports = scanner.scan_imports(files)
        assert "flask" in imports

    def test_no_duplicates(self, mock_logger):
        """Test that duplicate imports are handled."""
        scanner = PythonDependencyScanner(logger=mock_logger)
        files = {"main.py": "import requests\nimport requests"}
        imports = scanner.scan_imports(files)
        assert "requests" in imports
        assert len(imports) == 1


class TestNodeDependencyScanner:
    """Tests for NodeDependencyScanner."""

    def test_scan_require_statements(self, mock_logger):
        """Test scanning 'require' statements."""
        scanner = NodeDependencyScanner(logger=mock_logger)
        files = {"index.js": "const express = require('express');"}
        imports = scanner.scan_imports(files)
        assert "express" in imports

    def test_scan_es6_imports(self, mock_logger):
        """Test scanning ES6 'import' statements."""
        scanner = NodeDependencyScanner(logger=mock_logger)
        files = {"app.js": "import React from 'react';"}
        imports = scanner.scan_imports(files)
        assert "react" in imports

    def test_scoped_packages(self, mock_logger):
        """Test scanning scoped npm packages."""
        scanner = NodeDependencyScanner(logger=mock_logger)
        files = {"component.js": "import Button from '@material-ui/core';"}
        imports = scanner.scan_imports(files)
        assert "@material-ui" in imports


class TestGoDependencyScanner:
    """Tests for GoDependencyScanner."""

    def test_scan_go_imports(self, mock_logger):
        """Test scanning Go import blocks."""
        scanner = GoDependencyScanner(logger=mock_logger)
        content = """
        import (
            "fmt"
            "github.com/gin-gonic/gin"
        )
        """
        files = {"main.go": content}
        imports = scanner.scan_imports(files)
        assert "github.com/gin-gonic/gin" in imports
        assert "fmt" not in imports

    def test_single_line_import(self, mock_logger):
        """Test scanning single-line Go imports."""
        scanner = GoDependencyScanner(logger=mock_logger)
        files = {"main.go": 'import "github.com/stretchr/testify/assert"'}
        imports = scanner.scan_imports(files)
        assert "github.com/stretchr/testify/assert" in imports


class TestRustDependencyScanner:
    """Tests for RustDependencyScanner."""

    def test_scan_cargo_dependencies(self, mock_logger):
        """Test scanning Rust 'use' and 'extern crate' statements."""
        scanner = RustDependencyScanner(logger=mock_logger)
        content = """
        extern crate anyhow;
        use tokio::runtime::Runtime;
        use std::collections::HashMap;
        """
        files = {"main.rs": content}
        imports = scanner.scan_imports(files)
        assert "anyhow" in imports
        assert "tokio" in imports

    def test_rust_stdlib_excluded(self, mock_logger):
        """Test that Rust stdlib is excluded."""
        scanner = RustDependencyScanner(logger=mock_logger)
        files = {"main.rs": "use std::collections::HashMap;"}
        imports = scanner.scan_imports(files)
        assert "std" not in imports


class TestDependencyScanner:
    """Tests for the main DependencyScanner orchestrator."""

    def test_scan_all_imports(self, mock_logger):
        """Test scanning imports across all supported languages."""
        scanner = DependencyScanner(logger=mock_logger)
        files = {
            "main.py": "import flask",
            "index.js": "const express = require('express');",
            "main.go": 'import "github.com/gin-gonic/gin"',
            "main.rs": "use tokio;"
        }
        all_imports = scanner.scan_all_imports(files)
        
        assert "flask" in all_imports["python"]
        assert "express" in all_imports["node"]
        assert "github.com/gin-gonic/gin" in all_imports["go"]
        assert "tokio" in all_imports["rust"]

    def test_reconcile_dependencies(self, mock_logger, tmp_path):
        """Test dependency reconciliation."""
        scanner = DependencyScanner(logger=mock_logger)
        
        # Create a requirements.txt with excessive packages
        req_content = "\n".join([f"package{i}" for i in range(35)])
        
        files = {
            "main.py": "import requests\nimport flask",
            "requirements.txt": req_content
        }
        
        result = scanner.reconcile_dependencies(files, tmp_path)
        
        # Should be regenerated
        assert "requests" in result["requirements.txt"]
        assert "flask" in result["requirements.txt"]
        assert "package0" not in result["requirements.txt"]
