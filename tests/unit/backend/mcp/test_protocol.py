"""Tests for backend.mcp.protocol — JSON-RPC helpers and format converters."""

import json

import pytest

from backend.mcp.protocol import (
    decode,
    encode,
    error_response,
    mcp_tool_to_ollash,
    notification,
    ollash_tool_to_mcp,
    request,
    response,
    server_info,
    tool_result,
)

pytestmark = pytest.mark.unit


class TestMessageBuilders:
    def test_request_structure(self):
        msg = request("tools/list", {"cursor": None}, req_id=42)
        assert msg["jsonrpc"] == "2.0"
        assert msg["method"] == "tools/list"
        assert msg["id"] == 42
        assert msg["params"] == {"cursor": None}

    def test_request_no_params(self):
        msg = request("ping", req_id=1)
        assert "params" not in msg

    def test_notification_no_id(self):
        msg = notification("initialized")
        assert "id" not in msg
        assert msg["method"] == "initialized"

    def test_response_structure(self):
        msg = response({"tools": []}, req_id=5)
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 5
        assert msg["result"] == {"tools": []}

    def test_error_response_structure(self):
        msg = error_response(-32601, "Method not found", req_id=3)
        assert msg["id"] == 3
        assert msg["error"]["code"] == -32601
        assert msg["error"]["message"] == "Method not found"

    def test_error_response_with_data(self):
        msg = error_response(-32602, "Invalid params", req_id=1, data={"field": "name"})
        assert msg["error"]["data"] == {"field": "name"}

    def test_server_info_structure(self):
        info = server_info("myserver", "2.0.0")
        assert info["serverInfo"]["name"] == "myserver"
        assert info["serverInfo"]["version"] == "2.0.0"
        assert "protocolVersion" in info
        assert "capabilities" in info

    def test_tool_result_success(self):
        result = tool_result("hello world")
        assert result["isError"] is False
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "hello world"

    def test_tool_result_error(self):
        result = tool_result("something went wrong", is_error=True)
        assert result["isError"] is True


class TestFormatConverters:
    def test_ollash_to_mcp(self):
        ollash = {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        }
        mcp = ollash_tool_to_mcp(ollash)
        assert mcp["name"] == "read_file"
        assert mcp["description"] == "Read a file"
        assert "inputSchema" in mcp
        assert mcp["inputSchema"]["properties"]["path"]["type"] == "string"
        assert mcp["inputSchema"]["required"] == ["path"]

    def test_mcp_to_ollash(self):
        mcp = {
            "name": "write_file",
            "description": "Write content to a file",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        }
        ollash = mcp_tool_to_ollash(mcp)
        assert ollash["type"] == "function"
        fn = ollash["function"]
        assert fn["name"] == "write_file"
        assert fn["parameters"]["properties"]["path"]["type"] == "string"
        assert fn["parameters"]["required"] == ["path", "content"]

    def test_roundtrip_ollash_mcp_ollash(self):
        original = {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "Execute a shell command",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string", "description": "Shell command"}},
                    "required": ["command"],
                },
            },
        }
        recovered = mcp_tool_to_ollash(ollash_tool_to_mcp(original))
        assert recovered["function"]["name"] == original["function"]["name"]
        assert recovered["function"]["description"] == original["function"]["description"]
        assert recovered["function"]["parameters"]["required"] == ["command"]


class TestEncoding:
    def test_encode_produces_json_newline(self):
        msg = {"jsonrpc": "2.0", "id": 1, "result": {}}
        raw = encode(msg)
        assert raw.endswith(b"\n")
        parsed = json.loads(raw)
        assert parsed["id"] == 1

    def test_decode_bytes(self):
        raw = b'{"jsonrpc":"2.0","id":2,"method":"ping"}\n'
        msg = decode(raw)
        assert msg["method"] == "ping"
        assert msg["id"] == 2

    def test_decode_string(self):
        raw = '{"jsonrpc":"2.0","id":3,"result":{"tools":[]}}'
        msg = decode(raw)
        assert msg["result"]["tools"] == []

    def test_encode_decode_roundtrip(self):
        original = request("tools/list", req_id=99)
        recovered = decode(encode(original))
        assert recovered["method"] == "tools/list"
        assert recovered["id"] == 99
