"""Centralized pytest entry-point for Ollash.

Fixtures are split into domain modules under ``tests/fixtures/`` for
maintainability. This file registers them via ``pytest_plugins`` so pytest
discovers all fixtures automatically without any import side-effects.
"""

import os
import shutil
from pathlib import Path

# Disable slowapi rate limiting in the test suite so helper functions that
# call endpoints multiple times (e.g. _auth_headers in mcp tests) don't hit
# limits.  Production behaviour is unaffected.
os.environ.setdefault("RATELIMIT_ENABLED", "False")

# Register fixture modules — order matters: llm must come first (autouse session mock)
pytest_plugins = [
    "tests.fixtures.agent_fixtures",  # project_root, mock_kernel, default_agent
    "tests.fixtures.llm_fixtures",  # block_ollama_globally (autouse), mock_ollama, error variants
    "tests.fixtures.fastapi_fixtures",  # fastapi_app, client (replaces flask_fixtures)
    "tests.fixtures.e2e_fixtures",  # server_port, base_url, flask_server (uvicorn), page
]


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """Remove test-generated directories from the project root when all tests pass.

    Only runs on exit status 0 to preserve state for debugging when tests fail.
    ``generated_projects/`` is intentionally excluded — it is created by
    benchmark scripts, not the test suite.
    """
    if exitstatus != 0:
        return

    project_root = Path(__file__).parent.parent
    for name in [
        "test_root_fastapi",
        "test_root_flask",
        "test_root_e2e",
        "test_root",
        ".ollash_test",
    ]:
        target = project_root / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
