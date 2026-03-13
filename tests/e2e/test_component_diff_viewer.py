"""
E2E Playwright tests — DiffViewer component (component-isolated).

Injects diff-viewer.js into a minimal HTML page via set_content().
No server or Ollama instance required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

_JS_PATH = Path(__file__).parent.parent.parent / "frontend/static/js/components/diff-viewer.js"


def _html() -> str:
    js_src = _JS_PATH.read_text(encoding="utf-8")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  .diff-viewer {{ font-family: monospace; }}
  .diff-hunk-header {{ background: #f0f0f0; }}
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


@pytest.mark.e2e
def test_renders_empty_state(page_isolated: Page) -> None:
    """Renders a friendly message when diff is empty."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        const el = window.DiffViewer.render('');
        document.getElementById('output').appendChild(el);
    }""")
    expect(page_isolated.locator(".diff-empty")).to_have_text("No diff content.")


@pytest.mark.e2e
def test_renders_hunk_header(page_isolated: Page) -> None:
    """Hunk markers (@@ ...) are rendered in a header element."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        const el = window.DiffViewer.render('@@ -1,1 +1,1 @@\\n context');
        document.getElementById('output').appendChild(el);
    }""")
    expect(page_isolated.locator(".diff-hunk-header")).to_have_text("@@ -1,1 +1,1 @@")


@pytest.mark.e2e
def test_del_line_has_correct_class(page_isolated: Page) -> None:
    """Lines starting with '-' are rendered as tr.diff-del."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        const el = window.DiffViewer.render('@@ -1,1 +1,0 @@\\n-deleted line');
        document.getElementById('output').appendChild(el);
    }""")
    del_rows = page_isolated.locator("tr.diff-del")
    expect(del_rows).to_have_count(1)
    expect(del_rows.first).to_contain_text("deleted line")


@pytest.mark.e2e
def test_add_line_has_correct_class(page_isolated: Page) -> None:
    """Lines starting with '+' are rendered as tr.diff-add."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        const el = window.DiffViewer.render('@@ -1,0 +1,1 @@\\n+added line');
        document.getElementById('output').appendChild(el);
    }""")
    add_rows = page_isolated.locator("tr.diff-add")
    expect(add_rows).to_have_count(1)
    expect(add_rows.first).to_contain_text("added line")


@pytest.mark.e2e
def test_context_line_has_correct_class(page_isolated: Page) -> None:
    """Context lines (space-prefixed) are rendered as tr.diff-ctx."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        const el = window.DiffViewer.render('@@ -1,2 +1,2 @@\\n unchanged\\n-old\\n+new');
        document.getElementById('output').appendChild(el);
    }""")
    expect(page_isolated.locator("tr.diff-ctx")).to_have_count(1)


@pytest.mark.e2e
def test_html_escaping(page_isolated: Page) -> None:
    """HTML tags in the diff are escaped to prevent XSS."""
    page_isolated.set_content(_html())
    page_isolated.evaluate("""() => {
        const el = window.DiffViewer.render('@@ -1,1 +1,1 @@\\n <script>alert(1)</script>');
        document.getElementById('output').appendChild(el);
    }""")
    html = page_isolated.locator(".diff-code").first.inner_html()
    assert "&lt;script&gt;" in html, "Script tag must be HTML-escaped"


@pytest.mark.e2e
def test_load_for_file_shows_diff(page_isolated: Page) -> None:
    """loadForFile() fetches the API and renders the returned diff."""
    page_isolated.set_content(_html())
    diff_text = "@@ -1,1 +1,2 @@\n unchanged\n+extra line"
    page_isolated.route(
        "**/api/projects/**/git/diff/**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"diff": diff_text, "commit_sha": "abc1234"}),
        ),
    )
    page_isolated.evaluate("""async () => {
        const orig = window.fetch;
        window.fetch = (url, opts) => {
            if (url.startsWith('/api')) return orig('http://localhost' + url, opts);
            return orig(url, opts);
        };
        const container = document.getElementById('output');
        await window.DiffViewer.loadForFile('myapp', 'src/main.py', container);
    }""")
    expect(page_isolated.locator("tr.diff-ctx")).to_have_count(1)
    expect(page_isolated.locator("tr.diff-add")).to_have_count(1)


@pytest.mark.e2e
def test_load_for_file_error(page_isolated: Page) -> None:
    """loadForFile() shows an error element on HTTP 500."""
    page_isolated.set_content(_html())
    page_isolated.route("**/api/projects/**", lambda route: route.fulfill(status=500))
    page_isolated.evaluate("""async () => {
        const orig = window.fetch;
        window.fetch = (url, opts) => {
            if (url.startsWith('/api')) return orig('http://localhost' + url, opts);
            return orig(url, opts);
        };
        const container = document.getElementById('output');
        await window.DiffViewer.loadForFile('p', 'f', container);
    }""")
    expect(page_isolated.locator(".diff-error")).to_be_visible()
    expect(page_isolated.locator(".diff-error")).to_contain_text("HTTP 500")
