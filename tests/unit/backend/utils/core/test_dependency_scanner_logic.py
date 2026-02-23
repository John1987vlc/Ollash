import pytest
from backend.utils.core.analysis.scanners.dependency_scanner import (
    PythonDependencyScanner, NodeDependencyScanner, GoDependencyScanner, RustDependencyScanner
)

def test_python_scanner_scan_imports():
    scanner = PythonDependencyScanner()
    files = {
        "app.py": "import requests\nfrom flask import Flask\nimport os\nfrom .local import helper"
    }
    packages = scanner.scan_imports(files)
    assert "requests" in packages
    assert "flask" in packages
    assert "os" not in packages # stdlib
    assert "local" not in packages # relative

def test_node_scanner_scan_imports():
    scanner = NodeDependencyScanner()
    files = {
        "index.js": "const express = require('express');\nimport axios from 'axios';\nconst fs = require('fs');"
    }
    packages = scanner.scan_imports(files)
    assert "express" in packages
    assert "axios" in packages
    assert "fs" not in packages # builtin

def test_go_scanner_scan_imports():
    scanner = GoDependencyScanner()
    files = {
        "main.go": 'import ("fmt"\n"github.com/gin-gonic/gin")\nimport "net/http"'
    }
    packages = scanner.scan_imports(files)
    assert "github.com/gin-gonic/gin" in packages
    assert "fmt" not in packages
    assert "net/http" not in packages

def test_rust_scanner_scan_imports():
    scanner = RustDependencyScanner()
    files = {
        "main.rs": "use serde::Serialize;\nextern crate tokio;"
    }
    packages = scanner.scan_imports(files)
    assert "serde" in packages
    assert "tokio" in packages
