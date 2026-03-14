"""Tests for privacy_router — status (public) + audit (auth required)."""

import uuid

import pytest

pytestmark = pytest.mark.unit


def _auth_headers(client):
    name = f"priv_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"username": name, "password": "pass1234"})
    r = client.post("/api/auth/login", json={"username": name, "password": "pass1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestPrivacyStatus:
    def test_status_no_auth_required(self, client):
        """GET /api/privacy/status must be public (used by the UI badge)."""
        r = client.get("/api/privacy/status")
        assert r.status_code == 200

    def test_status_returns_required_fields(self, client):
        r = client.get("/api/privacy/status")
        data = r.json()
        assert "is_local" in data
        assert "ollama_url" in data
        assert "allowed_hosts" in data
        assert "mode" in data

    def test_status_mode_consistent_with_is_local(self, client):
        """mode field must be consistent with is_local flag."""
        r = client.get("/api/privacy/status")
        data = r.json()
        if data["is_local"]:
            assert data["mode"] == "local"
        else:
            assert data["mode"] == "remote"

    def test_status_mode_values(self, client):
        r = client.get("/api/privacy/status")
        assert r.json()["mode"] in ("local", "remote")


class TestPrivacyAudit:
    def test_audit_requires_auth(self, client):
        r = client.get("/api/privacy/audit")
        assert r.status_code == 401

    def test_audit_returns_summary_and_log(self, client):
        headers = _auth_headers(client)
        r = client.get("/api/privacy/audit", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert "log" in data

    def test_audit_summary_fields(self, client):
        headers = _auth_headers(client)
        r = client.get("/api/privacy/audit", headers=headers)
        summary = r.json()["summary"]
        assert "total_calls" in summary
        assert "local_calls" in summary
        assert "external_calls" in summary
        assert "is_clean" in summary
        assert "allowed_hosts" in summary

    def test_audit_log_is_list(self, client):
        headers = _auth_headers(client)
        r = client.get("/api/privacy/audit", headers=headers)
        assert isinstance(r.json()["log"], list)


class TestPrivacyClear:
    def test_clear_requires_auth(self, client):
        r = client.post("/api/privacy/clear")
        assert r.status_code == 401

    def test_clear_returns_204(self, client):
        headers = _auth_headers(client)
        r = client.post("/api/privacy/clear", headers=headers)
        assert r.status_code == 204
