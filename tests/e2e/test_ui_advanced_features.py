import pytest
import re
from playwright.sync_api import expect

@pytest.mark.e2e
def test_brain_view_loads(page, base_url):
    """Verifies that the Brain (Intelligence Hub) view loads correctly."""
    page.goto(base_url)
    
    # Expand 'Memoria y Checkpoints' group if needed
    header = page.locator("button[aria-controls='nav-group-memoria']")
    if header.get_attribute("aria-expanded") == "false":
        header.click()
        page.wait_for_timeout(300)
        
    page.locator(".nav-item[data-view='brain']").click()
    
    expect(page.locator("#brain-view")).to_be_visible()
    expect(page.locator("#knowledge-graph-container")).to_be_visible()
    expect(page.locator(".decision-panel")).to_be_visible()

@pytest.mark.e2e
def test_checkpoints_view_loads(page, base_url):
    """Verifies that the Checkpoints view loads."""
    page.goto(base_url)
    
    # Expand 'Memoria y Checkpoints' group
    header = page.locator("button[aria-controls='nav-group-memoria']")
    if header.get_attribute("aria-expanded") == "false":
        header.click()
        page.wait_for_timeout(300)
        
    page.locator(".nav-item[data-view='checkpoints']").click()
    
    expect(page.locator("#checkpoints-view")).to_be_visible()
    expect(page.locator("text='Project Time Machine'")).to_be_visible()
    expect(page.locator("button:has-text('Create Snapshot')")).to_be_visible()

@pytest.mark.e2e
def test_integrations_view_loads(page, base_url):
    """Verifies that the Integrations (Triggers) view loads."""
    page.goto(base_url)
    
    # Expand 'Sistema e Integraciones' group
    header = page.locator("button[aria-controls='nav-group-sistema']")
    # Force click if needed or check attribute
    if header.get_attribute("aria-expanded") == "false":
        header.click()
        page.wait_for_timeout(300) # Animation wait
        
    page.locator(".nav-item[data-view='integrations']").click()
    
    expect(page.locator("#integrations-view")).to_be_visible()
    expect(page.locator("button:has-text('+ New Trigger')")).to_be_visible()

@pytest.mark.e2e
def test_pair_programming_view_loads(page, base_url):
    """Verifies that the Pair Programming view loads with split editors."""
    page.goto(base_url)
    
    # Expand 'Operaciones' group
    header = page.locator("button[aria-controls='nav-group-operaciones']")
    if header.get_attribute("aria-expanded") == "false":
        header.click()
        page.wait_for_timeout(300)
        
    page.locator(".nav-item[data-view='pair-programming']").click()
    
    expect(page.locator("#pair-programming-view")).to_be_visible()
    expect(page.locator("#monaco-user")).to_be_visible()
    expect(page.locator("#monaco-agent")).to_be_visible()

@pytest.mark.e2e
def test_multimodal_buttons_present(page, base_url):
    """Verifies that Voice and OCR buttons are present in the Chat view."""
    page.goto(base_url)
    
    # Navigate to chat
    page.locator(".nav-item[data-view='chat']").first.click()
    
    expect(page.locator("#voice-input-btn")).to_be_visible()
    expect(page.locator("#attach-file-btn")).to_be_visible()

@pytest.mark.e2e
def test_terminal_toggle(page, base_url):
    """Verifies that the floating terminal can be toggled."""
    page.goto(base_url)
    
    bubble = page.locator("#terminal-bubble")
    terminal = page.locator("#floating-terminal")
    
    expect(bubble).to_be_visible()
    
    # Initial state: hidden
    # Note: to_be_hidden() passes if display:none, opacity:0, etc.
    expect(terminal).not_to_be_visible()
    
    bubble.click()
    
    # Wait for the class to be applied
    expect(terminal).to_have_class(re.compile(r"visible"))
    expect(terminal).to_be_visible()
    
    # Close it
    page.locator("#terminal-close").click()
    expect(terminal).not_to_have_class(re.compile(r"visible"))
    expect(terminal).not_to_be_visible()
