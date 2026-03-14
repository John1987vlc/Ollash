"""Tests for health_router — GET /api/health/"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestHealthRouter:
    def test_health_returns_200(self, client):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": [{"name": "qwen3.5:4b"}]}
            mock_get.return_value = mock_resp

            r = client.get("/api/health/")
            assert r.status_code == 200

    def test_health_ollama_connected(self, client):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": [{"name": "qwen3.5:4b"}, {"name": "qwen3.5:0.8b"}]}
            mock_get.return_value = mock_resp

            r = client.get("/api/health/")
            data = r.json()
            assert data["ollama_connected"] is True
            assert "qwen3.5:4b" in data["models_available"]
            assert data["status"] == "ok"

    def test_health_ollama_down(self, client):
        with patch("requests.get", side_effect=ConnectionError("refused")):
            r = client.get("/api/health/")
            assert r.status_code == 200
            data = r.json()
            assert data["ollama_connected"] is False
            assert data["status"] == "degraded"

    def test_health_returns_system_metrics(self, client):
        with patch("requests.get", side_effect=ConnectionError()):
            r = client.get("/api/health/")
            data = r.json()
            assert "cpu_percent" in data
            assert "ram_percent" in data

    def test_health_latency_included_when_connected(self, client):
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": []}
            mock_get.return_value = mock_resp

            r = client.get("/api/health/")
            data = r.json()
            assert data["ollama_latency_ms"] is not None
            assert data["ollama_latency_ms"] >= 0
