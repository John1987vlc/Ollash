"""Tests for mcp_router — tools list, server management (auth required)."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _auth_headers(client):
    name = f"mcp_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"username": name, "password": "pass1234"})
    r = client.post("/api/auth/login", json={"username": name, "password": "pass1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestMCPStatus:
    def test_status_requires_auth(self, client):
        r = client.get("/api/mcp/status")
        assert r.status_code == 401

    def test_status_returns_server_info(self, client):
        headers = _auth_headers(client)
        with patch("backend.api.routers.mcp_router._ollash_tools", return_value=[]):
            r = client.get("/api/mcp/status", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "server" in data
        assert data["server"]["name"] == "ollash"
        assert "run_command" in data["server"]
        assert "clients" in data

    def test_status_includes_tool_count(self, client):
        headers = _auth_headers(client)
        fake_tools = [{"name": "tool1"}, {"name": "tool2"}]
        with patch("backend.api.routers.mcp_router._ollash_tools", return_value=fake_tools):
            r = client.get("/api/mcp/status", headers=headers)
        assert r.json()["server"]["tool_count"] == 2


class TestMCPTools:
    def test_tools_requires_auth(self, client):
        r = client.get("/api/mcp/tools")
        assert r.status_code == 401

    def test_tools_returns_list(self, client):
        headers = _auth_headers(client)
        fake_tools = [
            {"name": "read_file", "description": "Read a file", "inputSchema": {"type": "object", "properties": {}}},
        ]
        with patch("backend.api.routers.mcp_router._ollash_tools", return_value=fake_tools):
            r = client.get("/api/mcp/tools", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "tools" in data
        assert "total" in data
        assert data["total"] >= 1


class TestMCPServers:
    def test_list_servers_requires_auth(self, client):
        r = client.get("/api/mcp/servers")
        assert r.status_code == 401

    def test_list_servers_empty(self, client):
        headers = _auth_headers(client)
        r = client.get("/api/mcp/servers", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_add_stdio_server(self, client):
        headers = _auth_headers(client)
        r = client.post(
            "/api/mcp/servers",
            json={"name": "test-fs", "transport": "stdio", "command": ["npx", "mcp-fs"]},
            headers=headers,
        )
        assert r.status_code == 201
        assert r.json()["name"] == "test-fs"

    def test_add_http_server(self, client):
        headers = _auth_headers(client)
        r = client.post(
            "/api/mcp/servers",
            json={"name": "remote-srv", "transport": "http", "url": "http://localhost:3000"},
            headers=headers,
        )
        assert r.status_code == 201

    def test_add_stdio_without_command_fails(self, client):
        headers = _auth_headers(client)
        r = client.post(
            "/api/mcp/servers",
            json={"name": "bad-srv", "transport": "stdio", "command": []},
            headers=headers,
        )
        assert r.status_code == 400

    def test_add_http_without_url_fails(self, client):
        headers = _auth_headers(client)
        r = client.post(
            "/api/mcp/servers",
            json={"name": "bad-http", "transport": "http", "url": ""},
            headers=headers,
        )
        assert r.status_code == 400

    def test_delete_nonexistent_server(self, client):
        headers = _auth_headers(client)
        r = client.delete("/api/mcp/servers/doesnotexist", headers=headers)
        assert r.status_code == 404

    def test_delete_server(self, client):
        headers = _auth_headers(client)
        client.post(
            "/api/mcp/servers",
            json={"name": "del-me", "transport": "stdio", "command": ["echo"]},
            headers=headers,
        )
        r = client.delete("/api/mcp/servers/del-me", headers=headers)
        assert r.status_code == 204


class TestMCPCall:
    def test_call_requires_auth(self, client):
        r = client.post("/api/mcp/call", json={"name": "read_file", "arguments": {}})
        assert r.status_code == 401

    def test_call_unknown_tool(self, client):
        headers = _auth_headers(client)
        with patch("backend.mcp.server._ToolExecutor") as MockExec:
            instance = MagicMock()
            instance.execute.side_effect = KeyError("unknown_tool")
            MockExec.return_value = instance
            r = client.post(
                "/api/mcp/call",
                json={"name": "unknown_tool", "arguments": {}},
                headers=headers,
            )
        assert r.status_code == 404
