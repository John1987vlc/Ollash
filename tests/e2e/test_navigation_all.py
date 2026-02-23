import pytest
import re
from playwright.sync_api import expect

@pytest.mark.e2e
def test_full_sidebar_navigation(page, base_url):
    """
    Automated test to verify all sidebar navigation items correctly switch views.
    """
    page.goto(base_url)
    
    # List of all view data-view IDs and their expected content container IDs
    nav_items = [
        ("chat", "chat-view"),
        ("create", "create-view"),
        ("projects", "projects-view"),
        ("pair-programming", "pair-programming-view"),
        ("swarm", "swarm-view"),
        ("operations", "operations-view"),
        ("git", "git-view"),
        ("checkpoints", "checkpoints-view"),
        ("knowledge", "knowledge-view"),
        ("brain", "brain-view"),
        ("cicd", "cicd-view"),
        ("integrations", "integrations-view"),
        ("automations", "automations-view"),
        ("architecture", "architecture-view"),
        ("docs", "docs-view"),
        ("costs", "costs-view"),
        ("resilience", "resilience-view"),
        ("insights", "insights-view"),
        ("sandbox", "sandbox-view"),
        ("prompts", "prompts-view"),
        ("security", "security-view"),
        ("audit", "audit-view"),
        ("policies", "policies-view"),
        ("benchmark", "benchmark-view"),
        ("settings", "settings-view")
    ]

    for view_id, container_id in nav_items:
        print(f"Testing navigation to: {view_id}")
        
        # Click the nav item (handle groups if they are collapsed)
        nav_item = page.locator(f".nav-item[data-view='{view_id}']")
        
        # If item is not visible, it might be in a collapsed group
        if not nav_item.is_visible():
            group = nav_item.locator("xpath=ancestor::div[contains(@class, 'nav-group')]")
            if group.count() > 0:
                header = group.locator(".nav-group-header")
                header.click(force=True)
        
        nav_item.click(force=True)
        page.wait_for_timeout(200) # Small pause for transition
        
        # Verify the view container becomes active
        expect(page.locator(f"#{container_id}")).to_be_visible()
        # Match class that contains 'active' as a whole word
        expect(page.locator(f"#{container_id}")).to_have_class(re.compile(r"(^|\s)active(\s|$)"))
        
        # Verify the nav item itself is marked active
        expect(nav_item).to_have_class(re.compile(r"(^|\s)active(\s|$)"))
