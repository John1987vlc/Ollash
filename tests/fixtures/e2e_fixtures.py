"""E2E / Playwright fixtures — Flask dev server, Playwright page with traces."""

import os
import threading
import time
from pathlib import Path

import pytest
import requests

from frontend.app import create_app


# ── Server lifecycle ──────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def server_port():
    """TCP port used by the E2E Flask server."""
    return 5001


@pytest.fixture(scope="session")
def base_url(server_port):
    """Base URL for the E2E test server."""
    return f"http://127.0.0.1:{server_port}"


@pytest.fixture(scope="session")
def flask_server(server_port, project_root):
    """Starts the Flask server in a background daemon thread.

    Uses exponential back-off (up to 15 s) to wait for the server to be
    ready instead of a fixed sleep loop, making the fixture faster on most
    machines and more robust on slow CI runners.
    """
    test_root = project_root / "test_root_e2e"
    os.makedirs(test_root, exist_ok=True)

    app = create_app(ollash_root_dir=test_root)
    app.config.update({"TESTING": True, "SERVER_NAME": f"127.0.0.1:{server_port}"})

    server_thread = threading.Thread(
        target=lambda: app.run(port=server_port, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    # Exponential back-off: 0.1 → 0.2 → 0.4 → 0.8 → 1.0 → 1.0 … (max 15 s total)
    url = f"http://127.0.0.1:{server_port}/"
    delay = 0.1
    deadline = time.monotonic() + 15.0

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
        raise RuntimeError(f"E2E Flask server did not respond on {url} within 15 seconds.")

    yield

    # ── Teardown: remove the temporary E2E root so no artifacts are left on disk
    import shutil
    try:
        shutil.rmtree(test_root, ignore_errors=True)
    except Exception:
        pass


# ── pytest hook for trace capture ────────────────────────────────────────────


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach the per-phase test result to the item node.

    Required so the ``page`` fixture can check whether the test failed and
    decide whether to save the Playwright trace.
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


# ── Playwright page ───────────────────────────────────────────────────────────


@pytest.fixture
def page(context, flask_server, request):
    """Enhanced Playwright page fixture.

    - Logs browser console errors and JS page errors.
    - Records a Playwright trace throughout the test.
    - Saves the trace to ``test-results/traces/`` ONLY when the test fails,
      keeping CI artifact sizes small.
    """
    context.tracing.start(screenshots=True, snapshots=True, sources=True)

    _page = context.new_page()
    _page.on(
        "console",
        lambda msg: print(f"BROWSER CONSOLE [{msg.type}]: {msg.text}") if msg.type == "error" else None,
    )
    _page.on("pageerror", lambda exc: print(f"BROWSER PAGE ERROR: {exc}"))

    yield _page

    # Determine whether the test body failed
    test_failed = hasattr(request.node, "rep_call") and request.node.rep_call.failed

    if test_failed:
        trace_dir = Path("test-results/traces")
        trace_dir.mkdir(parents=True, exist_ok=True)
        # Sanitize the node name to be a valid filename
        safe_name = request.node.name.replace("/", "_").replace("[", "_").replace("]", "_")
        context.tracing.stop(path=str(trace_dir / f"{safe_name}.zip"))
    else:
        context.tracing.stop()
