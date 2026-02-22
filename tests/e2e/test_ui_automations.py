import pytest
import json
from playwright.sync_api import expect


@pytest.mark.e2e
def test_automations_list_rendering(page, base_url):
    """
    Validates that existing automations are rendered correctly.
    """
    mock_tasks = [
        {
            "id": "task_1",
            "name": "Daily Security Scan",
            "agent": "cybersecurity",
            "prompt": "Scan all ports",
            "schedule": "daily",
            "status": "active",
        }
    ]

    page.route(
        "**/api/automations",
        lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(mock_tasks)),
    )

    page.goto(base_url)
    
    # Expand 'Sistema e Integraciones' group if needed
    header = page.locator("button[aria-controls='nav-group-sistema']")
    if header.get_attribute("aria-expanded") == "false":
        header.click()
        
    page.locator(".nav-item[data-view='automations']").click()

    # Wait for the grid to contain the task name
    expect(page.locator("#automations-grid")).to_contain_text("Daily Security Scan")


@pytest.mark.e2e
def test_create_automation_modal(page, base_url):
    """
    Validates the creation of a new automation using correct field IDs.
    """
    page.goto(base_url)
    
    # Expand 'Sistema e Integraciones' group if needed
    header = page.locator("button[aria-controls='nav-group-sistema']")
    if header.get_attribute("aria-expanded") == "false":
        header.click()
        
    page.locator(".nav-item[data-view='automations']").click()

    # Click New Automation
    page.locator("#new-automation-btn").click()

    # Verify modal is visible
    modal = page.locator("#automation-modal")
    expect(modal).to_be_visible()

    # Fill the form
    page.locator("#task-name").fill("E2E Test Task")
    page.locator("#task-prompt").fill("Clean temporary files")

    # Mock the POST response
    page.route(
        "**/api/automations",
        lambda route: route.fulfill(
            status=201, content_type="application/json", body=json.dumps({"status": "created", "id": "new_1"})
        ),
        times=1,
    )

    # Submit (using force because of the sidebar/z-index issues)
    page.locator("#automation-form button[type='submit']").click(force=True)

    # Modal should close
    expect(modal).to_be_hidden()


@pytest.mark.e2e
def test_automation_modal_has_aria_attributes(page, base_url):
    """
    Verifica que el modal de automatización tenga role='dialog' y aria-modal='true'
    una vez abierto (test de regresión de accesibilidad).
    """
    page.goto(base_url)
    
    # Expand 'Sistema e Integraciones' group if needed
    header = page.locator("button[aria-controls='nav-group-sistema']")
    if header.get_attribute("aria-expanded") == "false":
        header.click()
        
    page.locator(".nav-item[data-view='automations']").click()
    page.locator("#new-automation-btn").click()

    modal = page.locator("#automation-modal")
    expect(modal).to_be_visible()

    role = modal.get_attribute("role")
    aria_modal = modal.get_attribute("aria-modal")

    assert role == "dialog", f"Automation modal should have role='dialog', got '{role}'"
    assert aria_modal == "true", f"Automation modal should have aria-modal='true', got '{aria_modal}'"
