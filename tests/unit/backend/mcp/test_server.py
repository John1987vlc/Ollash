"""Tests for backend.mcp.server — MCPServer message dispatch."""

import json
from io import BytesIO
from unittest.mock import patch

import pytest

from backend.mcp.protocol import encode, request
from backend.mcp.server import MCPServer

pytestmark = pytest.mark.unit


@pytest.fixture
def server():
    """MCPServer with an empty tool catalog (no real Ollash tools loaded)."""
    srv = MCPServer()
    srv._tools_cache = []  # skip discover_tools() in tests
    return srv


class TestInitialize:
    def test_initialize_returns_server_info(self, server):
        msg = request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
            req_id=1,
        )
        resp = server.handle(msg)
        assert resp is not None
        assert resp["id"] == 1
        result = resp["result"]
        assert result["serverInfo"]["name"] == "ollash"
        assert "protocolVersion" in result
        assert "capabilities" in result

    def test_initialize_sets_initialized_flag(self, server):
        assert server._initialized is False
        server.handle(request("initialize", {}, req_id=1))
        assert server._initialized is True


class TestPing:
    def test_ping_returns_empty_result(self, server):
        resp = server.handle(request("ping", req_id=2))
        assert resp is not None
        assert resp["result"] == {}
        assert resp["id"] == 2


class TestToolsList:
    def test_tools_list_empty(self, server):
        resp = server.handle(request("tools/list", req_id=3))
        assert resp is not None
        assert "result" in resp
        assert resp["result"]["tools"] == []

    def test_tools_list_returns_catalog(self, server):
        server._tools_cache = [
            {"name": "read_file", "description": "Read", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "write_file", "description": "Write", "inputSchema": {"type": "object", "properties": {}}},
        ]
        resp = server.handle(request("tools/list", req_id=4))
        tools = resp["result"]["tools"]
        assert len(tools) == 2
        assert tools[0]["name"] == "read_file"


class TestToolsCall:
    def test_unknown_tool_returns_error(self, server):
        server._tools_cache = []
        resp = server.handle(request("tools/call", {"name": "nonexistent", "arguments": {}}, req_id=5))
        assert resp is not None
        assert "error" in resp
        assert resp["error"]["code"] == -32001  # ERR_TOOL_NOT_FOUND

    def test_known_tool_calls_executor(self, server):
        server._tools_cache = [
            {"name": "git_status", "description": "Git", "inputSchema": {"type": "object", "properties": {}}}
        ]
        with patch.object(server._executor, "execute", return_value="On branch master") as mock_exec:
            resp = server.handle(request("tools/call", {"name": "git_status", "arguments": {}}, req_id=6))
        assert resp is not None
        assert "result" in resp
        mock_exec.assert_called_once_with("git_status", {})
        assert "On branch master" in resp["result"]["content"][0]["text"]

    def test_tool_execution_error_returns_isError_true(self, server):
        server._tools_cache = [{"name": "bad_tool", "description": "Fails", "inputSchema": {}}]
        with patch.object(server._executor, "execute", side_effect=RuntimeError("boom")):
            resp = server.handle(request("tools/call", {"name": "bad_tool", "arguments": {}}, req_id=7))
        assert resp is not None
        assert "result" in resp
        assert resp["result"]["isError"] is True


class TestNotifications:
    def test_notification_returns_none(self, server):
        """Notifications (no id) must not produce a response."""
        msg = {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {}}
        result = server.handle(msg)
        assert result is None


class TestUnknownMethod:
    def test_unknown_method_returns_method_not_found(self, server):
        resp = server.handle(request("unknown/method", req_id=8))
        assert resp is not None
        assert "error" in resp
        assert resp["error"]["code"] == -32601  # ERR_METHOD_NOT_FOUND


class TestRunLoop:
    def test_run_processes_messages(self, server):
        """run() must dispatch messages and write responses to stdout buffer."""
        msgs = [
            request("ping", req_id=10),
            request("tools/list", req_id=11),
        ]
        stdin_data = b"".join(encode(m) for m in msgs)
        stdin = BytesIO(stdin_data)
        stdout = BytesIO()

        server._in = stdin
        server._out = stdout

        server.run()

        stdout.seek(0)
        output = stdout.read().decode()
        lines = [ln for ln in output.strip().split("\n") if ln]

        # Should have: 1 initialized notification + 2 responses
        assert len(lines) >= 2
        parsed = [json.loads(ln) for ln in lines]
        ids = [m.get("id") for m in parsed if "id" in m]
        assert 10 in ids
        assert 11 in ids
