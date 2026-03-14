"""MCP Router — REST API for MCP server management + HTTP tool bridge.

Endpoints (MCP Server — Ollash as server)
------------------------------------------
GET  /api/mcp/tools             — list all Ollash tools in MCP format
POST /api/mcp/call              — execute an Ollash tool by name (test endpoint)

Endpoints (MCP Client — Ollash as client)
------------------------------------------
GET  /api/mcp/servers           — list configured external MCP servers
POST /api/mcp/servers           — add / configure an external MCP server
DELETE /api/mcp/servers/{name}  — remove external server config
POST /api/mcp/servers/{name}/connect    — connect / reconnect
POST /api/mcp/servers/{name}/disconnect — disconnect
GET  /api/mcp/servers/{name}/tools      — list tools from that server
POST /api/mcp/servers/{name}/call       — call a tool on that server

Endpoints (Status)
------------------
GET  /api/mcp/status — full status: server capabilities + all client connections
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_current_user_dep
from backend.mcp.protocol import ollash_tool_to_mcp

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

_DB_PATH = Path(os.environ.get("OLLASH_ROOT_DIR", ".ollash")) / "mcp.db"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ServerAdd(BaseModel):
    name: str
    transport: str = "stdio"  # "stdio" or "http"
    command: list[str] = []  # for stdio transport
    url: str = ""  # for http transport
    env: dict[str, str] = {}


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict = {}


class ServerToolCallRequest(BaseModel):
    tool_name: str
    arguments: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store():
    from backend.mcp.server_store import MCPServerStore

    return MCPServerStore(_DB_PATH)


def _manager():
    from backend.mcp.client import mcp_client_manager

    return mcp_client_manager


def _ollash_tools() -> list[dict]:
    """Return all Ollash tools in MCP format."""
    try:
        from backend.utils.core.tools.tool_decorator import get_discovered_definitions
        from backend.utils.core.tools.tool_registry import discover_tools

        discover_tools()
        defs = get_discovered_definitions()
        return [ollash_tool_to_mcp(d) for d in defs]
    except Exception as exc:
        raise HTTPException(500, f"Could not load tools: {exc}") from exc


# ---------------------------------------------------------------------------
# MCP Server endpoints (Ollash as MCP server)
# ---------------------------------------------------------------------------


@router.get("/tools")
def list_ollash_tools(user: dict = Depends(get_current_user_dep)) -> dict:
    """Return all Ollash tools in MCP format (what external clients would see)."""
    tools = _ollash_tools()
    # Also include tools from connected external servers
    for _srv, ext_tools in _manager().all_tools().items():
        tools.extend(ext_tools)
    return {"tools": tools, "total": len(tools)}


@router.post("/call")
def call_ollash_tool(
    body: ToolCallRequest,
    user: dict = Depends(get_current_user_dep),
) -> dict:
    """Execute an Ollash tool by name.  Useful for testing from the web UI."""
    from backend.mcp.server import _ToolExecutor

    executor = _ToolExecutor()
    try:
        output = executor.execute(body.name, body.arguments)
        return {"content": [{"type": "text", "text": str(output)}], "isError": False}
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except Exception as exc:
        return {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True}


@router.get("/status")
def mcp_status(user: dict = Depends(get_current_user_dep)) -> dict:
    """Full MCP status: server info + all client connections."""
    tools = _ollash_tools()
    clients = _manager().list_servers()
    return {
        "server": {
            "name": "ollash",
            "version": "1.0.0",
            "protocol_version": "2024-11-05",
            "tool_count": len(tools),
            "run_command": "python -m backend.mcp",
        },
        "clients": clients,
        "total_external_tools": sum(len(_manager().tools_for_server(s["name"])) for s in clients),
    }


# ---------------------------------------------------------------------------
# MCP Client endpoints (Ollash consuming external servers)
# ---------------------------------------------------------------------------


@router.get("/servers")
def list_servers(user: dict = Depends(get_current_user_dep)) -> list[dict]:
    return _manager().list_servers()


@router.post("/servers", status_code=201)
def add_server(
    body: ServerAdd,
    user: dict = Depends(get_current_user_dep),
) -> dict:
    if body.transport == "stdio" and not body.command:
        raise HTTPException(400, "command is required for stdio transport")
    if body.transport == "http" and not body.url:
        raise HTTPException(400, "url is required for http transport")

    cfg = body.model_dump()
    # Persist to store
    _store().add(
        name=cfg["name"],
        transport=cfg["transport"],
        command=cfg["command"],
        url=cfg["url"],
        env=cfg["env"],
    )
    # Register in live manager
    _manager().add_server(cfg)
    return {"name": body.name, "status": "added"}


@router.delete("/servers/{name}", status_code=204)
def remove_server(name: str, user: dict = Depends(get_current_user_dep)) -> None:
    deleted = _store().delete(name)
    _manager().remove_server(name)
    if not deleted:
        raise HTTPException(404, detail=f"Server '{name}' not found")


@router.post("/servers/{name}/connect")
def connect_server(name: str, user: dict = Depends(get_current_user_dep)) -> dict:
    ok = _manager().connect(name)
    if not ok:
        raise HTTPException(502, detail=f"Could not connect to '{name}'")
    return {"name": name, "connected": True}


@router.post("/servers/{name}/disconnect")
def disconnect_server(name: str, user: dict = Depends(get_current_user_dep)) -> dict:
    _manager().disconnect(name)
    return {"name": name, "connected": False}


@router.get("/servers/{name}/tools")
def server_tools(name: str, user: dict = Depends(get_current_user_dep)) -> dict:
    tools = _manager().tools_for_server(name)
    if not tools and name not in {s["name"] for s in _manager().list_servers()}:
        raise HTTPException(404, detail=f"Server '{name}' not found")
    return {"server": name, "tools": tools, "total": len(tools)}


@router.post("/servers/{name}/call")
def call_server_tool(
    name: str,
    body: ServerToolCallRequest,
    user: dict = Depends(get_current_user_dep),
) -> dict:
    from backend.mcp.client import MCPConnection
    from backend.mcp.server_store import MCPServerStore

    cfg = MCPServerStore(_DB_PATH).get_by_name(name)
    if cfg is None:
        raise HTTPException(404, detail=f"Server '{name}' not found")

    conn = MCPConnection(cfg)
    if not conn.connect():
        raise HTTPException(502, detail=f"Could not connect to '{name}'")

    result = conn.call_tool(body.tool_name, body.arguments)
    conn.disconnect()

    if result is None:
        raise HTTPException(500, detail="No response from external server")
    return result
