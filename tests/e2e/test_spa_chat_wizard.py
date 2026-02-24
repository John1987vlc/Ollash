import re
from playwright.sync_api import Page, expect

# Base URL - assuming Flask is running on localhost:5000
BASE_URL = "http://localhost:5000"

def test_spa_navigation_and_header(page: Page):
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    # Navigate to Projects
    page.click("button[data-view='projects']")
    expect(page.locator("#current-view-title")).to_contain_text("Proyectos")
    expect(page.locator("#projects-view")).to_be_visible()

def test_chat_agent_selection(page: Page):
    page.goto(BASE_URL)
    page.click("button[data-view='chat']")

    # Wait for welcome screen
    page.wait_for_selector(".chat-welcome")

    # Use text selector which is more stable for these cards
    page.click("text=Code")

    # Header should update
    expect(page.locator("#chat-header-agent-name")).to_have_text("Code")

def test_prompt_library_v2(page: Page):
    page.goto(BASE_URL)
    page.click("#toggle-prompt-library")
    expect(page.locator("#prompt-library-modal")).to_be_visible()

    # Filter Toggle
    page.click("text=System")
    expect(page.locator("button[data-cat='system']")).to_have_class(re.compile(r".*active.*"))

    # Close
    page.click("#close-prompts-btn", force=True)
    expect(page.locator("#prompt-library-modal")).to_be_hidden()

def test_wizard_basic_flow(page: Page):
    page.goto(BASE_URL)
    page.click("button[data-view='create']")

    page.fill("#project-name", "e2e-project")
    page.click("text=Continuar")

    expect(page.locator("#wizard-step-2")).to_be_visible()

    page.click("text=Configurar Descripción")
    expect(page.locator("#wizard-step-3")).to_be_visible()
    expect(page.locator("#wizard-generate")).to_be_visible()
