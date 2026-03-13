"""
E2E Playwright tests — DebateRoom component (component-isolated).

Injects debate-room.js directly into a minimal HTML page via set_content().
No server or Ollama instance required.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

_JS_PATH = Path(__file__).parent.parent.parent / "frontend/static/js/components/debate-room.js"


def _html() -> str:
    js_src = _JS_PATH.read_text(encoding="utf-8")
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


@pytest.mark.e2e
def test_overlay_opens(page_isolated: Page) -> None:
    """DebateRoom.open() makes the overlay visible."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("() => window.DebateRoom.open('task-1')")
    expect(page_isolated.locator("#debate-room-overlay")).to_be_visible()


@pytest.mark.e2e
def test_node_id_label(page_isolated: Page) -> None:
    """open() updates the node ID label."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("() => window.DebateRoom.open('node-abc')")
    expect(page_isolated.locator("#debate-node-id-label")).to_have_text("node-abc")


@pytest.mark.e2e
def test_close_hides_overlay(page_isolated: Page) -> None:
    """close() hides the overlay."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("() => window.DebateRoom.open('n1')")
    expect(page_isolated.locator("#debate-room-overlay")).to_be_visible()
    page_isolated.evaluate("() => window.DebateRoom.close()")
    expect(page_isolated.locator("#debate-room-overlay")).to_be_hidden()


@pytest.mark.e2e
def test_agent_a_messages_in_panel_a(page_isolated: Page) -> None:
    """Messages from side 'a' appear in the left panel."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        window.DebateRoom.open('d1');
        window.DebateRoom.appendMessage(1, 'a', 'architect', 'Use microservices.');
        window.DebateRoom.appendMessage(2, 'a', 'architect', 'Better scalability.');
    }""")
    bubbles = page_isolated.locator("#debate-messages-a .debate-bubble")
    expect(bubbles).to_have_count(2)
    expect(bubbles.nth(0)).to_contain_text("Use microservices.")
    expect(bubbles.nth(1)).to_contain_text("Better scalability.")


@pytest.mark.e2e
def test_agent_b_messages_in_panel_b(page_isolated: Page) -> None:
    """Messages from side 'b' appear in the right panel."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        window.DebateRoom.open('d2');
        window.DebateRoom.appendMessage(1, 'b', 'auditor', 'Consider a monolith first.');
    }""")
    bubbles = page_isolated.locator("#debate-messages-b .debate-bubble")
    expect(bubbles).to_have_count(1)
    expect(bubbles.first).to_contain_text("Consider a monolith first.")


@pytest.mark.e2e
def test_interleaved_messages_correct_panels(page_isolated: Page) -> None:
    """Interleaved A/B messages land on the correct panel each time."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        window.DebateRoom.open('d3');
        window.DebateRoom.appendMessage(1, 'a', 'arch', 'Arg A1');
        window.DebateRoom.appendMessage(1, 'b', 'audit', 'Arg B1');
        window.DebateRoom.appendMessage(2, 'a', 'arch', 'Arg A2');
        window.DebateRoom.appendMessage(2, 'b', 'audit', 'Arg B2');
    }""")
    expect(page_isolated.locator("#debate-messages-a .debate-bubble")).to_have_count(2)
    expect(page_isolated.locator("#debate-messages-b .debate-bubble")).to_have_count(2)


@pytest.mark.e2e
def test_consensus_banner_appears(page_isolated: Page) -> None:
    """showConsensus() shows the consensus banner with the given text."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        window.DebateRoom.open('d4');
        window.DebateRoom.showConsensus('Both agree: use PostgreSQL.');
    }""")
    banner = page_isolated.locator("#debate-consensus")
    expect(banner).to_be_visible()
    expect(page_isolated.locator("#debate-consensus-text")).to_have_text("Both agree: use PostgreSQL.")


@pytest.mark.e2e
def test_consensus_hidden_on_reopen(page_isolated: Page) -> None:
    """Opening a new debate resets the consensus banner to hidden."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        window.DebateRoom.open('d-a');
        window.DebateRoom.showConsensus('Agreed.');
    }""")
    page_isolated.evaluate("() => window.DebateRoom.open('d-b')")
    expect(page_isolated.locator("#debate-consensus")).to_be_hidden()


@pytest.mark.e2e
def test_html_escaping_in_messages(page_isolated: Page) -> None:
    """HTML in argument text is escaped, not rendered as markup (XSS prevention)."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        window.DebateRoom.open('d-xss');
        window.DebateRoom.appendMessage(1, 'a', 'agent', '<b>XSS attempt</b>');
    }""")
    inner = page_isolated.locator("#debate-messages-a").inner_html()
    assert "<b>" not in inner, "Raw <b> tag must not appear — HTML should be escaped"
    assert "&lt;b&gt;" in inner, "Escaped &lt;b&gt; must be present"


@pytest.mark.e2e
def test_round_number_in_bubble(page_isolated: Page) -> None:
    """Each bubble displays the round number in its meta line."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        window.DebateRoom.open('d5');
        window.DebateRoom.appendMessage(3, 'a', 'arch', 'Third round proposal');
    }""")
    meta = page_isolated.locator(".debate-bubble-meta").first
    expect(meta).to_contain_text("Round 3")
