"""E2E SPA tests — project creation wizard (requires uvicorn mock server)."""

from __future__ import annotations

import re
import pytest
from playwright.sync_api import expect


@pytest.mark.e2e
def test_wizard_langgraph_option_is_selectable(page, base_url):
    """The wizard should display the 'Swarm con LangGraph' card and allow selecting it."""
    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)

    # Click on the button to create a project (e.g. navigation or projects page)
    proj_nav = page.locator(".nav-item[data-view='projects']")
    if proj_nav.count() == 0:
        # Fallback to direct navigation
        page.goto(f"{base_url}#create")
    else:
        proj_nav.click()
        # Click the Create Project button inside Projects view
        create_btn = page.locator("[data-view='create']").first
        create_btn.click()

    # Now we should be on the create-view
    expect(page.locator("#create-view")).to_be_visible(timeout=5_000)

    # In Step 1, fill the project name to proceed to Step 2 (configuration)
    page.locator("#project-name").fill("E2E_Test_Project")
    
    # Click "Next" to go to Step 2
    page.locator("#wizard-next-1").click()
    page.wait_for_timeout(300)

    # Ensure the LangGraph option is visible
    langgraph_card = page.locator("#mode-card-langgraph")
    expect(langgraph_card).to_be_visible(timeout=3_000)

    # Click it to select
    langgraph_card.click()
    page.wait_for_timeout(200)

    # Verify that it becomes active
    expect(langgraph_card).to_have_class(re.compile(r"active"))
