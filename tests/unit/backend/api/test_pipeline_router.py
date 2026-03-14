"""Tests for pipeline_router — phases catalog, pipeline CRUD, run API."""

import uuid

import pytest

pytestmark = pytest.mark.unit


def _auth_headers(client):
    """Register + login a unique test user and return auth headers."""
    name = f"pipe_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"username": name, "password": "pass1234"})
    r = client.post("/api/auth/login", json={"username": name, "password": "pass1234"})
    token = r.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


class TestPhasesCatalog:
    def test_list_phases_no_auth_required(self, client):
        """GET /api/pipelines/phases is public."""
        r = client.get("/api/pipelines/phases")
        assert r.status_code == 200
        phases = r.json()
        assert isinstance(phases, list)
        assert len(phases) >= 10

    def test_phases_have_required_fields(self, client):
        r = client.get("/api/pipelines/phases")
        for phase in r.json():
            assert "id" in phase
            assert "label" in phase
            assert "category" in phase
            assert "description" in phase

    def test_phases_include_security_scan(self, client):
        r = client.get("/api/pipelines/phases")
        ids = [p["id"] for p in r.json()]
        assert "SecurityScanPhase" in ids

    def test_phases_include_senior_review(self, client):
        r = client.get("/api/pipelines/phases")
        ids = [p["id"] for p in r.json()]
        assert "SeniorReviewPhase" in ids


class TestPipelineCRUD:
    def test_list_pipelines_requires_auth(self, client):
        r = client.get("/api/pipelines")
        assert r.status_code == 401

    def test_list_pipelines_with_auth(self, client):
        headers = _auth_headers(client)
        r = client.get("/api/pipelines", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_builtins_seeded(self, client):
        headers = _auth_headers(client)
        r = client.get("/api/pipelines", headers=headers)
        names = [p["name"] for p in r.json()]
        assert "Quick Review" in names
        assert "Refactor" in names

    def test_create_pipeline(self, client):
        headers = _auth_headers(client)
        r = client.post(
            "/api/pipelines",
            json={"name": "My Pipeline", "phases": ["SecurityScanPhase", "SeniorReviewPhase"]},
            headers=headers,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "My Pipeline"
        assert data["phases"] == ["SecurityScanPhase", "SeniorReviewPhase"]
        assert "id" in data

    def test_create_pipeline_unknown_phase(self, client):
        headers = _auth_headers(client)
        r = client.post(
            "/api/pipelines",
            json={"name": "Bad", "phases": ["FakePhase"]},
            headers=headers,
        )
        assert r.status_code == 400

    def test_create_pipeline_empty_name(self, client):
        headers = _auth_headers(client)
        r = client.post(
            "/api/pipelines",
            json={"name": "  ", "phases": ["SecurityScanPhase"]},
            headers=headers,
        )
        assert r.status_code == 400

    def test_get_pipeline(self, client):
        headers = _auth_headers(client)
        created = client.post(
            "/api/pipelines",
            json={"name": "Fetchable", "phases": ["VerificationPhase"]},
            headers=headers,
        ).json()
        r = client.get(f"/api/pipelines/{created['id']}", headers=headers)
        assert r.status_code == 200
        assert r.json()["name"] == "Fetchable"

    def test_get_nonexistent_pipeline(self, client):
        headers = _auth_headers(client)
        r = client.get("/api/pipelines/99999", headers=headers)
        assert r.status_code == 404

    def test_update_pipeline(self, client):
        headers = _auth_headers(client)
        created = client.post(
            "/api/pipelines",
            json={"name": "Old Name", "phases": ["SecurityScanPhase"]},
            headers=headers,
        ).json()
        r = client.put(
            f"/api/pipelines/{created['id']}",
            json={"name": "New Name", "phases": ["SeniorReviewPhase", "VerificationPhase"]},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "New Name"
        assert len(r.json()["phases"]) == 2

    def test_delete_user_pipeline(self, client):
        headers = _auth_headers(client)
        created = client.post(
            "/api/pipelines",
            json={"name": "Deletable", "phases": ["SecurityScanPhase"]},
            headers=headers,
        ).json()
        r = client.delete(f"/api/pipelines/{created['id']}", headers=headers)
        assert r.status_code == 204

    def test_delete_builtin_pipeline_blocked(self, client):
        headers = _auth_headers(client)
        pipelines = client.get("/api/pipelines", headers=headers).json()
        builtin = next((p for p in pipelines if p.get("builtin")), None)
        if builtin is None:
            pytest.skip("No builtin pipeline found")
        r = client.delete(f"/api/pipelines/{builtin['id']}", headers=headers)
        assert r.status_code == 404
