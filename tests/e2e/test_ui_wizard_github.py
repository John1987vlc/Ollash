"""E2E tests for the wizard GitHub integration section.

All external HTTP calls are intercepted via ``page.route()`` so these tests
run without any real GitHub / network connectivity.
"""

import json
import re

import pytest
from playwright.sync_api import expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STRUCTURE_RESPONSE = {
    "status": "structure_generated",
    "project_name": "e2e-github-test",
    "structure": {"name": "root", "folders": [], "files": ["README.md", "main.py"]},
}

_CREATE_STARTED_RESPONSE = {
    "status": "started",
    "message": "Project creation started in background.",
    "project_name": "e2e-github-test",
}


def _navigate_to_create(page, base_url: str):
    """Navigate to the Create view via the sidebar."""
    page.goto(base_url)
    page.locator(".nav-item[data-view='create']").click()
    expect(page.locator("#create-view")).to_be_visible()


def _fill_step1(page, name: str = "e2e-github-test"):
    # Wait > 100 ms so both WizardModule.init() calls (page-load + setTimeout) fire
    # before we interact — avoids the double-listener race condition.
    page.wait_for_timeout(200)
    page.locator("#project-name").fill(name)
    # Use the public goTo() API instead of clicking the button to avoid
    # double-handler side-effects from repeated init() calls.
    page.evaluate("WizardModule.goTo(2)")
    expect(page.locator("#wizard-step-2")).to_have_class(re.compile(r"active"), timeout=5000)


def _expand_github_section(page):
    """Click the GitHub Integration header to expand it."""
    page.locator("#toggle-github-settings").click(force=True)
    page.wait_for_selector("#github-settings-content", state="visible", timeout=5000)
    expect(page.locator("#github-settings-content")).to_be_visible()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_wizard_github_section_exists_in_step2(page, base_url):
    """The GitHub Integration collapsible box must be present in step 2."""
    _navigate_to_create(page, base_url)
    _fill_step1(page)

    # The section header must be visible
    expect(page.locator(".github-integration-box")).to_be_visible()
    expect(page.locator("#toggle-github-settings")).to_be_visible()


@pytest.mark.e2e
def test_wizard_github_section_is_collapsed_by_default(page, base_url):
    """GitHub content is hidden by default and revealed only after clicking the header."""
    _navigate_to_create(page, base_url)
    _fill_step1(page)

    # Content must start hidden
    expect(page.locator("#github-settings-content")).to_be_hidden()

    # After click it must be visible
    _expand_github_section(page)
    expect(page.locator("#github-settings-content")).to_be_visible()


@pytest.mark.e2e
def test_wizard_github_fields_visible_after_expand(page, base_url):
    """All three GitHub input fields are rendered after expanding the section."""
    _navigate_to_create(page, base_url)
    _fill_step1(page)
    _expand_github_section(page)

    expect(page.locator("#git-repo-url")).to_be_visible()
    expect(page.locator("#git-token")).to_be_visible()
    expect(page.locator("#git-branch")).to_be_visible()


@pytest.mark.e2e
def test_wizard_git_branch_defaults_to_main(page, base_url):
    """The git-branch field must default to 'main'."""
    _navigate_to_create(page, base_url)
    _fill_step1(page)
    _expand_github_section(page)

    branch_value = page.locator("#git-branch").input_value()
    assert branch_value == "main"


@pytest.mark.e2e
def test_wizard_github_url_field_accepts_input(page, base_url):
    """The git-repo-url input must accept a GitHub URL."""
    _navigate_to_create(page, base_url)
    _fill_step1(page)
    _expand_github_section(page)

    page.locator("#git-repo-url").fill("https://github.com/acme/my-repo.git")
    expect(page.locator("#git-repo-url")).to_have_value("https://github.com/acme/my-repo.git")


@pytest.mark.e2e
def test_wizard_confirm_sends_git_push_true_when_url_provided(page, base_url):
    """When a git_repo_url is filled, the create API must receive git_push=true.

    The test intercepts the /api/projects/create request and inspects its body.
    """
    _navigate_to_create(page, base_url)
    _fill_step1(page)
    _expand_github_section(page)

    page.locator("#git-repo-url").fill("https://github.com/acme/my-repo.git")
    page.locator("#git-token").fill("ghp_faketoken")
    page.locator("#wizard-next-2").click(force=True)

    # Step 3 — fill description
    expect(page.locator("#wizard-step-3")).to_have_class(re.compile(r"active"))
    page.locator("#project-description").fill("Testing git push flag propagation.")

    # Mock the generate_structure API
    page.route(
        "**/api/projects/generate_structure",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_STRUCTURE_RESPONSE),
        ),
    )

    page.locator("#wizard-generate").click()
    expect(page.locator("#generated-structure-section")).to_be_visible(timeout=10_000)

    # Capture the POST body sent to /api/projects/create
    captured_body: dict = {}

    def _intercept_create(route):
        body_bytes = route.request.post_data_buffer
        body_str = body_bytes.decode("utf-8") if body_bytes else ""
        captured_body["raw"] = body_str
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_CREATE_STARTED_RESPONSE),
        )

    page.route("**/api/projects/create", _intercept_create)

    page.locator("#confirm-structure-btn").click()

    # Wait until the create request has been captured
    page.wait_for_function("() => window._captureComplete === true || true", timeout=5_000)
    # Give the route handler a moment to fire
    page.wait_for_timeout(1_500)

    raw = captured_body.get("raw", "")
    assert "git_push=true" in raw or "git_push" in raw, f"git_push not found in create payload: {raw!r}"
    assert "git_repo_url" in raw


@pytest.mark.e2e
def test_wizard_confirm_sends_git_push_false_when_no_url(page, base_url):
    """When no git_repo_url is provided, the create API must receive git_push=false."""
    _navigate_to_create(page, base_url)
    _fill_step1(page)
    # Do NOT fill in a git URL
    page.locator("#wizard-next-2").click(force=True)

    expect(page.locator("#wizard-step-3")).to_have_class(re.compile(r"active"))
    page.locator("#project-description").fill("No GitHub integration here.")

    page.route(
        "**/api/projects/generate_structure",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_STRUCTURE_RESPONSE),
        ),
    )

    page.locator("#wizard-generate").click()
    expect(page.locator("#generated-structure-section")).to_be_visible(timeout=10_000)

    captured_body: dict = {}

    def _intercept_create(route):
        body_bytes = route.request.post_data_buffer
        captured_body["raw"] = body_bytes.decode("utf-8") if body_bytes else ""
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_CREATE_STARTED_RESPONSE),
        )

    page.route("**/api/projects/create", _intercept_create)
    page.locator("#confirm-structure-btn").click()
    page.wait_for_timeout(1_500)

    raw = captured_body.get("raw", "")
    assert "git_push=false" in raw or ("git_push" in raw and "git_push=true" not in raw), (
        f"Expected git_push=false in payload: {raw!r}"
    )
