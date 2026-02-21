import pytest
import json
from playwright.sync_api import expect


@pytest.mark.e2e
def test_project_dashboard_flow(page, base_url):
    """
    Validates the Project Dashboard Flow with correct mock data structure.
    """

    # --- 1. MOCK DATA ---
    mock_projects = {"status": "success", "projects": ["TestProjectA", "TestProjectB"]}

    # The frontend expects a 'files' key in the response for the tree
    mock_tree = {"status": "success", "files": [{"name": "main.py", "type": "file", "path": "main.py"}]}

    # Intercept API calls
    def handle_route(route):
        url = route.request.url
        if "/api/projects/list" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(mock_projects))
        elif "/files" in url or "/tree" in url:
            route.fulfill(status=200, content_type="application/json", body=json.dumps(mock_tree))
        else:
            route.continue_()

    page.route("**/api/projects/**", handle_route)

    # --- 2. NAVIGATION ---
    page.goto(base_url)
    page.locator(".nav-item[data-view='projects']").click()
    expect(page.locator("#projects-view")).to_be_visible()

    # --- 3. PROJECT SELECTION ---
    selector = page.locator("#existing-projects")
    page.wait_for_selector("#existing-projects option[value='TestProjectA']", state="attached")
    selector.select_option("TestProjectA", force=True)

    # --- 4. VERIFICATION ---
    workspace = page.locator("#project-workspace")
    expect(workspace).to_be_visible()

    # Check tree content
    file_tree = page.locator("#file-tree-list")
    expect(file_tree).to_contain_text("main.py", timeout=10000)


@pytest.mark.e2e
def test_project_dashboard_navigation(page, base_url):
    """Simple nav check."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='projects']").click()
    expect(page.locator("#projects-view")).to_be_visible()
