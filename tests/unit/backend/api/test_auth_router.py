"""Tests for auth_router — register, login, me, api-keys."""

import uuid

import pytest

pytestmark = pytest.mark.unit


def _uid():
    """Short unique suffix to avoid username collisions across tests."""
    return uuid.uuid4().hex[:8]


class TestRegister:
    def test_register_success(self, client):
        name = f"alice_{_uid()}"
        r = client.post("/api/auth/register", json={"username": name, "password": "secret123"})
        assert r.status_code == 201
        data = r.json()
        assert data["username"] == name
        assert "user_id" in data

    def test_register_duplicate(self, client):
        name = f"bob_{_uid()}"
        client.post("/api/auth/register", json={"username": name, "password": "pass1234"})
        r = client.post("/api/auth/register", json={"username": name, "password": "pass1234"})
        assert r.status_code == 409

    def test_register_short_username(self, client):
        r = client.post("/api/auth/register", json={"username": "ab", "password": "pass1234"})
        assert r.status_code in (400, 422)

    def test_register_short_password(self, client):
        name = f"carol_{_uid()}"
        r = client.post("/api/auth/register", json={"username": name, "password": "abc"})
        assert r.status_code in (400, 422)


class TestLogin:
    def test_login_success(self, client):
        name = f"dave_{_uid()}"
        client.post("/api/auth/register", json={"username": name, "password": "pass1234"})
        r = client.post("/api/auth/login", json={"username": name, "password": "pass1234"})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == name

    def test_login_wrong_password(self, client):
        name = f"eve_{_uid()}"
        client.post("/api/auth/register", json={"username": name, "password": "correct"})
        r = client.post("/api/auth/login", json={"username": name, "password": "wrong"})
        assert r.status_code == 401

    def test_login_nonexistent_user(self, client):
        r = client.post("/api/auth/login", json={"username": f"ghost_{_uid()}", "password": "pass"})
        assert r.status_code == 401


class TestMe:
    def _get_token(self, client):
        name = f"frank_{_uid()}"
        client.post("/api/auth/register", json={"username": name, "password": "pass1234"})
        r = client.post("/api/auth/login", json={"username": name, "password": "pass1234"})
        return r.json()["access_token"], name

    def test_me_with_valid_token(self, client):
        token, name = self._get_token(client)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["username"] == name

    def test_me_without_token(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_with_invalid_token(self, client):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer badtoken"})
        assert r.status_code == 401


class TestApiKeys:
    def _auth_headers(self, client):
        name = f"grace_{_uid()}"
        client.post("/api/auth/register", json={"username": name, "password": "pass1234"})
        r = client.post("/api/auth/login", json={"username": name, "password": "pass1234"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_create_api_key(self, client):
        headers = self._auth_headers(client)
        r = client.post("/api/auth/api-keys", json={"name": "my-key"}, headers=headers)
        assert r.status_code == 201
        data = r.json()
        assert "key" in data
        assert data["key"].startswith("ollash_")

    def test_list_api_keys(self, client):
        headers = self._auth_headers(client)
        client.post("/api/auth/api-keys", json={"name": "k1"}, headers=headers)
        r = client.get("/api/auth/api-keys", headers=headers)
        assert r.status_code == 200
        body = r.json()
        keys = body.get("api_keys", body) if isinstance(body, dict) else body
        assert len(keys) >= 1
        assert keys[0]["name"] == "k1"
        # raw key must not be exposed in list endpoint
        assert "key" not in keys[0]

    def test_delete_api_key(self, client):
        headers = self._auth_headers(client)
        created = client.post("/api/auth/api-keys", json={"name": "temp"}, headers=headers).json()
        key_id = created["key_id"]
        r = client.delete(f"/api/auth/api-keys/{key_id}", headers=headers)
        assert r.status_code in (200, 204)

    def test_create_key_without_auth(self, client):
        r = client.post("/api/auth/api-keys", json={"name": "k"})
        assert r.status_code == 401
