"""Centralized pytest entry-point for Ollash.

Fixtures are split into domain modules under ``tests/fixtures/`` for
maintainability. This file registers them via ``pytest_plugins`` so pytest
discovers all fixtures automatically without any import side-effects.
"""

import pytest

# Register fixture modules — order matters: llm must come first (autouse session mock)
pytest_plugins = [
    "tests.fixtures.agent_fixtures",  # project_root, mock_kernel, default_agent
    "tests.fixtures.llm_fixtures",  # block_ollama_globally (autouse), mock_ollama, error variants
    "tests.fixtures.fastapi_fixtures",  # fastapi_app, client (replaces flask_fixtures)
    "tests.fixtures.flask_fixtures",  # app (Flask), client (Flask) — kept for CLI tests
    "tests.fixtures.e2e_fixtures",  # server_port, base_url, flask_server (uvicorn), page
]


@pytest.fixture(autouse=True, scope="session")
def _patch_flask_request_url_for():
    """Patch Flask's Request with url_for() so FastAPI-style templates render under Flask.

    Templates migrated to Starlette syntax use ``request.url_for('static', path=...)``.
    This fixture makes that call work in Flask test contexts by delegating to
    Flask's ``url_for('static', filename=...)``.
    """
    from flask.wrappers import Request as FlaskRequest
    from flask import url_for as flask_url_for

    def _url_for(self, name: str, **params) -> str:
        if name == "static" and "path" in params:
            params["filename"] = params.pop("path")
        return flask_url_for(name, **params)

    FlaskRequest.url_for = _url_for
    yield
    try:
        delattr(FlaskRequest, "url_for")
    except AttributeError:
        pass
