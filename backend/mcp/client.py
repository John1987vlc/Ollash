"""MCP Client — connects Ollash to external MCP servers.

Supports two transports:
  stdio  — spawns external MCP server as a subprocess; communicates via
           stdin/stdout (newline-delimited JSON-RPC).
  http   — connects to an HTTP MCP endpoint (GET /sse + POST /messages).
           (Simplified: polls tools/list via POST for now.)

Usage inside Ollash agents
--------------------------
    from backend.mcp.client import mcp_client_manager

    # Get merged tool definitions (Ollama format) from all connected servers
    extra_defs = mcp_client_manager.get_ollash_definitions()

    # Call a tool on whichever server exposes it
    result = mcp_client_manager.call_tool("filesystem_read_file", {"path": "README.md"})

The module-level ``mcp_client_manager`` singleton is auto-populated from the
persisted server store when first accessed (lazy init).
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from backend.mcp.protocol import (
    decode,
    encode,
    mcp_tool_to_ollash,
    request,
    tool_result,
)

logger = logging.getLogger(__name__)

_DB_PATH = Path(os.environ.get("OLLASH_ROOT_DIR", ".ollash")) / "mcp.db"
_CONNECT_TIMEOUT = 10  # seconds
_CALL_TIMEOUT = 30  # seconds


# ---------------------------------------------------------------------------
# Single external server connection
# ---------------------------------------------------------------------------


class MCPConnection:
    """Manages one live connection to an external MCP server."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.name: str = config["name"]
        self.transport: str = config.get("transport", "stdio")
        self.command: list[str] = config.get("command", [])
        self.url: str = config.get("url", "")
        self.env: dict[str, str] = config.get("env", {})

        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._req_counter = 0
        self._tools: list[dict] | None = None  # cached MCP-format tools
        self._connected = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Open the connection. Returns True on success."""
        if self.transport == "stdio":
            return self._connect_stdio()
        if self.transport == "http":
            return self._connect_http()
        logger.error("[MCP client] Unknown transport: %s", self.transport)
        return False

    def _connect_stdio(self) -> bool:
        if not self.command:
            logger.error("[MCP client/%s] No command configured for stdio transport", self.name)
            return False
        try:
            env = {**os.environ, **self.env}
            self._proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            # Send initialize
            resp = self._rpc(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "ollash", "version": "1.0.0"},
                },
            )
            if resp and "result" in resp:
                self._connected = True
                logger.info("[MCP client/%s] Connected via stdio", self.name)
                return True
            return False
        except Exception as exc:
            logger.error("[MCP client/%s] Connection failed: %s", self.name, exc)
            return False

    def _connect_http(self) -> bool:
        """Verify HTTP endpoint is reachable with a tools/list call."""
        try:
            import requests as req

            r = req.post(
                self.url,
                json=request("tools/list", req_id=1),
                timeout=_CONNECT_TIMEOUT,
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
            if "result" in data:
                self._connected = True
                logger.info("[MCP client/%s] Connected via HTTP", self.name)
                return True
        except Exception as exc:
            logger.error("[MCP client/%s] HTTP connection failed: %s", self.name, exc)
        return False

    def disconnect(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                pass
            self._proc = None
        self._connected = False
        self._tools = None

    @property
    def is_connected(self) -> bool:
        if self.transport == "stdio":
            return self._connected and self._proc is not None and self._proc.poll() is None
        return self._connected

    # ------------------------------------------------------------------
    # RPC helpers
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._req_counter += 1
        return self._req_counter

    def _rpc(self, method: str, params: dict | None = None) -> dict | None:
        req_id = self._next_id()
        msg = request(method, params, req_id)

        if self.transport == "stdio":
            return self._rpc_stdio(msg)
        if self.transport == "http":
            return self._rpc_http(msg)
        return None

    def _rpc_stdio(self, msg: dict) -> dict | None:
        if not self._proc:
            return None
        with self._lock:
            try:
                self._proc.stdin.write(encode(msg))  # type: ignore[union-attr]
                self._proc.stdin.flush()  # type: ignore[union-attr]
                # Read response line with timeout via poll
                deadline = time.time() + _CALL_TIMEOUT
                while time.time() < deadline:
                    line = self._proc.stdout.readline()  # type: ignore[union-attr]
                    if line:
                        return decode(line)
                    time.sleep(0.01)
                logger.warning("[MCP client/%s] Timeout waiting for response", self.name)
            except Exception as exc:
                logger.error("[MCP client/%s] RPC error: %s", self.name, exc)
        return None

    def _rpc_http(self, msg: dict) -> dict | None:
        try:
            import requests as req

            r = req.post(
                self.url,
                json=msg,
                timeout=_CALL_TIMEOUT,
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.error("[MCP client/%s] HTTP RPC error: %s", self.name, exc)
        return None

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def list_tools(self, force: bool = False) -> list[dict]:
        """Return MCP-format tool list from the external server."""
        if self._tools is not None and not force:
            return self._tools

        if not self.is_connected and not self.connect():
            return []

        resp = self._rpc("tools/list")
        if resp and "result" in resp:
            self._tools = resp["result"].get("tools", [])
            return self._tools

        return []

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict | None:
        """Call a tool on the external server. Returns MCP tool_result dict or None."""
        if not self.is_connected and not self.connect():
            return None

        resp = self._rpc("tools/call", {"name": tool_name, "arguments": arguments})
        if resp and "result" in resp:
            return resp["result"]
        if resp and "error" in resp:
            err = resp["error"]
            return tool_result(f"MCP error: {err.get('message', err)}", is_error=True)
        return None


# ---------------------------------------------------------------------------
# Connection manager (singleton)
# ---------------------------------------------------------------------------


class MCPClientManager:
    """Manages all external MCP server connections.

    Thread-safe.  Lazily loads configs from the server store on first access.
    """

    def __init__(self) -> None:
        self._connections: dict[str, MCPConnection] = {}
        self._lock = threading.Lock()
        self._loaded = False
        # map tool_name → server_name (populated on first all_tools() call)
        self._tool_index: dict[str, str] = {}

    def _load_from_store(self) -> None:
        """Load enabled server configs from SQLite on first use."""
        if self._loaded:
            return
        self._loaded = True
        try:
            from backend.mcp.server_store import MCPServerStore

            store = MCPServerStore(_DB_PATH)
            for cfg in store.list_enabled():
                self._connections[cfg["name"]] = MCPConnection(cfg)
        except Exception as exc:
            logger.warning("[MCP client] Could not load server configs: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_server(self, config: dict[str, Any]) -> None:
        """Register an external server at runtime (also persisted via the router)."""
        with self._lock:
            name = config["name"]
            self._connections[name] = MCPConnection(config)
            self._tool_index = {}  # invalidate

    def remove_server(self, name: str) -> None:
        with self._lock:
            conn = self._connections.pop(name, None)
            if conn:
                conn.disconnect()
            self._tool_index = {}

    def connect(self, name: str) -> bool:
        self._load_from_store()
        with self._lock:
            conn = self._connections.get(name)
        if conn is None:
            return False
        return conn.connect()

    def disconnect(self, name: str) -> None:
        with self._lock:
            conn = self._connections.get(name)
        if conn:
            conn.disconnect()

    def list_servers(self) -> list[dict[str, Any]]:
        self._load_from_store()
        with self._lock:
            conns = list(self._connections.values())
        return [
            {
                "name": c.name,
                "transport": c.transport,
                "command": c.command,
                "url": c.url,
                "connected": c.is_connected,
            }
            for c in conns
        ]

    def all_tools(self) -> dict[str, list[dict]]:
        """Return {server_name: [mcp_tool, ...]} for all connected servers."""
        self._load_from_store()
        result: dict[str, list[dict]] = {}
        with self._lock:
            conns = list(self._connections.values())
        for conn in conns:
            try:
                tools = conn.list_tools()
                if tools:
                    result[conn.name] = tools
            except Exception as exc:
                logger.debug("[MCP client/%s] list_tools error: %s", conn.name, exc)
        return result

    def get_ollash_definitions(self) -> list[dict]:
        """Return all external tools as Ollama-format function definitions."""
        defs: list[dict] = []
        for _server, tools in self.all_tools().items():
            for t in tools:
                defs.append(mcp_tool_to_ollash(t))
        return defs

    def _build_tool_index(self) -> None:
        """Map tool_name → server_name for fast routing."""
        self._tool_index = {}
        for srv_name, tools in self.all_tools().items():
            for t in tools:
                self._tool_index[t["name"]] = srv_name

    def call_tool_if_known(self, tool_name: str, arguments: dict[str, Any]) -> dict | None:
        """Call tool on the first external server that exposes it. Returns None if not found."""
        if not self._tool_index:
            self._build_tool_index()

        server_name = self._tool_index.get(tool_name)
        if server_name is None:
            return None

        with self._lock:
            conn = self._connections.get(server_name)
        if conn is None:
            return None

        return conn.call_tool(tool_name, arguments)

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict | None:
        """Public: route tool call to the right external server."""
        return self.call_tool_if_known(tool_name, arguments)

    def tools_for_server(self, server_name: str) -> list[dict]:
        """Return MCP-format tools for one server."""
        with self._lock:
            conn = self._connections.get(server_name)
        if conn is None:
            return []
        return conn.list_tools()


# Module-level singleton
mcp_client_manager = MCPClientManager()
