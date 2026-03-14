"""Ollash MCP (Model Context Protocol) package.

Provides:
  - MCP Server (stdio) — exposes Ollash tools to external MCP clients
    (Claude Code, Cline, Continue.dev, etc.)
  - MCP Client — connects to external MCP servers and makes their tools
    available inside Ollash agents

Run the server:
    python -m backend.mcp

See also:
    backend/mcp/server.py  — server implementation
    backend/mcp/client.py  — client implementation
    backend/mcp/protocol.py — JSON-RPC 2.0 message helpers
"""
