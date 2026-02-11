"""Unit tests for DependencyScanner module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.utils.core.scanners.dependency_scanner import (
    DependencyScanner,
    PythonDependencyScanner,
    NodeDependencyScanner,
    GoDependencyScanner,
    RustDependencyScanner,
)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock()


@pytest.fixture
def scanner(mock_logger):
    """Create a DependencyScanner instance."""
    return DependencyScanner(logger=mock_logger)


class TestPythonDependencyScanner:
    """Test Python dependency scanning."""

    def test_scan_simple_imports(self, mock_logger):
        """Test scanning simple Python imports."""
        scanner = PythonDependencyScanner(logger=mock_logger)
        
        files = {
            "main.py": "import requests\nfrom flask import Flask\nimport os"
        }
        
        imports = scanner.scan_imports(files)
        assert "requests" in imports
        assert "flask" in imports
        assert "os" not in imports  # stdlib excluded

    def test_scan_from_imports(self, mock_logger):
        """Test scanning 'from X import Y' statements."""
        scanner = PythonDependencyScanner(logger=mock_logger)
        
        files = {
            "test.py": "from sqlalchemy import create_engine\nfrom numpy import array"
        }
        
        imports = scanner.scan_imports(files)
        assert "sqlalchemy" in imports
        assert "numpy" in imports

    def test_no_duplicates(self, mock_logger):
        """Test that imports are not duplicated."""
        scanner = PythonDependencyScanner(logger=mock_logger)
        
        files = {
            "app.py": "import requests\nimport requests\nfrom requests import get"
        }
        
        imports = scanner.scan_imports(files)
        assert imports.count("requests") == 1


class TestNodeDependencyScanner:
    """Test Node.js dependency scanning."""

    def test_scan_require_statements(self, mock_logger):
        """Test scanning require() statements."""
        scanner = NodeDependencyScanner(logger=mock_logger)
        
        files = {
            "index.js": 'const express = require("express");\nconst axios = require("axios");'
        }
        
        imports = scanner.scan_imports(files)
        assert "express" in imports
        assert "axios" in imports

    def test_scan_es6_imports(self, mock_logger):
        """Test scanning ES6 import statements."""
        scanner = NodeDependencyScanner(logger=mock_logger)
        
        files = {
            "app.ts": 'import React from "react";\nimport { useState } from "react";'
        }
        
        imports = scanner.scan_imports(files)
        assert "react" in imports

    def test_scoped_packages(self, mock_logger):
        """Test handling of scoped packages (@scope/package)."""
        scanner = NodeDependencyScanner(logger=mock_logger)
        
        files = {
            "package.js": 'const button = require("@material-ui/core/Button");'
        }
        
        imports = scanner.scan_imports(files)
        assert "@material-ui/core" in imports


class TestGoDependencyScanner:
    """Test Go dependency scanning."""

    def test_scan_go_imports(self, mock_logger):
        """Test scanning Go import statements."""
        scanner = GoDependencyScanner(logger=mock_logger)
        
        files = {
            "main.go": """
import (
    "fmt"
    "github.com/gin-gonic/gin"
    "gorm.io/gorm"
)
"""
        }
        
        imports = scanner.scan_imports(files)
        assert "github.com/gin-gonic/gin" in imports
        assert "gorm.io/gorm" in imports
        assert "fmt" not in imports  # stdlib excluded

    def test_single_line_import(self, mock_logger):
        """Test single-line Go imports."""
        scanner = GoDependencyScanner(logger=mock_logger)
        
        files = {
            "main.go": 'import "github.com/go-sql-driver/mysql"'
        }
        
        imports = scanner.scan_imports(files)
        assert "github.com/go-sql-driver/mysql" in imports


class TestRustDependencyScanner:
    """Test Rust dependency scanning."""

    def test_scan_cargo_dependencies(self, mock_logger):
        """Test scanning Rust crate declarations."""
        scanner = RustDependencyScanner(logger=mock_logger)
        
        files = {
            "main.rs": """
extern crate serde;
extern crate tokio;
use warp::Filter;
"""
        }
        
        imports = scanner.scan_imports(files)
        assert "serde" in imports
        assert "tokio" in imports
        assert "warp" in imports

    def test_rust_stdlib_excluded(self, mock_logger):
        """Test that Rust stdlib is excluded."""
        scanner = RustDependencyScanner(logger=mock_logger)
        
        files = {
            "lib.rs": "use std::collections;\nuse std::io;\nextern crate anyhow;"
        }
        
        imports = scanner.scan_imports(files)
        assert "std" not in imports
        assert "anyhow" in imports


class TestDependencyScanner:
    """Test the main DependencyScanner orchestrator."""

    def test_scan_all_imports(self, scanner):
        """Test scanning multiple languages in one pass."""
        files = {
            "main.py": "import requests\nfrom flask import Flask",
            "index.js": 'const express = require("express");',
            "main.go": 'import "github.com/gin-gonic/gin"',
            "main.rs": "extern crate tokio;",
        }
        
        all_imports = scanner.scan_all_imports(files)
        
        assert "python" in all_imports
        assert "javascript" in all_imports
        assert "go" in all_imports
        assert "rust" in all_imports
        assert "requests" in all_imports["python"]
        assert "express" in all_imports["javascript"]
        assert "github.com/gin-gonic/gin" in all_imports["go"]
        assert "tokio" in all_imports["rust"]

    def test_reconcile_dependencies(self, scanner, tmp_path):
        """Test dependency reconciliation across languages."""
        # Create test project structure
        py_file = tmp_path / "main.py"
        py_file.write_text("import requests\nfrom flask import Flask")
        
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("old-package==1.0.0\n")
        
        files = {
            "main.py": "import requests\nfrom flask import Flask",
            "requirements.txt": "old-package==1.0.0\n",
        }
        
        result = scanner.reconcile_dependencies(files, tmp_path)
        
        # Should update requirements.txt
        assert "requirements.txt" in result
        assert "requests" in result["requirements.txt"]
