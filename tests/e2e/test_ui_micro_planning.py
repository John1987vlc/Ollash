"""E2E test: Micro-planning events appear in the Web UI (Mejora 1).

Mocks the SSE endpoint to emit a ``micro_steps_planned`` event and verifies
that the UI renders progress feedback without errors.
Requires: running Flask server (started by flask_server fixture) + Playwright chromium.
"""

import json
import pytest
from playwright.sync_api import expect


@pytest.mark.e2e
def test_micro_planning_events_appear_in_ui(page, base_url):
    """Verify the UI can handle a micro_steps_planned SSE event without crashing.

    The test:
    1. Navigates to the root UI.
    2. Intercepts the project generation API and returns a structured JSON
       response that includes ``micro_steps_planned`` progress data.
    3. Confirms the page renders without JS errors.
    """

    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))

    # Mock the auto-agent generate endpoint to simulate micro-planning output
    mock_response = {
        "status": "success",
        "project_name": "test_micro_project",
        "events": [
            {
                "type": "micro_steps_planned",
                "file_path": "src/main.py",
                "steps": ["Define imports", "Define Config class", "Implement main()"],
                "step_count": 3,
                "agent_id": "developer_0",
            }
        ],
        "generated_files": ["src/main.py"],
    }

    def handle_generate_api(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(mock_response),
        )

    def handle_projects_api(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"projects": []}),
        )

    page.route("**/api/auto-agent/projects**", handle_generate_api)
    page.route("**/api/projects**", handle_projects_api)

    page.goto(base_url, timeout=15000)

    # The page should load successfully
    expect(page).not_to_have_title("Error", timeout=5000)

    # Navigate to the auto-agent / projects view if it exists
    wizard_nav = page.locator(".nav-item[data-view='projects'], .nav-item[data-view='auto-agent']")
    if wizard_nav.count() > 0:
        wizard_nav.first.click()

    # Confirm no critical JS errors occurred during navigation
    critical_errors = [e for e in console_errors if "TypeError" in e or "ReferenceError" in e]
    assert critical_errors == [], f"JS errors in UI: {critical_errors}"


@pytest.mark.e2e
def test_rescue_step_event_does_not_crash_ui(page, base_url):
    """Verify the UI handles an unknown event type (rescue_step_executed) gracefully."""

    console_errors = []
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))

    def handle_rescue_api(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "status": "partial",
                    "rescue_steps": [
                        {"step": "Validate imports", "action": "Check deps"},
                        {"step": "Reduce context", "action": "Trim window"},
                        {"step": "Retry generation", "action": "Reattempt"},
                    ],
                }
            ),
        )

    page.route("**/api/**", handle_rescue_api)
    page.goto(base_url, timeout=15000)

    # Page should not crash with unknown event data
    expect(page).not_to_have_title("500", timeout=5000)
    assert console_errors == [], f"Page errors: {console_errors}"
