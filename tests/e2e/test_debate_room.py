"""
E2E Playwright tests — DebateRoom component (P8).

Scenario:
  1. Load a minimal HTML page with the real debate-room.js injected.
  2. Simulate SSE events by calling JS API directly.
  3. Verify split-screen opens, agent messages appear on correct sides,
     and consensus banner shows.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_COMPONENT_PATH = Path(__file__).parent.parent.parent / "frontend/static/js/components/debate-room.js"


def _build_html() -> str:
    js_src = _COMPONENT_PATH.read_text(encoding="utf-8")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  [hidden] {{ display: none !important; }}
  .debate-overlay {{ position: fixed; inset: 0; background: rgba(0,0,0,.6); }}
</style>
</head>
<body>
  <script>{js_src}</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_debate_room_overlay_opens(page: Page) -> None:
    """DebateRoom.open() makes the overlay visible."""
    page.set_content(_build_html())

    page.evaluate("() => window.DebateRoom.open('debate-task-1')")

    overlay = page.locator("#debate-room-overlay")
    expect(overlay).to_be_visible()


@pytest.mark.e2e
def test_debate_room_node_id_label(page: Page) -> None:
    """open() sets the node ID label."""
    page.set_content(_build_html())

    page.evaluate("() => window.DebateRoom.open('node-xyz')")

    label = page.locator("#debate-node-id-label")
    expect(label).to_have_text("node-xyz")


@pytest.mark.e2e
def test_debate_room_close_hides_overlay(page: Page) -> None:
    """close() hides the overlay."""
    page.set_content(_build_html())

    page.evaluate("() => window.DebateRoom.open('n1')")
    expect(page.locator("#debate-room-overlay")).to_be_visible()

    page.evaluate("() => window.DebateRoom.close()")
    expect(page.locator("#debate-room-overlay")).to_be_hidden()


@pytest.mark.e2e
def test_debate_room_agent_a_messages_appear_in_panel_a(page: Page) -> None:
    """Messages from agent_a appear in the left panel."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        window.DebateRoom.open('debate-1');
        window.DebateRoom.appendMessage(1, 'a', 'architect_0', 'Use microservices.');
        window.DebateRoom.appendMessage(2, 'a', 'architect_0', 'Better scalability.');
    }""")

    panel_a = page.locator("#debate-messages-a")
    bubbles = panel_a.locator(".debate-bubble")
    expect(bubbles).to_have_count(2)
    expect(bubbles.nth(0)).to_contain_text("Use microservices.")
    expect(bubbles.nth(1)).to_contain_text("Better scalability.")


@pytest.mark.e2e
def test_debate_room_agent_b_messages_appear_in_panel_b(page: Page) -> None:
    """Messages from agent_b appear in the right panel."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        window.DebateRoom.open('debate-2');
        window.DebateRoom.appendMessage(1, 'b', 'auditor_0', 'Consider a monolith first.');
    }""")

    panel_b = page.locator("#debate-messages-b")
    bubbles = panel_b.locator(".debate-bubble")
    expect(bubbles).to_have_count(1)
    expect(bubbles.first).to_contain_text("Consider a monolith first.")


@pytest.mark.e2e
def test_debate_room_interleaved_messages_correct_panels(page: Page) -> None:
    """Interleaved A/B messages land on the correct panel each time."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        window.DebateRoom.open('debate-3');
        window.DebateRoom.appendMessage(1, 'a', 'arch', 'Arg A1');
        window.DebateRoom.appendMessage(1, 'b', 'audit', 'Arg B1');
        window.DebateRoom.appendMessage(2, 'a', 'arch', 'Arg A2');
        window.DebateRoom.appendMessage(2, 'b', 'audit', 'Arg B2');
    }""")

    expect(page.locator("#debate-messages-a .debate-bubble")).to_have_count(2)
    expect(page.locator("#debate-messages-b .debate-bubble")).to_have_count(2)


@pytest.mark.e2e
def test_debate_room_consensus_banner_appears(page: Page) -> None:
    """showConsensus() shows the consensus banner with the given text."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        window.DebateRoom.open('debate-4');
        window.DebateRoom.showConsensus('Both agree: use PostgreSQL.');
    }""")

    banner = page.locator("#debate-consensus")
    expect(banner).to_be_visible()
    expect(page.locator("#debate-consensus-text")).to_have_text("Both agree: use PostgreSQL.")


@pytest.mark.e2e
def test_debate_room_consensus_hidden_on_reopen(page: Page) -> None:
    """Opening a new debate resets the consensus banner to hidden."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        window.DebateRoom.open('debate-a');
        window.DebateRoom.showConsensus('Agreed.');
    }""")

    # Reopen for a new debate
    page.evaluate("() => window.DebateRoom.open('debate-b')")
    expect(page.locator("#debate-consensus")).to_be_hidden()


@pytest.mark.e2e
def test_debate_room_html_escaping_in_messages(page: Page) -> None:
    """HTML in argument text is escaped, not rendered as markup."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        window.DebateRoom.open('debate-xss');
        window.DebateRoom.appendMessage(1, 'a', 'agent', '<b>XSS attempt</b>');
    }""")

    panel_a = page.locator("#debate-messages-a")
    inner = panel_a.inner_html()
    assert "<b>" not in inner
    assert "&lt;b&gt;" in inner


@pytest.mark.e2e
def test_debate_room_round_number_shown_in_bubble(page: Page) -> None:
    """Each bubble displays the round number in its meta line."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        window.DebateRoom.open('debate-5');
        window.DebateRoom.appendMessage(3, 'a', 'arch', 'Third round proposal');
    }""")

    meta = page.locator(".debate-bubble-meta").first
    expect(meta).to_contain_text("Round 3")
