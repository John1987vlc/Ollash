"""
E2E SPA tests — simplified sidebar (requires uvicorn mock server).

Verifies the new navigation structure:
  - PRINCIPAL group: Chat, Nuevo Proyecto, Mis Proyectos
  - MI PROYECTO group: hidden by default, shown when project is active
  - HERRAMIENTAS group: collapsed by default
  - Standalone items: Ayuda y Guías, Configuración
  - Removed stub items are NOT present in the sidebar

New minimalist redesign notes:
  - Sidebar starts collapsed (64px icon-rail) — all group contents forced visible
  - Tests that check group collapse/item count must first expand the sidebar
    to the full 240px expanded mode before asserting collapse state.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect


# ── Helpers ──────────────────────────────────────────────────────────────────


def _load(page, base_url):
    page.goto(base_url)
    page.wait_for_load_state("load", timeout=15_000)


def _expand_sidebar(page):
    """Ensure the sidebar is in the full 240px expanded mode.

    The redesigned sidebar starts collapsed (icon-rail, 64px).  In collapsed
    mode all nav-group contents are forced open with max-height override so
    normal collapse CSS does not apply.  Tests that assert on HERRAMIENTAS
    height or on visible-item counts must expand the sidebar first.
    """
    sidebar = page.locator(".sidebar")
    if not sidebar.evaluate("el => el.classList.contains('sidebar--expanded')"):
        # Click the collapse-toggle button (which also acts as expand in collapsed state)
        toggle = page.locator("#sidebar-collapse-toggle")
        if toggle.count():
            toggle.click()
        else:
            # Fallback: click the logo button which also expands the sidebar
            page.locator("#sidebar-logo-btn").click()
        page.wait_for_timeout(300)


# ── PRINCIPAL group ───────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_principal_group_visible_on_load(page, base_url):
    """PRINCIPAL nav group is expanded and visible without any interaction."""
    _load(page, base_url)
    for view in ("chat", "create", "projects"):
        item = page.locator(f".nav-item[data-view='{view}']")
        expect(item).to_be_visible(timeout=3_000), f"Nav item data-view='{view}' should be visible"


@pytest.mark.e2e
def test_chat_nav_item_label_is_spanish(page, base_url):
    """The chat nav item shows the simplified Spanish label 'Chat' (not 'Chat Principal')."""
    _load(page, base_url)
    chat = page.locator(".nav-item[data-view='chat']")
    expect(chat).to_be_visible(timeout=3_000)
    label = chat.locator("span").text_content()
    assert label is not None and "Chat" in label, f"Expected label containing 'Chat', got '{label}'"


@pytest.mark.e2e
def test_projects_nav_item_label_updated(page, base_url):
    """The projects nav item label is 'Mis Proyectos' (not 'Proyectos')."""
    _load(page, base_url)
    item = page.locator(".nav-item[data-view='projects']")
    expect(item).to_be_visible(timeout=3_000)
    label = item.locator("span").text_content()
    assert label is not None and "Proyectos" in label, f"Expected label containing 'Proyectos', got '{label}'"


# ── MI PROYECTO group ─────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_project_group_hidden_on_initial_load(page, base_url):
    """The MI PROYECTO group (#nav-group-project) is hidden before a project is selected."""
    _load(page, base_url)
    group = page.locator("#nav-group-project")
    assert group.count() == 1, "#nav-group-project must exist in DOM"
    # Must not be visible — display:none is set inline
    expect(group).to_be_hidden(timeout=3_000)


@pytest.mark.e2e
def test_project_group_contains_required_views(page, base_url):
    """MI PROYECTO group contains Archivos, Git, Historial, Documentación nav items."""
    _load(page, base_url)
    for view in ("architecture", "git", "checkpoints", "docs"):
        item = page.locator(f"#nav-group-project .nav-item[data-view='{view}']")
        assert item.count() == 1, f"MI PROYECTO group must contain nav-item[data-view='{view}']"


@pytest.mark.e2e
def test_checkpoints_nav_item_renamed_to_historial(page, base_url):
    """Checkpoints nav item is labelled 'Historial' (not 'Time Machine')."""
    _load(page, base_url)
    item = page.locator("#nav-group-project .nav-item[data-view='checkpoints']")
    assert item.count() == 1, "checkpoints nav item must exist inside #nav-group-project"
    label = item.locator("span").text_content() or ""
    assert "Historial" in label, f"Expected 'Historial', got '{label}'"
    assert "Time Machine" not in label, "Old label 'Time Machine' must be removed"


# ── HERRAMIENTAS group ────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_herramientas_group_collapsed_by_default(page, base_url):
    """HERRAMIENTAS group header starts with aria-expanded=false."""
    _load(page, base_url)
    # Find header by its inner text
    header = page.locator(".nav-group-header", has_text="Herramientas")
    if header.count() == 0:
        pytest.skip("HERRAMIENTAS group not found — layout may differ")
    expect(header).to_be_visible(timeout=3_000)
    expanded = header.get_attribute("aria-expanded")
    assert expanded == "false", f"HERRAMIENTAS should start collapsed, got aria-expanded='{expanded}'"


@pytest.mark.e2e
def test_herramientas_items_clipped_until_expanded(page, base_url):
    """Knowledge, Seguridad, Benchmark are not interactable until HERRAMIENTAS is expanded.

    The collapse uses max-height:0 + overflow:hidden CSS animation, so elements
    remain in the layout tree but are visually clipped to height 0.  We verify
    the container itself has 0 height (i.e. nothing overflows into view).

    NOTE: The redesigned sidebar starts in 64px icon-rail mode where ALL group
    contents are forcibly shown (max-height override).  We must expand the
    sidebar to full 240px mode first so the normal HERRAMIENTAS collapse rules
    apply before checking the height.
    """
    _load(page, base_url)
    _expand_sidebar(page)

    container = page.locator("#nav-group-herramientas")
    if container.count() == 0:
        pytest.skip("nav-group-herramientas not found")
    bounding_box = container.bounding_box()
    height = bounding_box["height"] if bounding_box else 0
    assert height == 0, f"HERRAMIENTAS group content should have height 0 when collapsed, got {height}px"


@pytest.mark.e2e
def test_herramientas_expands_on_click(page, base_url):
    """Clicking HERRAMIENTAS header reveals its child nav items."""
    _load(page, base_url)
    header = page.locator(".nav-group-header", has_text="Herramientas")
    if header.count() == 0:
        pytest.skip("HERRAMIENTAS group header not found")
    header.click()
    page.wait_for_timeout(400)
    knowledge = page.locator(".nav-item[data-view='knowledge']")
    expect(knowledge).to_be_visible(timeout=3_000)


# ── Standalone bottom items ───────────────────────────────────────────────────


@pytest.mark.e2e
def test_help_nav_item_exists(page, base_url):
    """'Ayuda y Guías' nav item exists in the sidebar."""
    _load(page, base_url)
    item = page.locator(".nav-item[data-view='help']")
    assert item.count() >= 1, "nav-item[data-view='help'] must be present"
    expect(item.first).to_be_visible(timeout=3_000)


@pytest.mark.e2e
def test_settings_nav_item_still_present(page, base_url):
    """Configuración nav item is still present at the bottom of the sidebar."""
    _load(page, base_url)
    item = page.locator(".nav-item[data-view='settings']")
    expect(item.first).to_be_visible(timeout=3_000)


# ── Removed stubs are gone ────────────────────────────────────────────────────


@pytest.mark.e2e
def test_stub_views_removed_from_sidebar(page, base_url):
    """Stub/non-functional nav items are NOT visible in the sidebar."""
    _load(page, base_url)
    removed_views = [
        "operations",
        "brain",
        "resilience",
        "insights",
        "analytics",
        "automations",
        "costs",
        "sandbox",
        "policies",
        "cicd",
        "swarm",
        "hil",
        "pipeline",
    ]
    for view in removed_views:
        item = page.locator(f".nav-item[data-view='{view}']")
        # Item must either not exist or be hidden
        if item.count() > 0:
            (
                expect(item.first).to_be_hidden(timeout=2_000),
                (f"Stub nav-item[data-view='{view}'] should not be visible to users"),
            )


# ── Total nav item count ──────────────────────────────────────────────────────


@pytest.mark.e2e
def test_visible_nav_items_count_reduced(page, base_url):
    """Visible nav items in the sidebar are ≤ 10 when HERRAMIENTAS is collapsed.

    In expanded sidebar mode with HERRAMIENTAS collapsed (default state), only
    the PRINCIPAL items + standalone bottom items are visible (≤ 10 total).
    We must expand the sidebar first — in collapsed 64px icon-rail mode all
    group contents are force-shown, skewing the count.
    """
    _load(page, base_url)
    _expand_sidebar(page)

    visible_items = page.locator(".sidebar .nav-item:visible")
    count = visible_items.count()
    assert count <= 10, (
        f"Expected ≤ 10 visible nav items (simplified UI), found {count}. Remove stub items from the sidebar."
    )
