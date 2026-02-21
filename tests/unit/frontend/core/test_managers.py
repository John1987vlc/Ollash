"""Tests for frontend core managers (config and services)."""

import pytest
from flask import Flask
from frontend.core.config_manager import setup_app_config
from frontend.core.service_manager import init_app_services
from backend.utils.core.system.event_publisher import EventPublisher


@pytest.fixture
def base_app():
    """Returns a fresh Flask app instance without initialization."""
    return Flask("test_app")


@pytest.mark.unit
def test_setup_app_config(base_app, project_root):
    """Verifies that app configuration is correctly injected."""
    app = setup_app_config(base_app, project_root)

    assert "config" in app.config
    assert app.config["ollash_root_dir"] == project_root
    assert app.secret_key is not None
    assert len(app.secret_key) > 0


@pytest.mark.unit
def test_init_app_services_success(base_app, project_root):
    """Verifies that core services are initialized and stored in app config."""
    event_publisher = EventPublisher()
    app = init_app_services(base_app, project_root, event_publisher)

    assert "automation_manager" in app.config
    assert "alert_manager" in app.config
    assert "notification_manager" in app.config
    assert app.config["event_publisher"] == event_publisher

    # Clean up
    if app.config["automation_manager"]:
        app.config["automation_manager"].stop()


@pytest.mark.unit
def test_init_app_services_error_handling(base_app):
    """Verifies that service initialization handles errors gracefully."""
    # Pass an invalid root path to trigger potential errors
    from pathlib import Path

    invalid_path = Path("/non/existent/path")

    event_publisher = EventPublisher()
    # Should not raise exception, but log and continue
    app = init_app_services(base_app, invalid_path, event_publisher)

    # Even if managers fail to start, the app object should be returned
    assert isinstance(app, Flask)
