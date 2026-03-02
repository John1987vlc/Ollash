"""E2E / Playwright fixtures — uvicorn dev server, Playwright page with traces.

Replaces the Flask threading server with a uvicorn subprocess so the FastAPI
application and all its lifespan events are properly initialized.
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests


# ── Server lifecycle ──────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def server_port():
    """TCP port used by the E2E uvicorn server."""
    return 5001


@pytest.fixture(scope="session")
def base_url(server_port):
    """Base URL for the E2E test server."""
    return f"http://127.0.0.1:{server_port}"


@pytest.fixture(scope="session")
def flask_server(server_port, project_root):
    """
    Starts the FastAPI/uvicorn server in a subprocess for E2E testing.

    The fixture name is kept as 'flask_server' for backward compatibility with
    all existing test files that depend on it. Only this fixture changes.

    Uses exponential back-off (up to 20 s) to wait for readiness.
    """
    test_root = project_root / "test_root_e2e"
    test_root.mkdir(parents=True, exist_ok=True)

    env = {
        "OLLASH_ROOT_DIR": str(test_root),
        "TESTING": "1",
        # Prevent real Ollama calls during E2E
        "OLLAMA_URL": "http://127.0.0.1:9999",
    }

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "run_web:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(server_port),
            "--log-level",
            "warning",
        ],
        env={**__import__("os").environ, **env},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Exponential back-off: 0.1 → 0.2 → 0.4 … (max 20 s total)
    url = f"http://127.0.0.1:{server_port}/api/health/"
    delay = 0.1
    deadline = time.monotonic() + 20.0

    while time.monotonic() < deadline:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                break
        except requests.ConnectionError:
            pass
        time.sleep(delay)
        delay = min(delay * 2, 1.0)
    else:
        proc.terminate()
        raise RuntimeError(f"E2E uvicorn server did not respond on {url} within 20 seconds.")

    yield

    # ── Teardown
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    shutil.rmtree(test_root, ignore_errors=True)


# ── pytest hook for trace capture ────────────────────────────────────────────


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach per-phase test result to the item node for trace capture."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


# ── Playwright page ───────────────────────────────────────────────────────────


@pytest.fixture
def page(context, flask_server, request):
    """Enhanced Playwright page fixture with trace capture on failure."""
    context.tracing.start(screenshots=True, snapshots=True, sources=True)

    _page = context.new_page()
    _page.on(
        "console",
        lambda msg: print(f"BROWSER CONSOLE [{msg.type}]: {msg.text}") if msg.type == "error" else None,
    )
    _page.on("pageerror", lambda exc: print(f"BROWSER PAGE ERROR: {exc}"))

    yield _page

    test_failed = hasattr(request.node, "rep_call") and request.node.rep_call.failed

    if test_failed:
        trace_dir = Path("test-results/traces")
        trace_dir.mkdir(parents=True, exist_ok=True)
        safe_name = request.node.name.replace("/", "_").replace("[", "_").replace("]", "_")
        context.tracing.stop(path=str(trace_dir / f"{safe_name}.zip"))
    else:
        context.tracing.stop()
