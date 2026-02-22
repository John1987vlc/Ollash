"""Tests for the Common Blueprint and modular page rendering."""

import pytest


@pytest.mark.unit
def test_index_route(client):
    """Test that the root URL renders the main index page."""
    response = client.get("/")
    assert response.status_code == 200
    # Check for content from base.html or index.html
    assert b"Ollash" in response.data
    assert b"sidebar" in response.data


@pytest.mark.unit
@pytest.mark.parametrize(
    "path,view_id",
    [
        ("/chat", b"chat-view"),
        ("/projects", b"projects-view"),
        ("/settings", b"settings-view"),
        ("/architecture", b"architecture-view"),
        ("/docs", b"docs-view"),
        ("/costs", b"costs-view"),
        ("/create", b"create-view"),
        ("/benchmark", b"benchmark-view"),
        ("/automations", b"automations-view"),
        ("/brain", b"brain-view"),
        ("/plugins", b"plugins-view"),
        ("/prompts", b"prompts-view"),
        ("/audit", b"audit-view"),
        ("/knowledge", b"knowledge-view"),
        ("/tuning", b"tuning-view"),
        ("/policies", b"policies-view"),
        ("/fragments", b"fragments-view"),
    ],
)
def test_modular_page_routes(client, path, view_id):
    """Test that each modular page route is accessible and contains its specific view ID."""
    response = client.get(path)
    assert response.status_code == 200
    assert view_id in response.data


@pytest.mark.unit
def test_api_status_check(client, mock_ollama):
    """Test the status check API with a mocked response."""
    from unittest.mock import patch, MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "qwen3-coder:30b"}]}

    with patch("requests.get", return_value=mock_resp):
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert "models" in data
        # Flexibility for :latest suffix
        model_names = [m.split(":")[0] for m in data["models"]]
        assert "qwen3-coder" in model_names


@pytest.mark.unit
def test_settings_page_has_no_inline_scripts(client):
    """
    Verifica que settings.html no contiene bloques <script> con JS inline.
    El script loadHealth() fue movido a frontend/static/js/pages/settings.js
    como parte de las mejoras de UI/UX (extracción de scripts inline).
    """
    response = client.get("/settings")
    assert response.status_code == 200

    html = response.data.decode("utf-8")

    # The old inline function must not appear in the rendered HTML
    assert "async function loadHealth()" not in html, (
        "Inline 'loadHealth' function must be removed from settings.html and moved to settings.js"
    )

    # The external script reference must be present instead
    assert "settings.js" in html, (
        "settings.html must include a <script src='.../settings.js'> tag pointing to the external module"
    )
