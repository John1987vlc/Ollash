"""Centralized pytest entry-point for Ollash.

Fixtures are split into domain modules under ``tests/fixtures/`` for
maintainability. This file registers them via ``pytest_plugins`` so pytest
discovers all fixtures automatically without any import side-effects.
"""

# Register fixture modules — order matters: llm must come first (autouse session mock)
pytest_plugins = [
    "tests.fixtures.agent_fixtures",    # project_root, mock_kernel, default_agent
    "tests.fixtures.llm_fixtures",      # block_ollama_globally (autouse), mock_ollama, error variants
    "tests.fixtures.fastapi_fixtures",  # fastapi_app, client (replaces flask_fixtures)
    "tests.fixtures.flask_fixtures",    # app (Flask), client (Flask) — kept for CLI tests
    "tests.fixtures.e2e_fixtures",      # server_port, base_url, flask_server (uvicorn), page
]
