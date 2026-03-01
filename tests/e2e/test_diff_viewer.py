"""
E2E Playwright tests — DiffViewer component (P6).

Scenario:
  1. A minimal HTML page injects the real diff-viewer.js.
  2. Tests verify: hunk rendering, line colors, empty state,
     and the loadForFile() async fetch flow (mocked via page.route).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# HTML template — inlines real diff-viewer.js source
# ---------------------------------------------------------------------------

_COMPONENT_PATH = Path(__file__).parent.parent.parent / "frontend/static/js/components/diff-viewer.js"


def _build_html() -> str:
    js_src = _COMPONENT_PATH.read_text(encoding="utf-8")
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body>
  <div id="output"></div>
  <script>{js_src}</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_diff_viewer_renders_empty_state(page: Page) -> None:
    """render('') produces a .diff-empty element."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        const el = window.DiffViewer.render('');
        document.getElementById('output').appendChild(el);
    }""")

    expect(page.locator(".diff-empty")).to_be_visible()
    expect(page.locator(".diff-empty")).to_have_text("No diff content.")


@pytest.mark.e2e
def test_diff_viewer_renders_hunk_header(page: Page) -> None:
    """Hunk header line appears as .diff-hunk-header element."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        const diff = '@@ -1,3 +1,4 @@\\n context\\n-removed\\n+added\\n';
        const el = window.DiffViewer.render(diff);
        document.getElementById('output').appendChild(el);
    }""")

    header = page.locator(".diff-hunk-header")
    expect(header).to_be_visible()
    expect(header).to_have_text("@@ -1,3 +1,4 @@")


@pytest.mark.e2e
def test_diff_viewer_del_line_has_correct_class(page: Page) -> None:
    """Lines starting with '-' are rendered as tr.diff-del."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        const diff = '@@ -1,1 +1,0 @@\\n-deleted line\\n';
        const el = window.DiffViewer.render(diff);
        document.getElementById('output').appendChild(el);
    }""")

    del_rows = page.locator("tr.diff-del")
    expect(del_rows).to_have_count(1)


@pytest.mark.e2e
def test_diff_viewer_add_line_has_correct_class(page: Page) -> None:
    """Lines starting with '+' are rendered as tr.diff-add."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        const diff = '@@ -0,0 +1,2 @@\\n+first added\\n+second added\\n';
        const el = window.DiffViewer.render(diff);
        document.getElementById('output').appendChild(el);
    }""")

    add_rows = page.locator("tr.diff-add")
    expect(add_rows).to_have_count(2)


@pytest.mark.e2e
def test_diff_viewer_context_line_has_correct_class(page: Page) -> None:
    """Context lines (space-prefixed) are rendered as tr.diff-ctx."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        const diff = '@@ -1,2 +1,2 @@\\n unchanged\\n-old\\n+new\\n';
        const el = window.DiffViewer.render(diff);
        document.getElementById('output').appendChild(el);
    }""")

    ctx_rows = page.locator("tr.diff-ctx")
    expect(ctx_rows).to_have_count(1)


@pytest.mark.e2e
def test_diff_viewer_escapes_html_in_code(page: Page) -> None:
    """Code content is HTML-escaped to prevent XSS."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        const diff = '@@ -0,0 +1,1 @@\\n+<script>alert(1)</script>\\n';
        const el = window.DiffViewer.render(diff);
        document.getElementById('output').appendChild(el);
    }""")

    # No actual <script> tag should be injected
    output = page.locator("#output")
    inner_html = output.inner_html()
    assert "<script>" not in inner_html.lower()
    assert "&lt;script&gt;" in inner_html


@pytest.mark.e2e
def test_diff_viewer_load_for_file_shows_diff(page: Page) -> None:
    """loadForFile() fetches the API and renders the returned diff."""
    page.set_content(_build_html())

    # Mock the git diff API
    diff_text = "@@ -1,1 +1,2 @@\n unchanged\n+extra line\n"
    page.route(
        "**/api/projects/*/git/diff/**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"diff": diff_text, "commit_sha": "abc1234"}),
        ),
    )

    page.evaluate("""async () => {
        const container = document.getElementById('output');
        await window.DiffViewer.loadForFile('myapp', 'src/main.py', container);
    }""")

    expect(page.locator("tr.diff-ctx")).to_have_count(1)
    expect(page.locator("tr.diff-add")).to_have_count(1)


@pytest.mark.e2e
def test_diff_viewer_load_for_file_shows_error_on_failure(page: Page) -> None:
    """loadForFile() shows an error message when the API returns 404."""
    page.set_content(_build_html())

    page.route(
        "**/api/projects/*/git/diff/**",
        lambda route: route.fulfill(status=404, body="Not found"),
    )

    page.evaluate("""async () => {
        const container = document.getElementById('output');
        await window.DiffViewer.loadForFile('badproject', 'x.py', container);
    }""")

    expect(page.locator(".diff-error")).to_be_visible()
