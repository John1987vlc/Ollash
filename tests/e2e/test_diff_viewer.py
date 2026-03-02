"""
E2E Playwright tests — Unified Diff Viewer (P6).

Scenario:
  1. Load a minimal page with diff-viewer.js injected.
  2. Provide a raw git diff string to DiffViewer.render().
  3. Verify the generated table has correct row classes (diff-add, diff-del, diff-ctx).
  4. Test loadForFile() with mocked network calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMPONENT_PATH = Path(__file__).parent.parent.parent / "frontend/static/js/components/diff-viewer.js"


def _build_html() -> str:
    js_src = _COMPONENT_PATH.read_text(encoding="utf-8")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  .diff-viewer {{ font-family: monospace; border: 1px solid #ccc; }}
  .diff-hunk-header {{ background: #f0f0f0; padding: 4px; color: #666; }}
  .diff-add {{ background: #e6ffed; }}
  .diff-del {{ background: #ffeef0; }}
  .diff-ctx {{ color: #444; }}
</style>
</head>
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
    """Renders a friendly message when diff is empty."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        const el = window.DiffViewer.render('');
        document.getElementById('output').appendChild(el);
    }""")

    expect(page.locator(".diff-empty")).to_have_text("No diff content.")


@pytest.mark.e2e
def test_diff_viewer_renders_hunk_header(page: Page) -> None:
    """Hunk markers (@@ ...) are rendered in a header div."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        const diff = '@@ -1,1 +1,1 @@\\n context';
        const el = window.DiffViewer.render(diff);
        document.getElementById('output').appendChild(el);
    }""")

    expect(page.locator(".diff-hunk-header")).to_have_text("@@ -1,1 +1,1 @@")


@pytest.mark.e2e
def test_diff_viewer_del_line_has_correct_class(page: Page) -> None:
    """Lines starting with '-' are rendered as tr.diff-del."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        const diff = '@@ -1,1 +1,0 @@\\n-deleted line';
        const el = window.DiffViewer.render(diff);
        document.getElementById('output').appendChild(el);
    }""")

    del_rows = page.locator("tr.diff-del")
    expect(del_rows).to_have_count(1)
    expect(del_rows.first).to_contain_text("deleted line")


@pytest.mark.e2e
def test_diff_viewer_add_line_has_correct_class(page: Page) -> None:
    """Lines starting with '+' are rendered as tr.diff-add."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        const diff = '@@ -1,0 +1,1 @@\\n+added line';
        const el = window.DiffViewer.render(diff);
        document.getElementById('output').appendChild(el);
    }""")

    add_rows = page.locator("tr.diff-add")
    expect(add_rows).to_have_count(1)
    expect(add_rows.first).to_contain_text("added line")


@pytest.mark.e2e
def test_diff_viewer_context_line_has_correct_class(page: Page) -> None:
    """Context lines (space-prefixed) are rendered as tr.diff-ctx."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        // We use a diff without trailing newline to avoid extra ctx line
        const diff = '@@ -1,2 +1,2 @@\\n unchanged\\n-old\\n+new';
        const el = window.DiffViewer.render(diff);
        document.getElementById('output').appendChild(el);
    }""")

    ctx_rows = page.locator("tr.diff-ctx")
    expect(ctx_rows).to_have_count(1)


@pytest.mark.e2e
def test_diff_viewer_escapes_html_in_code(page: Page) -> None:
    """HTML tags in the diff are escaped to prevent XSS/rendering issues."""
    page.set_content(_build_html())

    page.evaluate("""() => {
        const diff = '@@ -1,1 +1,1 @@\\n <script>alert(1)</script>';
        const el = window.DiffViewer.render(diff);
        document.getElementById('output').appendChild(el);
    }""")

    code_td = page.locator(".diff-code").first
    # inner_html() should contain escaped chars
    html = code_td.inner_html()
    assert "&lt;script&gt;" in html


@pytest.mark.e2e
def test_diff_viewer_load_for_file_shows_diff(page: Page) -> None:
    """loadForFile() fetches the API and renders the returned diff."""
    page.set_content(_build_html())

    # Mock the git diff API with absolute URL
    diff_text = "@@ -1,1 +1,2 @@\n unchanged\n+extra line"

    # Use a more inclusive pattern that matches http://localhost/api...
    page.route(
        "**/api/projects/**/git/diff/**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"diff": diff_text, "commit_sha": "abc1234"}),
        ),
    )

    page.on("console", lambda msg: print(f"BROWSER: {msg.text}"))

    page.evaluate("""async () => {
        // Patch fetch for this specific call to avoid about:blank relative path error
        const originalFetch = window.fetch;
        window.fetch = (url, options) => {
            console.log('Fetching:', url);
            if (url.startsWith('/api')) {
                return originalFetch('http://localhost' + url, options);
            }
            return originalFetch(url, options);
        };

        const container = document.getElementById('output');
        try {
            await window.DiffViewer.loadForFile('myapp', 'src/main.py', container);
            console.log('loadForFile completed, HTML:', container.innerHTML);
        } catch (e) {
            console.error('loadForFile failed:', e.message);
        }
    }""")

    expect(page.locator("tr.diff-ctx")).to_have_count(1)
    expect(page.locator("tr.diff-add")).to_have_count(1)


@pytest.mark.e2e
def test_diff_viewer_load_for_file_shows_error_on_failure(page: Page) -> None:
    """Handles API errors gracefully."""
    page.set_content(_build_html())

    page.route("**/api/projects/**", lambda route: route.fulfill(status=500))

    page.evaluate("""async () => {
        const originalFetch = window.fetch;
        window.fetch = (url, options) => {
            if (url.startsWith('/api')) {
                return originalFetch('http://localhost' + url, options);
            }
            return originalFetch(url, options);
        };
        const container = document.getElementById('output');
        await window.DiffViewer.loadForFile('p', 'f', container);
    }""")

    expect(page.locator(".diff-error")).to_be_visible()
    expect(page.locator(".diff-error")).to_contain_text("HTTP 500")
