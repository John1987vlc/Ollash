"""Unit tests for CoWorkAgent."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.cowork_agent import CoWorkAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(tmp_path: Path, files: dict | None = None) -> CoWorkAgent:
    """Construct a CoWorkAgent with an optional set of pre-populated files."""
    if files:
        for name, content in files.items():
            (tmp_path / name).write_text(content, encoding="utf-8")
    return CoWorkAgent(workspace_path=tmp_path, event_bridge=MagicMock())


def _fake_ollama_response(content: str) -> tuple:
    """Return a minimal Ollama response tuple (response_dict, usage_dict)."""
    return (
        {"message": {"content": content, "tool_calls": []}},
        {"prompt_tokens": 10, "completion_tokens": 5},
    )


def _tool_call_response(tool_name: str, arguments: dict) -> tuple:
    """Return a response that triggers a single tool call."""
    return (
        {
            "message": {
                "content": "",
                "tool_calls": [{"function": {"name": tool_name, "arguments": arguments}}],
            }
        },
        {"prompt_tokens": 5, "completion_tokens": 2},
    )


# ---------------------------------------------------------------------------
# TestCoWorkAgentInit
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoWorkAgentInit:
    def test_indexes_md_and_txt_files(self, tmp_path: Path) -> None:
        (tmp_path / "readme.md").write_text("# Hello", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("Some notes", encoding="utf-8")
        agent = CoWorkAgent(workspace_path=tmp_path)
        assert "readme.md" in agent._file_index
        assert "notes.txt" in agent._file_index

    def test_skips_binary_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")
        (tmp_path / "archive.zip").write_bytes(b"PK")
        agent = CoWorkAgent(workspace_path=tmp_path)
        assert "image.png" not in agent._file_index
        assert "archive.zip" not in agent._file_index

    def test_nonexistent_workspace_does_not_raise(self, tmp_path: Path) -> None:
        agent = CoWorkAgent(workspace_path=tmp_path / "does_not_exist")
        assert agent._file_index == {}

    def test_history_starts_empty(self, tmp_path: Path) -> None:
        agent = CoWorkAgent(workspace_path=tmp_path)
        assert agent._history == []

    def test_workspace_path_stored(self, tmp_path: Path) -> None:
        agent = CoWorkAgent(workspace_path=tmp_path)
        assert agent.workspace_path == tmp_path

    def test_skips_excluded_directories(self, tmp_path: Path) -> None:
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.json").write_text("{}", encoding="utf-8")
        agent = CoWorkAgent(workspace_path=tmp_path)
        assert not any("node_modules" in p for p in agent._file_index)


# ---------------------------------------------------------------------------
# TestCoWorkAgentSystemPrompt
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoWorkAgentSystemPrompt:
    def test_includes_workspace_path(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        prompt = agent._build_system_prompt()
        assert str(tmp_path) in prompt

    def test_includes_file_count(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("content", encoding="utf-8")
        (tmp_path / "b.txt").write_text("more", encoding="utf-8")
        agent = CoWorkAgent(workspace_path=tmp_path)
        prompt = agent._build_system_prompt()
        assert "2" in prompt

    def test_lists_file_names(self, tmp_path: Path) -> None:
        (tmp_path / "report.md").write_text("report content", encoding="utf-8")
        agent = CoWorkAgent(workspace_path=tmp_path)
        prompt = agent._build_system_prompt()
        assert "report.md" in prompt

    def test_empty_workspace_prompt(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        prompt = agent._build_system_prompt()
        assert "0" in prompt  # 0 files


# ---------------------------------------------------------------------------
# TestCoWorkAgentReindex
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoWorkAgentReindex:
    def test_reindex_picks_up_new_file(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        assert len(agent._file_index) == 0
        (tmp_path / "new.md").write_text("new content", encoding="utf-8")
        count = agent.reindex()
        assert count == 1
        assert "new.md" in agent._file_index

    def test_reindex_returns_file_count(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")
        agent = CoWorkAgent(workspace_path=tmp_path)
        result = agent.reindex()
        assert result == 2


# ---------------------------------------------------------------------------
# TestCoWorkAgentToolDispatch
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoWorkAgentToolDispatch:
    def test_list_workspace_files_empty(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        result = json.loads(agent._dispatch_tool("list_workspace_files", {}))
        assert result["file_count"] == 0
        assert result["files"] == []

    def test_list_workspace_files_with_content(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path, {"doc.md": "hello world"})
        result = json.loads(agent._dispatch_tool("list_workspace_files", {}))
        assert result["file_count"] == 1
        assert result["files"][0]["path"] == "doc.md"
        assert result["files"][0]["size_chars"] == len("hello world")

    def test_read_workspace_file_found_by_name(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path, {"hello.md": "# Hello World"})
        result = json.loads(agent._dispatch_tool("read_workspace_file", {"path": "hello.md"}))
        assert "Hello World" in result["content"]
        assert result["truncated"] is False

    def test_read_workspace_file_not_found(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        result = json.loads(agent._dispatch_tool("read_workspace_file", {"path": "missing.md"}))
        assert "error" in result

    def test_read_workspace_file_matches_by_filename(self, tmp_path: Path) -> None:
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "notes.md").write_text("sub notes", encoding="utf-8")
        agent = CoWorkAgent(workspace_path=tmp_path)
        result = json.loads(agent._dispatch_tool("read_workspace_file", {"path": "notes.md"}))
        assert "sub notes" in result["content"]

    def test_read_workspace_file_respects_max_lines(self, tmp_path: Path) -> None:
        content = "\n".join(f"line {i}" for i in range(300))
        agent = _make_agent(tmp_path, {"big.txt": content})
        result = json.loads(agent._dispatch_tool("read_workspace_file", {"path": "big.txt", "max_lines": 10}))
        assert result["lines_shown"] == 10
        assert result["truncated"] is True

    def test_search_workspace_finds_match(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path, {"doc.md": "The quick brown fox\nA lazy dog"})
        result = json.loads(agent._dispatch_tool("search_workspace", {"query": "quick"}))
        assert result["match_count"] >= 1
        assert any("quick" in m["text"].lower() for m in result["matches"])

    def test_search_workspace_case_insensitive(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path, {"doc.md": "IMPORTANT NOTE"})
        result = json.loads(agent._dispatch_tool("search_workspace", {"query": "important"}))
        assert result["match_count"] >= 1

    def test_search_workspace_no_matches(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path, {"doc.md": "Hello world"})
        result = json.loads(agent._dispatch_tool("search_workspace", {"query": "xyzzy_not_found"}))
        assert result["match_count"] == 0

    def test_search_workspace_empty_query_returns_error(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        result = json.loads(agent._dispatch_tool("search_workspace", {"query": ""}))
        assert "error" in result

    def test_create_document_writes_file(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        result = json.loads(
            agent._dispatch_tool("create_document", {"filename": "output.md", "content": "# New Doc\nContent here."})
        )
        assert result["status"] == "created"
        assert (tmp_path / "output.md").exists()
        assert (tmp_path / "output.md").read_text(encoding="utf-8") == "# New Doc\nContent here."

    def test_create_document_updates_index(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        agent._dispatch_tool("create_document", {"filename": "new.md", "content": "indexed"})
        assert "new.md" in agent._file_index
        assert agent._file_index["new.md"] == "indexed"

    def test_create_document_prevents_directory_traversal(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        agent._dispatch_tool("create_document", {"filename": "../evil.txt", "content": "bad"})
        # Should NOT write outside workspace
        assert not (tmp_path.parent / "evil.txt").exists()
        # Should write safe_name inside workspace
        assert (tmp_path / "evil.txt").exists()

    def test_create_document_missing_filename(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        result = json.loads(agent._dispatch_tool("create_document", {"filename": "", "content": "text"}))
        assert "error" in result

    def test_create_document_missing_content(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        result = json.loads(agent._dispatch_tool("create_document", {"filename": "x.md", "content": ""}))
        assert "error" in result

    def test_unknown_tool_returns_error(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        result = json.loads(agent._dispatch_tool("nonexistent_tool", {}))
        assert "error" in result
        assert "nonexistent_tool" in result["error"]


# ---------------------------------------------------------------------------
# TestCoWorkAgentChat
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCoWorkAgentChat:
    async def test_chat_returns_text_and_metrics(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        with patch.object(agent, "_call_ollama_raw", return_value=_fake_ollama_response("Hello!")):
            result = await agent.chat("What's in my workspace?")
        assert result["text"] == "Hello!"
        assert "duration" in result["metrics"]
        assert "tokens" in result["metrics"]
        assert isinstance(result["metrics"]["duration"], float)

    async def test_chat_appends_to_history(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        with patch.object(agent, "_call_ollama_raw", return_value=_fake_ollama_response("Hi")):
            await agent.chat("Hello")
        assert len(agent._history) == 2
        assert agent._history[0]["role"] == "user"
        assert agent._history[0]["content"] == "Hello"
        assert agent._history[1]["role"] == "assistant"
        assert agent._history[1]["content"] == "Hi"

    async def test_chat_publishes_thinking_event(self, tmp_path: Path) -> None:
        mock_bridge = MagicMock()
        agent = CoWorkAgent(workspace_path=tmp_path, event_bridge=mock_bridge)
        with patch.object(agent, "_call_ollama_raw", return_value=_fake_ollama_response("Hi")):
            await agent.chat("Hello")
        thinking_calls = [c for c in mock_bridge.push_event.call_args_list if c[0][0] == "thinking"]
        assert len(thinking_calls) >= 1

    async def test_chat_publishes_final_answer_event(self, tmp_path: Path) -> None:
        mock_bridge = MagicMock()
        agent = CoWorkAgent(workspace_path=tmp_path, event_bridge=mock_bridge)
        with patch.object(agent, "_call_ollama_raw", return_value=_fake_ollama_response("Done")):
            await agent.chat("Hi")
        final_calls = [c for c in mock_bridge.push_event.call_args_list if c[0][0] == "final_answer"]
        assert len(final_calls) == 1
        assert final_calls[0][0][1]["content"] == "Done"

    async def test_chat_handles_ollama_failure(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        with patch.object(agent, "_call_ollama_raw", side_effect=RuntimeError("connection refused")):
            result = await agent.chat("Hello")
        assert "Sorry" in result["text"]
        assert result["metrics"]["tokens"] == 0

    async def test_chat_executes_tool_call_then_gets_final(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path, {"doc.md": "important content"})
        side_effects = [
            _tool_call_response("list_workspace_files", {}),
            _fake_ollama_response("Your workspace has 1 file: doc.md"),
        ]
        with patch.object(agent, "_call_ollama_raw", side_effect=side_effects):
            result = await agent.chat("List my files")
        assert "doc.md" in result["text"]

    async def test_chat_handles_json_string_arguments(self, tmp_path: Path) -> None:
        """Tool arguments sent as JSON string (not dict) should be parsed."""
        agent = _make_agent(tmp_path, {"hello.md": "world"})
        side_effects = [
            (
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "read_workspace_file",
                                    "arguments": '{"path": "hello.md"}',  # JSON string
                                }
                            }
                        ],
                    }
                },
                {"prompt_tokens": 5, "completion_tokens": 2},
            ),
            _fake_ollama_response("File contains: world"),
        ]
        with patch.object(agent, "_call_ollama_raw", side_effect=side_effects):
            result = await agent.chat("Read hello.md")
        assert "world" in result["text"]

    async def test_chat_no_bridge_does_not_crash(self, tmp_path: Path) -> None:
        agent = CoWorkAgent(workspace_path=tmp_path, event_bridge=None)
        with patch.object(agent, "_call_ollama_raw", return_value=_fake_ollama_response("ok")):
            result = await agent.chat("Hi")
        assert result["text"] == "ok"

    def test_reset_clears_history(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        agent._history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
        agent.reset()
        assert agent._history == []

    def test_trim_history_caps_at_max(self, tmp_path: Path) -> None:
        agent = _make_agent(tmp_path)
        for i in range(CoWorkAgent.MAX_HISTORY + 10):
            agent._history.append({"role": "user", "content": str(i)})
        agent._trim_history()
        assert len(agent._history) == CoWorkAgent.MAX_HISTORY
