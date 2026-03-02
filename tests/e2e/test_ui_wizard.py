"""
E2E Playwright tests — Project Creation Wizard (V2).

Validates the multi-step wizard and the transition to the Kanban board.
"""

from __future__ import annotations

import json
import re

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_project_wizard_flow(page: Page, base_url: str) -> None:
    """
    Validates the multi-step project creation wizard.
    """
    page.goto(base_url)
    page.locator(".nav-item[data-view='create']").click()

    # Wait for the wizard view
    expect(page.locator("#create-view")).to_be_visible()

    # --- Step 1: Project Identity ---
    page.locator("#project-name").fill("E2E-Wizard-Project")

    # Click Next
    page.locator("#wizard-next-1").click()

    # --- Step 2: Configuration ---
    # Wait for step 2 to be active
    expect(page.locator("#wizard-step-2")).to_have_class(re.compile(r"active"))

    # Click Next
    page.locator("#wizard-next-2").click()

    # --- Step 3: Description ---
    expect(page.locator("#wizard-step-3")).to_have_class(re.compile(r"active"))
    page.locator("#project-description").fill("A project generated via E2E test.")

    # Mock the /api/projects/create response
    page.route(
        "**/api/projects/create",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"status": "started", "project_name": "E2E-Wizard-Project"}),
        ),
    )

    # Mock SSE endpoint
    page.route(
        "**/api/projects/stream/*",
        lambda route: route.fulfill(status=200, content_type="text/event-stream", body='data: {"status": "ok"}\n\n'),
    )

    # Click Generate
    page.locator("#wizard-generate").click()

    # Verify Kanban board appears
    expect(page.locator("#kanban-board")).to_be_visible(timeout=5000)

    # Verify success toast (approximate check via internal JS state or DOM if possible)
    # Since it's an async flow with SSE, we just check that we didn't get an error
    expect(page.locator("#wizard-generate")).to_be_disabled()
