"""MCP Server — exposes Ollash tools to external MCP clients via stdio.

Protocol: JSON-RPC 2.0 over stdin/stdout (one JSON object per line).

Supported methods
-----------------
  initialize          → server capabilities + tool list
  initialized         → (notification, no response)
  ping                → {}
  tools/list          → {tools: [...]}
  tools/call          → {content: [{type: "text", text: "..."}], isError: bool}
  notifications/cancelled → (ignored)

Run
---
    python -m backend.mcp
    python -m backend.mcp --port 3000    # HTTP+SSE mode (future)

Claude Code / Cline config (.mcp.json):
    {
      "mcpServers": {
        "ollash": {
          "command": "python",
          "args": ["-m", "backend.mcp"],
          "cwd": "/path/to/ollash"
        }
      }
    }
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any

from backend.mcp.protocol import (
    ERR_INTERNAL,
    ERR_METHOD_NOT_FOUND,
    ERR_TOOL_NOT_FOUND,
    decode,
    encode,
    error_response,
    notification,
    ollash_tool_to_mcp,
    response,
    server_info,
    tool_result,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool execution — lightweight, no full agent context
# ---------------------------------------------------------------------------


class _ToolExecutor:
    """Minimal tool executor for MCP server context.

    Executes Ollash tools that don't require a full PhaseContext.
    Complex tools (file generation, RAG) fall back to a description message.
    """

    _SAFE_TOOLSETS = frozenset(
        {
            "file_system_tools",
            "command_line_tools",
            "git_operations_tools",
            "system_tools",
            "network_tools",
        }
    )

    def __init__(self) -> None:
        self._root = Path(os.environ.get("OLLASH_MCP_ROOT", Path.cwd()))
        self._tools_cache: dict[str, dict] | None = None

    def _get_tool_info(self, name: str) -> dict | None:
        if self._tools_cache is None:
            from backend.utils.core.tools.tool_decorator import get_discovered_tools

            self._tools_cache = get_discovered_tools()
        return self._tools_cache.get(name)

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool and return string result."""
        info = self._get_tool_info(tool_name)
        if info is None:
            raise KeyError(f"Tool '{tool_name}' not found")

        toolset_id = info.get("toolset_id", "")
        if toolset_id not in self._SAFE_TOOLSETS:
            return (
                f"[MCP] Tool '{tool_name}' (toolset: {toolset_id}) requires a full "
                "agent session. Start a chat session via the Ollash web UI or CLI "
                "to use this tool with full context."
            )

        try:
            return self._run_safe_tool(tool_name, toolset_id, arguments)
        except Exception as exc:
            raise RuntimeError(f"Tool execution failed: {exc}") from exc

    def _run_safe_tool(self, name: str, toolset_id: str, args: dict) -> str:
        """Route to the appropriate toolset executor."""
        if toolset_id == "file_system_tools":
            return self._exec_file(name, args)
        if toolset_id == "command_line_tools":
            return self._exec_command(name, args)
        if toolset_id == "git_operations_tools":
            return self._exec_git(name, args)
        if toolset_id == "system_tools":
            return self._exec_system(name, args)
        return f"[MCP] Tool '{name}' executed (no output captured for this toolset)"

    def _exec_file(self, name: str, args: dict) -> str:
        from backend.utils.core.io.file_manager import FileManager

        fm = FileManager(logger=None, project_root=self._root)  # type: ignore[arg-type]
        if name == "read_file":
            path = args.get("file_path", args.get("path", ""))
            return fm.read_file(path) or "(empty file)"
        if name == "write_file":
            path = args["file_path"]
            content = args["content"]
            fm.write_file(path, content)
            return f"Written: {path}"
        if name == "list_files":
            path = args.get("directory", args.get("path", "."))
            items = [str(p.relative_to(self._root)) for p in Path(self._root / path).iterdir()]
            return "\n".join(items)
        return f"[MCP] file_system_tools/{name}: no direct handler"

    def _exec_command(self, name: str, args: dict) -> str:
        from backend.utils.core.command_executor import CommandExecutor
        from backend.utils.core.system.confirmation_manager import ConfirmationManager

        cm = ConfirmationManager(auto_confirm=True)
        ce = CommandExecutor(confirmation_manager=cm, sandbox_level="limited")
        if name in ("run_command", "execute_command"):
            cmd = args.get("command", args.get("cmd", ""))
            result = ce.execute(cmd, cwd=str(self._root))
            return result.get("stdout", "") + result.get("stderr", "")
        return f"[MCP] command_line_tools/{name}: no direct handler"

    def _exec_git(self, name: str, args: dict) -> str:
        import subprocess

        cwd = str(self._root)
        git_map = {
            "git_status": ["git", "status", "--short"],
            "git_log": ["git", "log", "--oneline", "-10"],
            "git_diff": ["git", "diff"],
        }
        cmd = git_map.get(name)
        if cmd:
            r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=15)
            return r.stdout + r.stderr
        return f"[MCP] git_operations_tools/{name}: no direct handler"

    def _exec_system(self, name: str, args: dict) -> str:
        if name == "get_system_info":
            import platform
            import psutil

            return json.dumps(
                {
                    "platform": platform.platform(),
                    "cpu_count": psutil.cpu_count(),
                    "memory_total_gb": round(psutil.virtual_memory().total / 1e9, 1),
                    "disk_free_gb": round(psutil.disk_usage("/").free / 1e9, 1),
                }
            )
        return f"[MCP] system_tools/{name}: no direct handler"


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------


class MCPServer:
    """Stateful MCP server instance.  Handles one stdio session."""

    VERSION = "1.0.0"
    NAME = "ollash"

    def __init__(self, stdin: io.RawIOBase | None = None, stdout: io.RawIOBase | None = None) -> None:
        self._in = stdin or sys.stdin.buffer
        self._out = stdout or sys.stdout.buffer
        self._executor = _ToolExecutor()
        self._initialized = False
        self._tools_cache: list[dict] | None = None

    # ------------------------------------------------------------------
    # Tool catalog
    # ------------------------------------------------------------------

    def _get_mcp_tools(self) -> list[dict]:
        if self._tools_cache is not None:
            return self._tools_cache

        # Discover all Ollash tools
        try:
            from backend.utils.core.tools.tool_decorator import get_discovered_definitions
            from backend.utils.core.tools.tool_registry import discover_tools

            discover_tools()
            defs = get_discovered_definitions()
            self._tools_cache = [ollash_tool_to_mcp(d) for d in defs]
        except Exception as exc:
            logger.warning("Could not load Ollash tools: %s", exc)
            self._tools_cache = []

        # Merge tools from connected external MCP servers
        try:
            from backend.mcp.client import mcp_client_manager

            for srv_tools in mcp_client_manager.all_tools().values():
                self._tools_cache.extend(srv_tools)
        except Exception:
            pass

        return self._tools_cache

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    def handle(self, msg: dict) -> dict | None:
        """Process one JSON-RPC message.  Returns response dict or None for notifications."""
        method = msg.get("method", "")
        req_id = msg.get("id")
        params = msg.get("params") or {}

        # Notifications have no id → no response
        if req_id is None:
            return None

        try:
            if method == "initialize":
                return self._handle_initialize(params, req_id)
            if method == "ping":
                return response({}, req_id)
            if method == "tools/list":
                return self._handle_tools_list(params, req_id)
            if method == "tools/call":
                return self._handle_tools_call(params, req_id)
            return error_response(ERR_METHOD_NOT_FOUND, f"Method not found: {method}", req_id)
        except Exception as exc:
            logger.error("Unhandled error in %s: %s", method, exc)
            return error_response(ERR_INTERNAL, str(exc), req_id)

    def _handle_initialize(self, params: dict, req_id: Any) -> dict:
        self._initialized = True
        return response(server_info(self.NAME, self.VERSION), req_id)

    def _handle_tools_list(self, params: dict, req_id: Any) -> dict:
        tools = self._get_mcp_tools()
        # Simple pagination: return all (no cursor logic needed for typical sizes)
        return response({"tools": tools}, req_id)

    def _handle_tools_call(self, params: dict, req_id: Any) -> dict:
        name = params.get("name", "")
        arguments = params.get("arguments") or {}

        # Check tool exists
        known = {t["name"] for t in self._get_mcp_tools()}
        if name not in known:
            return error_response(ERR_TOOL_NOT_FOUND, f"Tool '{name}' not found", req_id)

        # Try external MCP servers first
        try:
            from backend.mcp.client import mcp_client_manager

            ext_result = mcp_client_manager.call_tool_if_known(name, arguments)
            if ext_result is not None:
                return response(ext_result, req_id)
        except Exception:
            pass

        # Execute Ollash tool
        try:
            output = self._executor.execute(name, arguments)
            return response(tool_result(str(output)), req_id)
        except KeyError as exc:
            return error_response(ERR_TOOL_NOT_FOUND, str(exc), req_id)
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Tool execution error: %s\n%s", exc, tb)
            return response(tool_result(f"Error: {exc}\n{tb}", is_error=True), req_id)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Read JSON-RPC messages from stdin, write responses to stdout."""
        # Send initialized notification after server starts
        self._send(notification("notifications/initialized"))

        for raw_line in self._in:
            raw_line = raw_line.strip() if isinstance(raw_line, bytes) else raw_line.strip().encode()
            if not raw_line:
                continue
            try:
                msg = decode(raw_line)
            except json.JSONDecodeError as exc:
                self._send_raw(error_response(-32700, f"Parse error: {exc}", None))
                continue

            resp = self.handle(msg)
            if resp is not None:
                self._send(resp)

    def _send(self, msg: dict) -> None:
        self._out.write(encode(msg))
        self._out.flush()

    def _send_raw(self, msg: dict) -> None:
        self._send(msg)


def main() -> None:
    """Entry point: start the MCP server in stdio mode."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s %(message)s",
        stream=sys.stderr,  # logs go to stderr, not stdout (stdout is MCP channel)
    )
    server = MCPServer()
    server.run()
