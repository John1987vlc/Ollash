"""Module for handling Flask application configuration injection."""

import os
from pathlib import Path
from backend.core.config import config as central_config


def setup_app_config(app, ollash_root_dir: Path):
    """Combines centralized config and injects it into Flask app config."""

    combined_config = {
        **(central_config.TOOL_SETTINGS or {}),
        **(central_config.LLM_MODELS or {}),
        **(central_config.AGENT_FEATURES or {}),
        **(central_config.ALERTS or {}),
        **(central_config.AUTOMATION_TEMPLATES or {}),
    }

    app.config["config"] = combined_config
    app.config["ollash_root_dir"] = ollash_root_dir

    # Secret key for session management
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32).hex())

    # Static and template folders are already set in create_app factory
    return app
