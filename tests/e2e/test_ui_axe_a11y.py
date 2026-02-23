"""Automated accessibility tests using axe-core via axe-playwright-python.

These tests scan each major page for WCAG violations of critical or serious
impact. Informational / minor violations are excluded to keep the suite
actionable without excessive noise.

Requirements:
    pip install axe-playwright-python>=0.1.3
"""

import pytest

try:
    from axe_playwright_python.sync_playwright import Axe

    AXE_AVAILABLE = True
except ImportError:
    AXE_AVAILABLE = False


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not AXE_AVAILABLE, reason="axe-playwright-python not installed"),
]

# Pages to scan — path: human-readable label
PAGES_TO_SCAN = [
    ("/", "Home / Dashboard"),
    ("/chat", "Chat"),
    ("/settings", "Settings"),
    ("/docs", "Documentation"),
    ("/benchmark", "Benchmark"),
    ("/knowledge", "Knowledge Base"),
    ("/policies", "Policies"),
]

# Impact levels that must be zero for the test to pass
BLOCKING_IMPACTS = {"critical", "serious"}


@pytest.mark.parametrize("path,label", PAGES_TO_SCAN, ids=[p[1] for p in PAGES_TO_SCAN])
def test_no_critical_axe_violations(page, base_url, flask_server, path, label):
    """Each major page must have zero critical/serious axe-core violations.

    The test navigates to the page, waits for network activity to settle,
    then runs the axe accessibility engine and collects all violations.
    Only violations with impact 'critical' or 'serious' fail the test.
    """
    page.goto(f"{base_url}{path}", wait_until="networkidle")

    axe = Axe()
    results = axe.run(page)

    blocking_violations = [
        v for v in results.violations if v.get("impact") in BLOCKING_IMPACTS
    ]

    if blocking_violations:
        summary_lines = []
        for v in blocking_violations:
            nodes_affected = len(v.get("nodes", []))
            summary_lines.append(
                f"  [{v['impact'].upper()}] {v['id']}: {v['description']} "
                f"({nodes_affected} node(s) affected)"
            )
        violation_report = "\n".join(summary_lines)
        pytest.fail(
            f"Axe found {len(blocking_violations)} blocking violation(s) on '{label}' ({path}):\n"
            f"{violation_report}"
        )


def test_chat_page_axe_with_modal_open(page, base_url, flask_server):
    """The axe scan must also pass when a modal dialog is open.

    Modals introduce new focusable elements and ARIA roles that can expose
    accessibility issues not visible on the base page render.
    """
    page.goto(f"{base_url}/chat", wait_until="networkidle")

    # Open a modal if a trigger exists (e.g., notification config modal)
    trigger = page.locator('[data-modal-target], [data-bs-toggle="modal"]').first
    if trigger.is_visible():
        trigger.click()
        page.wait_for_timeout(300)

    axe = Axe()
    results = axe.run(page)

    blocking_violations = [
        v for v in results.violations if v.get("impact") in BLOCKING_IMPACTS
    ]

    assert len(blocking_violations) == 0, (
        "Axe violations with modal open: "
        + ", ".join(v["id"] for v in blocking_violations)
    )


def test_command_palette_axe(page, base_url, flask_server):
    """The command palette overlay must pass axe checks when visible."""
    page.goto(f"{base_url}/", wait_until="networkidle")

    # Open command palette
    page.keyboard.press("Control+k")
    page.wait_for_selector("#command-palette-overlay", state="visible", timeout=2000)

    axe = Axe()
    results = axe.run(page)

    blocking_violations = [
        v for v in results.violations if v.get("impact") in BLOCKING_IMPACTS
    ]

    assert len(blocking_violations) == 0, (
        "Axe violations in command palette: "
        + ", ".join(v["id"] for v in blocking_violations)
    )
