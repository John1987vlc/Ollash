import pytest
from unittest.mock import patch, MagicMock
from backend.utils.core.tools.wasm_sandbox import TestResult

@pytest.fixture
def client(flask_app):
    return flask_app.test_client()

def test_sandbox_page_loads(client):
    """Test that the sandbox playground UI renders."""
    response = client.get("/sandbox/")
    assert response.status_code == 200
    assert b"Safe Execution Sandbox" in response.data

@patch("frontend.blueprints.sandbox_bp.docker_sandbox")
@patch("frontend.blueprints.sandbox_bp.wasm_sandbox")
def test_execute_code_python_success(mock_wasm, mock_docker, client):
    """Test successful Python code execution via Docker fallback."""
    mock_docker.is_available = True
    mock_docker.execute_in_container.return_value = TestResult(
        success=True,
        exit_code=0,
        stdout="hello world
",
        stderr="",
        duration_seconds=0.1
    )
    
    payload = {
        "code": "print('hello world')",
        "language": "python"
    }
    
    response = client.post("/sandbox/execute", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "hello world" in data["output"]
    assert data["duration"] == 0.1

def test_execute_code_missing_code(client):
    """Test error handling when no code is provided."""
    response = client.post("/sandbox/execute", json={})
    assert response.status_code == 400
    assert b"No code provided" in response.data

@patch("frontend.blueprints.sandbox_bp.docker_sandbox")
@patch("frontend.blueprints.sandbox_bp.wasm_sandbox")
def test_execute_code_unsupported_language(mock_wasm, mock_docker, client):
    """Test error handling for unsupported languages."""
    payload = {
        "code": "some code",
        "language": "cobol"
    }
    response = client.post("/sandbox/execute", json=payload)
    assert response.status_code == 400
    assert b"not supported" in response.data
