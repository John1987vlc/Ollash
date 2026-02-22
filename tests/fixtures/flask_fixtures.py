"""Flask application fixtures — test client, app instance, CLI runner."""

import os

import pytest

from frontend.app import create_app


@pytest.fixture
def app(project_root):
    """Creates a Flask app instance configured for testing."""
    test_root = project_root / "test_root_flask"
    os.makedirs(test_root, exist_ok=True)

    _app = create_app(ollash_root_dir=test_root)
    _app.config.update({
        "TESTING": True,
        "ollash_root_dir": str(test_root),
    })
    yield _app


@pytest.fixture
def client(app):
    """A Flask test client for making HTTP requests."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A Flask CLI runner for invoking CLI commands in tests."""
    return app.test_cli_runner()
