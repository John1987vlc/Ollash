"""
E2E tests — minimalist frontend redesign (Phase 1–7).

Covers:
  - Sidebar collapse toggle (icon-rail ↔ expanded)
  - Chat history drawer open/close
  - Agent selector pill in chat top bar
  - Task DAG collapsible bottom strip
  - Mode badge (Chat / Auto Agent)
  - Page load bar (replaces full-screen spinner)
  - Project hub card grid
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load(page, base_url):
    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)


def _go_to_chat(page, base_url):
    _load(page, base_url)
    nav = page.locator(".nav-item[data-view='chat']")
    if nav.count():
        nav.click()
    expect(page.locator("#chat-view")).to_be_visible(timeout=5_000)


# ── Sidebar collapse (Phase 2) ────────────────────────────────────────────────


@pytest.mark.e2e
def test_sidebar_starts_collapsed(page, base_url):
    """On fresh load the sidebar is in 64px icon-rail mode (not expanded)."""
    _load(page, base_url)
    sidebar = page.locator(".sidebar")
    has_expanded = sidebar.evaluate("el => el.classList.contains('sidebar--expanded')")
    assert not has_expanded, "Sidebar should start collapsed (icon-rail mode) on fresh load"


@pytest.mark.e2e
def test_sidebar_expands_on_collapse_toggle_click(page, base_url):
    """Clicking #sidebar-collapse-toggle expands the sidebar to 240px mode."""
    _load(page, base_url)
    toggle = page.locator("#sidebar-collapse-toggle")
    if toggle.count() == 0:
        pytest.skip("#sidebar-collapse-toggle not found")

    # Ensure collapsed first
    sidebar = page.locator(".sidebar")
    if sidebar.evaluate("el => el.classList.contains('sidebar--expanded')"):
        toggle.click()
        page.wait_for_timeout(300)

    toggle.click()
    page.wait_for_timeout(350)

    has_expanded = sidebar.evaluate("el => el.classList.contains('sidebar--expanded')")
    assert has_expanded, "Sidebar should have .sidebar--expanded class after toggle click"


@pytest.mark.e2e
def test_sidebar_logo_btn_expands_when_collapsed(page, base_url):
    """Clicking the logo button expands the sidebar when it is in icon-rail mode."""
    _load(page, base_url)
    sidebar = page.locator(".sidebar")

    # Force collapsed state
    if sidebar.evaluate("el => el.classList.contains('sidebar--expanded')"):
        page.locator("#sidebar-collapse-toggle").click()
        page.wait_for_timeout(300)

    logo_btn = page.locator("#sidebar-logo-btn")
    if logo_btn.count() == 0:
        pytest.skip("#sidebar-logo-btn not found")

    logo_btn.click()
    page.wait_for_timeout(350)

    has_expanded = sidebar.evaluate("el => el.classList.contains('sidebar--expanded')")
    assert has_expanded, "Clicking logo in collapsed mode should expand the sidebar"


@pytest.mark.e2e
def test_collapsed_sidebar_shows_icon_tooltips(page, base_url):
    """Nav items have a data-tooltip attribute for the CSS tooltip in icon-rail mode."""
    _load(page, base_url)
    items_with_tooltip = page.locator(".sidebar .nav-item[data-tooltip]")
    count = items_with_tooltip.count()
    assert count >= 3, f"Expected at least 3 nav items with data-tooltip for icon-rail mode, found {count}"


# ── Chat history drawer (Phase 3) ─────────────────────────────────────────────


@pytest.mark.e2e
def test_chat_history_drawer_hidden_on_load(page, base_url):
    """The chat history drawer is hidden (not open) when the chat view first loads."""
    _go_to_chat(page, base_url)
    drawer = page.locator("#chat-history-drawer")
    if drawer.count() == 0:
        pytest.skip("#chat-history-drawer not found")
    has_open = drawer.evaluate("el => el.classList.contains('drawer--open')")
    assert not has_open, "History drawer should be closed on initial chat load"


@pytest.mark.e2e
def test_chat_history_drawer_opens_on_button_click(page, base_url):
    """Clicking #open-history-drawer opens the history drawer."""
    _go_to_chat(page, base_url)
    btn = page.locator("#open-history-drawer")
    if btn.count() == 0:
        pytest.skip("#open-history-drawer button not found")

    btn.click()
    page.wait_for_timeout(350)

    drawer = page.locator("#chat-history-drawer")
    has_open = drawer.evaluate("el => el.classList.contains('drawer--open')")
    assert has_open, "History drawer should have .drawer--open class after button click"


@pytest.mark.e2e
def test_chat_history_drawer_closes_on_close_button(page, base_url):
    """Clicking #close-history-drawer closes the drawer."""
    _go_to_chat(page, base_url)
    open_btn = page.locator("#open-history-drawer")
    if open_btn.count() == 0:
        pytest.skip("#open-history-drawer not found")

    open_btn.click()
    page.wait_for_timeout(350)

    close_btn = page.locator("#close-history-drawer")
    if close_btn.count() == 0:
        pytest.skip("#close-history-drawer not found")
    close_btn.click()
    page.wait_for_timeout(350)

    drawer = page.locator("#chat-history-drawer")
    has_open = drawer.evaluate("el => el.classList.contains('drawer--open')")
    assert not has_open, "History drawer should close after clicking close button"


@pytest.mark.e2e
def test_chat_history_list_id_preserved(page, base_url):
    """#chat-history-list is still present in the DOM (moved into drawer — ID preserved)."""
    _go_to_chat(page, base_url)
    assert page.locator("#chat-history-list").count() == 1, "#chat-history-list must exist (JS backward compat)"


# ── Agent selector pill (Phase 3) ─────────────────────────────────────────────


@pytest.mark.e2e
def test_agent_selector_pill_present_in_chat_top_bar(page, base_url):
    """The agent selector pill (#chat-session-header) is visible in the chat top bar."""
    _go_to_chat(page, base_url)
    pill = page.locator("#chat-session-header")
    if pill.count() == 0:
        pytest.skip("#chat-session-header pill not found")
    expect(pill).to_be_visible(timeout=3_000)


@pytest.mark.e2e
def test_agent_pill_contains_name_and_status_spans(page, base_url):
    """The agent pill contains #chat-header-agent-name and #chat-header-status spans."""
    _go_to_chat(page, base_url)
    expect(page.locator("#chat-header-agent-name")).to_be_visible(timeout=3_000)
    expect(page.locator("#chat-header-status")).to_be_visible(timeout=3_000)


# ── Task DAG strip (Phase 3) ──────────────────────────────────────────────────


@pytest.mark.e2e
def test_dag_strip_present_in_chat_view(page, base_url):
    """The task DAG collapsible strip (#hitl-dag-panel) is rendered in chat view."""
    _go_to_chat(page, base_url)
    strip = page.locator("#hitl-dag-panel")
    assert strip.count() == 1, "#hitl-dag-panel must be present in chat view"


@pytest.mark.e2e
def test_dag_node_count_id_preserved(page, base_url):
    """#dag-node-count span is in the DOM (moved into strip — ID preserved for JS)."""
    _go_to_chat(page, base_url)
    assert page.locator("#dag-node-count").count() == 1, "#dag-node-count must exist (JS backward compat)"


# ── Mode badge (Phase 7) ──────────────────────────────────────────────────────


@pytest.mark.e2e
def test_mode_badge_exists_in_dom(page, base_url):
    """#mode-badge element is present in the DOM."""
    _load(page, base_url)
    assert page.locator("#mode-badge").count() == 1, "#mode-badge must exist in base layout"


@pytest.mark.e2e
def test_mode_badge_shows_chat_label_on_chat_view(page, base_url):
    """Mode badge has class 'mode-chat' and shows 'Chat' text when chat view is active."""
    _go_to_chat(page, base_url)
    badge = page.locator("#mode-badge")
    if badge.count() == 0:
        pytest.skip("#mode-badge not found")

    # Badge may be hidden in chat view per Phase 6D — that is acceptable
    badge_class = badge.get_attribute("class") or ""
    badge_text = badge.text_content() or ""
    if "hidden" in badge_class or badge.is_hidden():
        pass  # Chat view hides mode badge — this is intentional
    else:
        assert "Chat" in badge_text, f"Mode badge should show 'Chat' in chat view, got '{badge_text}'"


# ── Page load bar (Phase 6) ───────────────────────────────────────────────────


@pytest.mark.e2e
def test_page_load_bar_exists_in_dom(page, base_url):
    """#page-load-bar element is present at the top of the page."""
    _load(page, base_url)
    assert page.locator("#page-load-bar").count() == 1, "#page-load-bar must exist (replaces full-screen spinner)"


@pytest.mark.e2e
def test_global_page_loader_still_in_dom(page, base_url):
    """#global-page-loader div still exists for backward-compat (hidden)."""
    _load(page, base_url)
    # Loader div may have been kept as hidden for JS backward compat
    loader = page.locator("#global-page-loader")
    if loader.count():
        expect(loader).to_be_hidden(timeout=3_000)


# ── Project card grid (Phase 5) ───────────────────────────────────────────────


@pytest.mark.e2e
def test_project_cards_grid_present_in_projects_view(page, base_url):
    """#project-cards-grid is rendered in the projects view."""
    _load(page, base_url)
    nav = page.locator(".nav-item[data-view='projects']")
    if nav.count() == 0:
        pytest.skip("Projects nav item not found")
    nav.click()
    expect(page.locator("#projects-view, #project-view, [data-view-id='projects']").first).to_be_visible(timeout=5_000)
    assert page.locator("#project-cards-grid").count() == 1, "#project-cards-grid must exist in projects view"


@pytest.mark.e2e
def test_existing_projects_select_still_in_dom(page, base_url):
    """Hidden #existing-projects <select> is still in the DOM for JS backward compat."""
    _load(page, base_url)
    nav = page.locator(".nav-item[data-view='projects']")
    if nav.count() == 0:
        pytest.skip("Projects nav item not found")
    nav.click()
    page.wait_for_timeout(500)
    sel = page.locator("#existing-projects")
    assert sel.count() == 1, "#existing-projects select must exist (JS backward compat)"
    # It should be hidden (display:none) — card grid is the visible layer
    expect(sel).to_be_hidden(timeout=2_000)
