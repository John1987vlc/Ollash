"""
CoWorkAgent — folder-aware document Q&A and creation agent.

Mirrors SimpleChatAgent: same tool loop, same Ollama HTTP client, same event bridge API.
The user assigns a local workspace folder; the agent indexes all text documents in it
and can answer questions about them, search across them, and create new documents.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from backend.services.chat_event_bridge import ChatEventBridge

logger = logging.getLogger("ollash")

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "llm_models.json"
_MAX_TOOL_ITERATIONS = 5

# ---------------------------------------------------------------------------
# Tool definitions (Ollama function-calling format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_workspace_files",
            "description": "Lists all indexed files in the assigned workspace folder with their sizes.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_workspace_file",
            "description": "Reads the content of a specific file from the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path (e.g. 'readme.md') or filename of the file to read.",
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum number of lines to return (default 200).",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_workspace",
            "description": "Searches for a text query across all files in the workspace. Returns matching lines with file and line number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text to search for (case-insensitive).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_document",
            "description": "Creates a new document file in the workspace with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename for the new document (e.g. 'summary.md', 'report.txt').",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full content to write to the file.",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Supported document extensions for indexing
# ---------------------------------------------------------------------------

_DOC_EXTENSIONS = frozenset(
    {
        ".md",
        ".txt",
        ".rst",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".py",
        ".js",
        ".ts",
        ".html",
        ".css",
        ".sh",
        ".env.example",
    }
)

_EXCLUDE_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".cache",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ollash",
    }
)


# ---------------------------------------------------------------------------
# Config loader (mirrors SimpleChatAgent._load_config)
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {"ollama_url": "http://localhost:11434", "default_model": "qwen3.5:4b"}


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class CoWorkAgent:
    """Stateful document-Q&A agent scoped to a local workspace folder.

    On construction the agent walks *workspace_path* and indexes all
    text-readable documents into an in-memory dict (relative_path → content).
    The LLM can then read, search, and create files via tool calls.
    """

    MAX_HISTORY = 40

    def __init__(
        self,
        workspace_path: Path,
        event_bridge: Optional["ChatEventBridge"] = None,
        model: Optional[str] = None,
    ) -> None:
        cfg = _load_config()
        ollama_url = cfg.get("ollama_url", "http://localhost:11434").rstrip("/")
        self._model = model or cfg.get("default_model", "ornith:9b")
        self._timeout = cfg.get("default_timeout", 120)
        import ollama
        self._client = ollama.Client(host=ollama_url, timeout=self._timeout)


        self.workspace_path = Path(workspace_path)
        self.event_bridge = event_bridge
        self._history: List[dict] = []
        self._file_index: Dict[str, str] = {}  # relative_path -> content

        self._index_workspace()

    # ------------------------------------------------------------------
    # Workspace indexing
    # ------------------------------------------------------------------

    def _index_workspace(self) -> None:
        """Walk workspace_path and load all text-readable documents into memory."""
        if not self.workspace_path.exists():
            return

        for dirpath, dirnames, filenames in os.walk(self.workspace_path):
            dirnames[:] = sorted(d for d in dirnames if d not in _EXCLUDE_DIRS)
            for fname in filenames:
                if Path(fname).suffix.lower() not in _DOC_EXTENSIONS:
                    continue
                full = Path(dirpath) / fname
                try:
                    rel = str(full.relative_to(self.workspace_path))
                    content = full.read_text(encoding="utf-8", errors="replace")
                    self._file_index[rel] = content
                except Exception:
                    pass

    def reindex(self) -> int:
        """Re-scan the workspace. Returns new file count."""
        self._file_index.clear()
        self._index_workspace()
        return len(self._file_index)

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        file_list = "\n".join(f"  - {p}" for p in sorted(self._file_index)[:50])
        if len(self._file_index) > 50:
            file_list += f"\n  ... and {len(self._file_index) - 50} more files"

        return (
            "You are CoWork, an AI assistant specialized in analyzing and creating documents.\n"
            f"Workspace folder: {self.workspace_path}\n"
            f"Indexed files ({len(self._file_index)} total):\n{file_list}\n\n"
            "Available tools:\n"
            "  - list_workspace_files: show all indexed files\n"
            "  - read_workspace_file: read a specific file's content\n"
            "  - search_workspace: search text across all files\n"
            "  - create_document: write a new document to the workspace\n\n"
            "Guidelines:\n"
            "  - Always read relevant files before answering questions about them.\n"
            "  - For document creation tasks, generate high-quality, well-structured content.\n"
            "  - When creating documents, confirm what was written and where it was saved.\n"
            "  - Be concise but thorough in document analysis."
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(self, message: str) -> dict:
        """Process a user message. Returns {"text": str, "metrics": dict}."""
        start = time.time()
        total_tokens = 0

        self._history.append({"role": "user", "content": message})
        self._trim_history()

        if self.event_bridge:
            self.event_bridge.push_event("thinking", {"message": "Analyzing workspace..."})

        messages = [{"role": "system", "content": self._build_system_prompt()}] + self._history
        response_text = ""

        try:
            for _ in range(_MAX_TOOL_ITERATIONS):
                data, usage = self._call_ollama_raw(messages)
                total_tokens += usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

                msg = data.get("message", {})
                content = msg.get("content", "").strip()
                tool_calls = msg.get("tool_calls") or []

                if not tool_calls:
                    response_text = content
                    break

                # Execute tool calls
                messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    raw_args = fn.get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args)
                        except Exception:
                            args = {}
                    else:
                        args = raw_args if isinstance(raw_args, dict) else {}

                    if self.event_bridge:
                        self.event_bridge.push_event("thinking", {"message": f"Using tool: {tool_name}..."})

                    logger.info(f"[CoWorkAgent] Tool call: {tool_name}({args})")
                    result = self._dispatch_tool(tool_name, args)
                    logger.info(f"[CoWorkAgent] Tool result ({tool_name}): {result[:120]}")

                    messages.append({"role": "tool", "content": result})
            else:
                response_text = content

        except Exception as exc:
            logger.error(f"[CoWorkAgent] Error: {exc}")
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
    # Tool dispatch
    # ------------------------------------------------------------------

    def _dispatch_tool(self, name: str, args: dict) -> str:
        if name == "list_workspace_files":
            return self._tool_list_workspace_files()
        if name == "read_workspace_file":
            return self._tool_read_workspace_file(args.get("path", ""), args.get("max_lines", 200))
        if name == "search_workspace":
            return self._tool_search_workspace(args.get("query", ""))
        if name == "create_document":
            return self._tool_create_document(args.get("filename", ""), args.get("content", ""))
        return json.dumps({"error": f"Unknown tool: {name}"})

    def _tool_list_workspace_files(self) -> str:
        files = [
            {"path": p, "size_chars": len(c), "lines": c.count("\n") + 1} for p, c in sorted(self._file_index.items())
        ]
        return json.dumps(
            {"workspace": str(self.workspace_path), "file_count": len(files), "files": files},
            ensure_ascii=False,
        )

    def _tool_read_workspace_file(self, path: str, max_lines: int = 200) -> str:
        # Try exact relative path
        content = self._file_index.get(path)

        # Try matching by filename suffix or name
        if content is None:
            for rel, c in self._file_index.items():
                if rel.endswith(path) or Path(rel).name == Path(path).name:
                    content = c
                    path = rel
                    break

        # Try absolute-ish path relative to workspace
        if content is None:
            candidate = self.workspace_path / path
            try:
                content = candidate.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return json.dumps({"error": f"File not found: {path}"})

        lines = content.splitlines()
        truncated = len(lines) > max_lines
        return json.dumps(
            {
                "path": path,
                "content": "\n".join(lines[:max_lines]),
                "lines_shown": min(len(lines), max_lines),
                "total_lines": len(lines),
                "truncated": truncated,
            },
            ensure_ascii=False,
        )

    def _tool_search_workspace(self, query: str) -> str:
        if not query:
            return json.dumps({"error": "query is required"})

        ql = query.lower()
        matches = []

        for path, content in self._file_index.items():
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if ql in line.lower():
                    matches.append({"file": path, "line": i + 1, "text": line.strip()[:200]})
                    if len(matches) >= 30:
                        break
            if len(matches) >= 30:
                break

        return json.dumps(
            {"query": query, "match_count": len(matches), "matches": matches},
            ensure_ascii=False,
        )

    def _tool_create_document(self, filename: str, content: str) -> str:
        if not filename:
            return json.dumps({"error": "filename is required"})
        if not content:
            return json.dumps({"error": "content is required"})

        # Strip any directory traversal — only allow plain filenames
        safe_name = Path(filename).name
        dest = self.workspace_path / safe_name

        try:
            dest.write_text(content, encoding="utf-8")
            # Update in-memory index
            self._file_index[safe_name] = content
            return json.dumps(
                {"status": "created", "path": str(dest), "filename": safe_name, "size_chars": len(content)},
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_ollama_raw(self, messages: list) -> tuple:
        """POST to Ollama /api/chat and return (response_dict, usage_dict)."""
        logger.info(f"[CoWorkAgent] Calling {self._model} ...")
        
        opts = {"temperature": 0.4, "num_ctx": 8192, "num_predict": 2048}
        
        response = self._client.chat(
            model=self._model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            options=opts
        )

        if hasattr(response, "model_dump"):
            data = response.model_dump()
        elif hasattr(response, "dict"):
            data = response.dict()
        else:
            data = dict(response)

        prompt_eval = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)
        logger.info(f"[CoWorkAgent] Done. Tokens: {prompt_eval} prompt, {eval_count} completion")

        return data, {"prompt_tokens": prompt_eval, "completion_tokens": eval_count}

    def _trim_history(self) -> None:
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY :]
