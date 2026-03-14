"""MCP JSON-RPC 2.0 protocol helpers.

Covers the subset of MCP 1.0 used by Ollash:
  initialize / initialized / ping
  tools/list / tools/call
  notifications/cancelled

Reference: https://spec.modelcontextprotocol.io/specification/
"""

from __future__ import annotations

import json
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MCP_VERSION = "2024-11-05"
JSONRPC_VERSION = "2.0"

# Capability names
CAP_TOOLS = "tools"
CAP_RESOURCES = "resources"
CAP_PROMPTS = "prompts"

# Error codes (JSON-RPC standard + MCP extensions)
ERR_PARSE_ERROR = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603
ERR_TOOL_NOT_FOUND = -32001
ERR_TOOL_EXEC_FAILED = -32002


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------


def request(method: str, params: dict | None = None, req_id: int | str = 1) -> dict:
    msg: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def notification(method: str, params: dict | None = None) -> dict:
    msg: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def response(result: Any, req_id: int | str = 1) -> dict:
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "result": result}


def error_response(code: int, message: str, req_id: int | str | None = None, data: Any = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "error": err}


# ---------------------------------------------------------------------------
# Standard MCP results
# ---------------------------------------------------------------------------


def server_info(name: str = "ollash", version: str = "1.0.0") -> dict:
    return {
        "protocolVersion": MCP_VERSION,
        "capabilities": {
            CAP_TOOLS: {"listChanged": False},
        },
        "serverInfo": {"name": name, "version": version},
    }


def tool_result(content: str, is_error: bool = False) -> dict:
    """Wrap a tool execution result in MCP format."""
    return {
        "content": [{"type": "text", "text": content}],
        "isError": is_error,
    }


# ---------------------------------------------------------------------------
# Format converters — Ollash ↔ MCP
# ---------------------------------------------------------------------------


def ollash_tool_to_mcp(tool_def: dict) -> dict:
    """Convert an Ollash/Ollama function definition to MCP tool schema.

    Ollash format:
        {type: "function", function: {name, description, parameters: {...}}}

    MCP format:
        {name, description, inputSchema: {type: "object", properties: {}, required: []}}
    """
    fn = tool_def.get("function", {})
    params = fn.get("parameters", {})
    return {
        "name": fn.get("name", ""),
        "description": fn.get("description", ""),
        "inputSchema": {
            "type": "object",
            "properties": params.get("properties", {}),
            "required": params.get("required", []),
        },
    }


def mcp_tool_to_ollash(mcp_tool: dict) -> dict:
    """Convert an MCP tool schema to Ollash/Ollama function definition."""
    schema = mcp_tool.get("inputSchema", {})
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.get("name", ""),
            "description": mcp_tool.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            },
        },
    }


# ---------------------------------------------------------------------------
# I/O helpers (used by both server and client)
# ---------------------------------------------------------------------------


def encode(msg: dict) -> bytes:
    """Encode a message as a newline-terminated JSON bytes."""
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def decode(line: str | bytes) -> dict:
    """Decode a JSON line into a message dict."""
    if isinstance(line, bytes):
        line = line.decode("utf-8")
    return json.loads(line.strip())
