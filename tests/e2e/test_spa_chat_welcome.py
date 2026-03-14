"""
E2E SPA tests — chat welcome screen (requires uvicorn mock server).

Verifies the new onboarding welcome:
  - Welcome screen shows on chat load
  - 5 example cards are rendered
  - Clicking a card populates the input with the prompt text
  - Clicking a card hides the welcome screen
  - Input placeholder is in Spanish
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect


# ── Helpers ──────────────────────────────────────────────────────────────────


def _navigate_to_chat(page, base_url):
    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)
    chat_nav = page.locator(".nav-item[data-view='chat']")
    if chat_nav.count() == 0:
        pytest.skip("Chat nav item not found")
    chat_nav.first.click()
    expect(page.locator("#chat-view")).to_be_visible(timeout=5_000)


# ── Welcome screen visibility ─────────────────────────────────────────────────


@pytest.mark.e2e
def test_chat_welcome_screen_visible_on_load(page, base_url):
    """#chat-welcome-screen is visible when chat view opens."""
    _navigate_to_chat(page, base_url)
    welcome = page.locator("#chat-welcome-screen")
    expect(welcome).to_be_visible(timeout=3_000)


@pytest.mark.e2e
def test_chat_welcome_title_is_spanish(page, base_url):
    """Welcome screen h2 contains 'Ollash' or 'Bienvenido'."""
    _navigate_to_chat(page, base_url)
    h2 = page.locator("#chat-welcome-screen h2")
    expect(h2).to_be_visible(timeout=3_000)
    text = h2.text_content() or ""
    assert "Ollash" in text or "Bienvenido" in text, f"Expected 'Ollash' or 'Bienvenido' in welcome h2, got '{text}'"


# ── Example cards ─────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_chat_welcome_has_five_example_cards(page, base_url):
    """Welcome screen renders exactly 5 example cards."""
    _navigate_to_chat(page, base_url)
    cards = page.locator(".welcome-example-card")
    count = cards.count()
    assert count == 5, f"Expected 5 welcome example cards, found {count}"


@pytest.mark.e2e
def test_chat_welcome_cards_are_visible(page, base_url):
    """All 5 welcome example cards are visible."""
    _navigate_to_chat(page, base_url)
    cards = page.locator(".welcome-example-card")
    for i in range(cards.count()):
        expect(cards.nth(i)).to_be_visible(timeout=3_000)


@pytest.mark.e2e
def test_chat_welcome_card_has_data_prompt(page, base_url):
    """Each example card has a non-empty data-prompt attribute."""
    _navigate_to_chat(page, base_url)
    cards = page.locator(".welcome-example-card")
    for i in range(cards.count()):
        prompt = cards.nth(i).get_attribute("data-prompt") or ""
        assert prompt.strip(), f"Card {i} has empty data-prompt"


@pytest.mark.e2e
def test_chat_welcome_card_has_label(page, base_url):
    """Each example card has a visible .example-label span with text."""
    _navigate_to_chat(page, base_url)
    cards = page.locator(".welcome-example-card")
    for i in range(cards.count()):
        label = cards.nth(i).locator(".example-label")
        expect(label).to_be_visible(timeout=3_000)
        text = label.text_content() or ""
        assert text.strip(), f"Card {i} .example-label is empty"


# ── Card click behaviour ──────────────────────────────────────────────────────


@pytest.mark.e2e
def test_clicking_card_populates_chat_input(page, base_url):
    """Clicking an example card sets the chat input value to the card's data-prompt."""
    _navigate_to_chat(page, base_url)
    first_card = page.locator(".welcome-example-card").first
    expected_prompt_raw = first_card.get_attribute("data-prompt") or ""
    assert expected_prompt_raw, "First card must have a data-prompt attribute"

    first_card.click()
    page.wait_for_timeout(300)

    input_val = page.locator("#chat-input").input_value()
    # data-prompt uses \n as literal two chars; the JS replaces them with real newlines
    expected = expected_prompt_raw.replace("\\n", "\n")
    assert input_val.strip() == expected.strip(), (
        f"Input value mismatch.\nExpected: {expected!r}\nGot:      {input_val!r}"
    )


@pytest.mark.e2e
def test_clicking_card_hides_welcome_screen(page, base_url):
    """Clicking an example card hides #chat-welcome-screen."""
    _navigate_to_chat(page, base_url)
    first_card = page.locator(".welcome-example-card").first
    first_card.click()
    page.wait_for_timeout(300)
    expect(page.locator("#chat-welcome-screen")).to_be_hidden(timeout=3_000)


@pytest.mark.e2e
def test_clicking_card_focuses_chat_input(page, base_url):
    """Clicking an example card moves keyboard focus to #chat-input."""
    _navigate_to_chat(page, base_url)
    first_card = page.locator(".welcome-example-card").first
    first_card.click()
    page.wait_for_timeout(300)
    # Evaluate whether #chat-input is the focused element
    is_focused = page.evaluate("document.activeElement && document.activeElement.id === 'chat-input'")
    assert is_focused, "#chat-input should be focused after clicking a welcome card"


# ── Input placeholder ─────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_chat_input_placeholder_is_spanish(page, base_url):
    """The chat textarea has a Spanish placeholder."""
    _navigate_to_chat(page, base_url)
    chat_input = page.locator("#chat-input")
    expect(chat_input).to_be_visible(timeout=3_000)
    placeholder = chat_input.get_attribute("placeholder") or ""
    assert placeholder, "Chat input must have a placeholder"
    # Must not be the old English placeholder
    assert "Ask Ollash" not in placeholder, f"Placeholder should be in Spanish, not English. Got: '{placeholder}'"


# ── No JS errors ──────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_welcome_screen_no_js_errors(page, base_url):
    """Loading the chat welcome screen and clicking a card produces no JS errors."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    _navigate_to_chat(page, base_url)
    page.locator(".welcome-example-card").first.click()
    page.wait_for_timeout(300)
    assert not errors, f"JS errors on chat welcome screen: {errors}"
