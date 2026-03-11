"""
SimpleChatAgent — lightweight Q&A chat agent with read-only tools.

One LLM call per turn normally; runs a short tool loop when the model
requests a tool. Available tools are intentionally read-only / query-only:
no file writes, no shell execution.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import socket
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import requests

if TYPE_CHECKING:
    from backend.services.chat_event_bridge import ChatEventBridge

logger = logging.getLogger("ollash")

SYSTEM_PROMPT = """\
You are Ollash, a helpful AI assistant. You answer questions clearly and concisely.
You can help with code explanations, debugging, technical discussions, and general questions.
You have access to tools — use them when the user needs real data:
- get_system_info / get_public_ip: machine and network information
- web_search: search the internet for up-to-date information
- ping_host: test connectivity to a host
- search_files: find files on the local filesystem by name or pattern
- read_file / list_directory: read file content or list a folder

When search_files returns results, present each one with its full path and a
clickable folder link formatted as a markdown link: [Open folder](file:///path/to/folder).
On Windows paths look like file:///C:/Users/... — always include the triple slash.

When providing code, use proper markdown code blocks with the language identifier.
Keep responses practical and focused. You do NOT generate full software projects —
that is handled separately by the project generation pipeline.
"""

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "llm_models.json"

# Maximum tool-call iterations per turn to prevent runaway loops
_MAX_TOOL_ITERATIONS = 5


# ---------------------------------------------------------------------------
# Tool definitions (Ollama function-calling format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": (
                "Returns local machine information: hostname, local IP address, "
                "operating system, CPU count, and total RAM."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_public_ip",
            "description": "Returns the public (external) IP address of this machine.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Searches the web using DuckDuckGo and returns a short summary "
                "plus a list of relevant results with titles and URLs."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The search query."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ping_host",
            "description": "Pings a hostname or IP address and reports latency and packet loss.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Hostname or IP to ping."},
                    "count": {"type": "integer", "description": "Number of packets (default 4)."},
                },
                "required": ["host"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the content of a file and returns it as text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative path to the file."},
                    "max_lines": {"type": "integer", "description": "Maximum lines to return (default 100)."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Searches for files on the local filesystem by name or glob pattern "
                "(e.g. '*.pdf', 'invoice*', 'report.xlsx'). Returns matching paths "
                "and a file:// folder link for each result so the user can open "
                "the containing folder directly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "File name or glob pattern to search for (e.g. '*.pdf', 'config.json').",
                    },
                    "root": {
                        "type": "string",
                        "description": (
                            "Root directory to start the search from. Defaults to the user's home directory."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 20).",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations (all read-only)
# ---------------------------------------------------------------------------


def _tool_get_system_info() -> str:
    try:
        import psutil

        ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
        cpu_count = psutil.cpu_count(logical=True)
    except ImportError:
        ram_gb = "unknown"
        cpu_count = os.cpu_count() or "unknown"

    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "unavailable"

    return json.dumps(
        {
            "hostname": socket.gethostname(),
            "local_ip": local_ip,
            "os": f"{platform.system()} {platform.release()}",
            "cpu_cores": cpu_count,
            "ram_gb": ram_gb,
        },
        ensure_ascii=False,
    )


def _tool_get_public_ip() -> str:
    for endpoint in [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]:
        try:
            resp = requests.get(endpoint, timeout=5)
            if resp.ok:
                return json.dumps({"public_ip": resp.text.strip()})
        except Exception:
            continue
    return json.dumps({"error": "Could not determine public IP."})


def _tool_web_search(query: str) -> str:
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=8,
        )
        data = resp.json()
    except Exception as exc:
        return json.dumps({"error": f"Search failed: {exc}"})

    results = []
    abstract = data.get("Abstract", "").strip()
    if abstract:
        results.append({"title": data.get("Heading", query), "summary": abstract, "url": data.get("AbstractURL", "")})

    for topic in data.get("RelatedTopics", [])[:6]:
        text = topic.get("Text", "").strip()
        url = topic.get("FirstURL", "")
        if text:
            results.append({"title": text[:80], "url": url})

    if not results:
        return json.dumps({"message": f"No results found for '{query}'."})
    return json.dumps({"query": query, "results": results}, ensure_ascii=False)


def _tool_ping_host(host: str, count: int = 4) -> str:
    is_windows = platform.system().lower() == "windows"
    flag = "-n" if is_windows else "-c"
    try:
        result = subprocess.run(
            ["ping", flag, str(count), host],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout or result.stderr
        return json.dumps({"host": host, "output": output.strip()[:800]})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Ping to {host} timed out."})
    except FileNotFoundError:
        return json.dumps({"error": "ping command not found."})


def _tool_read_file(path: str, max_lines: int = 100) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return json.dumps({"error": f"File not found: {path}"})
        if not p.is_file():
            return json.dumps({"error": f"Not a file: {path}"})
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        truncated = len(lines) > max_lines
        content = "\n".join(lines[:max_lines])
        result = {"path": str(p), "content": content, "lines_shown": min(len(lines), max_lines)}
        if truncated:
            result["truncated"] = True
            result["total_lines"] = len(lines)
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _tool_list_directory(path: str) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return json.dumps({"error": f"Path not found: {path}"})
        if not p.is_dir():
            return json.dumps({"error": f"Not a directory: {path}"})
        entries = []
        for item in sorted(p.iterdir()):
            entries.append({"name": item.name, "type": "dir" if item.is_dir() else "file"})
        return json.dumps({"path": str(p), "entries": entries[:100]}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _path_to_file_url(p: Path) -> str:
    """Convert a Path to a file:// URL usable as a clickable link."""
    # pathlib.Path.as_uri() handles Windows drive letters correctly (file:///C:/...)
    return p.as_uri()


def _tool_search_files(pattern: str, root: Optional[str] = None, max_results: int = 20) -> str:
    try:
        import fnmatch

        start_dir = Path(root).expanduser() if root else Path.home()
        if not start_dir.exists():
            return json.dumps({"error": f"Root directory not found: {start_dir}"})

        matches = []
        for dirpath, dirnames, filenames in os.walk(start_dir):
            # Skip hidden and system directories to keep the search fast
            dirnames[:] = [
                d for d in dirnames if not d.startswith(".") and d not in {"$Recycle.Bin", "System Volume Information"}
            ]
            for fname in filenames:
                if fnmatch.fnmatch(fname.lower(), pattern.lower()):
                    full = Path(dirpath) / fname
                    folder = Path(dirpath)
                    matches.append(
                        {
                            "name": fname,
                            "path": str(full),
                            "folder": str(folder),
                            "folder_link": _path_to_file_url(folder),
                        }
                    )
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break

        if not matches:
            return json.dumps(
                {
                    "message": f"No files matching '{pattern}' found under {start_dir}.",
                    "searched_root": str(start_dir),
                }
            )

        return json.dumps(
            {
                "pattern": pattern,
                "searched_root": str(start_dir),
                "total_found": len(matches),
                "results": matches,
            },
            ensure_ascii=False,
        )

    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _dispatch_tool(name: str, args: dict) -> str:
    """Route a tool call to its implementation."""
    if name == "get_system_info":
        return _tool_get_system_info()
    if name == "get_public_ip":
        return _tool_get_public_ip()
    if name == "web_search":
        return _tool_web_search(args.get("query", ""))
    if name == "ping_host":
        return _tool_ping_host(args.get("host", ""), args.get("count", 4))
    if name == "read_file":
        return _tool_read_file(args.get("path", ""), args.get("max_lines", 100))
    if name == "list_directory":
        return _tool_list_directory(args.get("path", ""))
    if name == "search_files":
        return _tool_search_files(args.get("pattern", "*"), args.get("root"), args.get("max_results", 20))
    return json.dumps({"error": f"Unknown tool: {name}"})


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"ollama_url": "http://localhost:11434", "default_model": "qwen3.5:4b"}


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class SimpleChatAgent:
    """Stateful conversational agent with read-only query tools."""

    MAX_HISTORY = 40

    def __init__(
        self,
        event_bridge: Optional["ChatEventBridge"] = None,
        model: Optional[str] = None,
    ):
        cfg = _load_config()
        self._url = cfg.get("ollama_url", "http://localhost:11434").rstrip("/") + "/api/chat"
        self._model = model or cfg.get("default_model", "qwen3.5:4b")
        self._timeout = cfg.get("default_timeout", 120)
        self.event_bridge = event_bridge
        self._history: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(self, message: str) -> dict:
        """Process a user message and return {"text": str, "metrics": dict}."""
        start = time.time()
        total_tokens = 0

        self._history.append({"role": "user", "content": message})
        self._trim_history()

        if self.event_bridge:
            self.event_bridge.push_event("thinking", {"message": "Thinking..."})

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self._history
        response_text = ""

        try:
            for iteration in range(_MAX_TOOL_ITERATIONS):
                data, usage = self._call_ollama_raw(messages)
                total_tokens += usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

                msg = data.get("message", {})
                content = msg.get("content", "").strip()
                tool_calls = msg.get("tool_calls") or []

                if not tool_calls:
                    # Final answer — no more tool calls
                    response_text = content
                    break

                # There are tool calls — execute them and continue
                messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    raw_args = fn.get("arguments", {})
                    args = raw_args if isinstance(raw_args, dict) else {}

                    if self.event_bridge:
                        self.event_bridge.push_event("thinking", {"message": f"Using tool: {tool_name}..."})

                    logger.info(f"[SimpleChatAgent] Tool call: {tool_name}({args})")
                    result = _dispatch_tool(tool_name, args)
                    logger.info(f"[SimpleChatAgent] Tool result ({tool_name}): {result[:120]}")

                    messages.append(
                        {
                            "role": "tool",
                            "content": result,
                        }
                    )
            else:
                response_text = content  # use last content if max iterations reached

        except Exception as exc:
            logger.error(f"SimpleChatAgent error: {exc}")
            response_text = "Sorry, I couldn't reach the language model. Please check that Ollama is running."

        self._history.append({"role": "assistant", "content": response_text})

        elapsed = round(time.time() - start, 2)
        metrics = {"duration": elapsed, "tokens": total_tokens}

        if self.event_bridge:
            self.event_bridge.push_event("final_answer", {"content": response_text, "metrics": metrics})

        return {"text": response_text, "metrics": metrics}

    def reset(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_ollama_raw(self, messages: list[dict]) -> tuple[dict, dict]:
        """Call Ollama and return the raw response dict + usage dict."""
        payload = {
            "model": self._model,
            "messages": messages,
            "tools": TOOL_DEFINITIONS,
            "stream": False,
            "options": {
                "temperature": 0.4,
                "num_ctx": 8192,
                "num_predict": 2048,
            },
        }

        logger.info(f"[SimpleChatAgent] Calling {self._model} ...")
        resp = requests.post(self._url, json=payload, timeout=self._timeout)

        if not resp.ok:
            logger.error(f"[SimpleChatAgent] Ollama returned {resp.status_code}: {resp.text[:200]}")
            raise RuntimeError(f"Ollama error {resp.status_code}")

        data = resp.json()
        prompt_eval = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)
        logger.info(f"[SimpleChatAgent] Done. Tokens: {prompt_eval} prompt, {eval_count} completion")

        return data, {"prompt_tokens": prompt_eval, "completion_tokens": eval_count}

    def _trim_history(self) -> None:
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY :]
