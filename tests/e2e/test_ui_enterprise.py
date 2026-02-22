import pytest
from playwright.sync_api import Page, expect

def test_operations_dashboard_loads(page: Page):
    page.goto("http://localhost:5000/operations/")
    expect(page.get_by_text("Operations Center")).to_be_visible()
    expect(page.get_by_text("Scheduled Tasks")).to_be_visible()
    
    # Check DAG Preview
    page.get_by_role("button", name="Simulate Plan").click()
    expect(page.locator(".dag-node").first).to_be_visible()

def test_git_dashboard_loads(page: Page):
    page.goto("http://localhost:5000/git/")
    expect(page.get_by_text("Git Control")).to_be_visible()
    expect(page.get_by_text("Branch:")).to_be_visible()

def test_knowledge_dropzone(page: Page):
    page.goto("http://localhost:5000/knowledge/")
    expect(page.get_by_text("Drag & drop Documents or Images for OCR Ingestion")).to_be_visible()

def test_prompt_studio_validation(page: Page):
    page.goto("http://localhost:5000/prompts/")
    # Type a short prompt to trigger warning
    page.get_by_placeholder("Enter your system prompt...").fill("Too short")
    # Wait for debounce
    page.wait_for_timeout(1000)
    expect(page.get_by_text("Prompt is too short")).to_be_visible()
