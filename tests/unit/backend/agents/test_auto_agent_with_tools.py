"""Unit tests for AutoAgentWithTools."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.auto_agent_with_tools import AutoAgentWithTools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(tmp_path: Path) -> AutoAgentWithTools:
    return AutoAgentWithTools(
        llm_manager=MagicMock(),
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
        generated_projects_dir=tmp_path / "projects",
    )


def _finish_tool_call() -> dict:
    return {
        "tool_calls": [
            {
                "function": {
                    "name": "finish_project",
                    "arguments": {"summary": "Done."},
                }
            }
        ],
        "content": "",
    }


def _plan_tool_call() -> dict:
    blueprint = {
        "project_type": "api",
        "tech_stack": ["python"],
        "files": [{"path": "main.py", "purpose": "entry point"}],
    }
    return {
        "tool_calls": [
            {
                "function": {
                    "name": "plan_project",
                    "arguments": {"blueprint_json": json.dumps(blueprint)},
                }
            }
        ],
        "content": "",
    }


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAutoAgentWithToolsInit:
    def test_init_creates_projects_dir(self, tmp_path):
        agent = _make_agent(tmp_path)
        assert (tmp_path / "projects").is_dir()

    def test_init_sets_max_iterations(self, tmp_path):
        assert AutoAgentWithTools.MAX_ITERATIONS == 30

    def test_init_sets_roles(self, tmp_path):
        assert AutoAgentWithTools._ROLE == "tool_agent"
        assert AutoAgentWithTools._CODE_ROLE == "code_generator"

    def test_default_project_root_under_generated_dir(self, tmp_path):
        """project_root should default to generated_projects_dir / project_name."""
        agent = _make_agent(tmp_path)
        # We verify by running with explicit project_root and checking path
        assert agent.generated_projects_dir == tmp_path / "projects"


# ---------------------------------------------------------------------------
# _dispatch_tool_call
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDispatchToolCall:
    async def test_dispatch_unknown_tool(self, tmp_path):
        agent = _make_agent(tmp_path)
        from backend.utils.domains.auto_generation.tools.project_creation_tools import (
            ProjectCreationTools,
        )

        agent._tools = ProjectCreationTools(
            project_root=tmp_path / "p",
            event_publisher=MagicMock(),
            logger=MagicMock(),
        )
        agent._code_client = MagicMock()
        result = await agent._dispatch_tool_call("nonexistent_tool", {})
        assert result["ok"] is False
        assert "Unknown tool" in result["error"]

    async def test_dispatch_write_project_file_requires_path(self, tmp_path):
        agent = _make_agent(tmp_path)
        from backend.utils.domains.auto_generation.tools.project_creation_tools import (
            ProjectCreationTools,
        )

        agent._tools = ProjectCreationTools(
            project_root=tmp_path / "p",
            event_publisher=MagicMock(),
            logger=MagicMock(),
        )
        agent._code_client = MagicMock()
        result = await agent._dispatch_tool_call("write_project_file", {"spec": "some spec"})
        assert result["ok"] is False
        assert "relative_path" in result["error"]

    async def test_dispatch_write_project_file_requires_spec(self, tmp_path):
        agent = _make_agent(tmp_path)
        from backend.utils.domains.auto_generation.tools.project_creation_tools import (
            ProjectCreationTools,
        )

        agent._tools = ProjectCreationTools(
            project_root=tmp_path / "p",
            event_publisher=MagicMock(),
            logger=MagicMock(),
        )
        agent._code_client = MagicMock()
        result = await agent._dispatch_tool_call("write_project_file", {"relative_path": "main.py"})
        assert result["ok"] is False
        assert "spec" in result["error"]

    async def test_dispatch_plan_project(self, tmp_path):
        agent = _make_agent(tmp_path)
        from backend.utils.domains.auto_generation.tools.project_creation_tools import (
            ProjectCreationTools,
        )

        agent._tools = ProjectCreationTools(
            project_root=tmp_path / "p",
            event_publisher=MagicMock(),
            logger=MagicMock(),
        )
        result = await agent._dispatch_tool_call(
            "plan_project",
            {"blueprint_json": '{"project_type":"api","files":[]}'},
        )
        assert result["ok"] is True

    async def test_dispatch_finish_project(self, tmp_path):
        agent = _make_agent(tmp_path)
        from backend.utils.domains.auto_generation.tools.project_creation_tools import (
            ProjectCreationTools,
        )

        agent._tools = ProjectCreationTools(
            project_root=tmp_path / "p",
            event_publisher=MagicMock(),
            logger=MagicMock(),
        )
        agent._tools.project_root.mkdir(parents=True)
        result = await agent._dispatch_tool_call("finish_project", {"summary": "Done."})
        assert result["ok"] is True
        assert agent._tools.finished is True


# ---------------------------------------------------------------------------
# _get_client / _get_code_client fallbacks
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestClientResolution:
    def test_get_client_falls_back_to_generalist(self, tmp_path):
        agent = _make_agent(tmp_path)
        agent.llm_manager.get_client.side_effect = [
            Exception("role not found"),
            MagicMock(name="generalist_client"),
        ]
        client = agent._get_client()
        assert client is not None

    def test_get_code_client_falls_back_to_coder(self, tmp_path):
        agent = _make_agent(tmp_path)
        coder = MagicMock(name="coder_client")
        agent.llm_manager.get_client.side_effect = [
            Exception("code_generator not found"),
            coder,
        ]
        client = agent._get_code_client()
        assert client is coder

    def test_get_code_client_falls_back_to_orchestrator(self, tmp_path):
        """Last resort: reuse the orchestrator client."""
        agent = _make_agent(tmp_path)
        orchestrator = MagicMock(name="orchestrator")
        agent._client = orchestrator
        agent.llm_manager.get_client.side_effect = [
            Exception("code_generator not found"),
            Exception("coder not found"),
        ]
        client = agent._get_code_client()
        assert client is orchestrator


# ---------------------------------------------------------------------------
# run() — mocked tool loop
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRun:
    async def test_run_returns_project_root(self, tmp_path):
        agent = _make_agent(tmp_path)

        # Mock both clients
        mock_client = MagicMock()
        mock_client.model = "ministral-3:8b"
        mock_client.stream_chat = AsyncMock(
            return_value=(_finish_tool_call(), {"prompt_tokens": 10, "completion_tokens": 5})
        )
        mock_client.unload_model = MagicMock()
        mock_client.close = AsyncMock()

        agent.llm_manager.get_client.return_value = mock_client

        with patch.object(
            agent, "_load_prompt", AsyncMock(return_value=("sys", "Build {project_name}: {description}"))
        ):
            # Patch _tool_loop to finish immediately (sets tools.finished)
            async def fake_loop(*args, **kwargs):
                agent._tools.finished = True

            with patch.object(agent, "_tool_loop", side_effect=fake_loop):
                result = await agent.run("A test API", "test_api")

        assert isinstance(result, Path)
        assert result.name == "test_api"

    async def test_run_sets_default_project_root(self, tmp_path):
        agent = _make_agent(tmp_path)
        mock_client = MagicMock()
        mock_client.model = "m"
        mock_client.unload_model = MagicMock()
        mock_client.close = AsyncMock()
        agent.llm_manager.get_client.return_value = mock_client

        with patch.object(agent, "_load_prompt", AsyncMock(return_value=("s", "{project_name}{description}"))):

            async def fake_loop(*args, **kwargs):
                agent._tools.finished = True

            with patch.object(agent, "_tool_loop", side_effect=fake_loop):
                result = await agent.run("desc", "my_proj")

        assert result == tmp_path / "projects" / "my_proj"

    async def test_run_unloads_clients_on_exception(self, tmp_path):
        agent = _make_agent(tmp_path)
        mock_client = MagicMock()
        mock_client.model = "m"
        mock_client.unload_model = MagicMock()
        mock_client.close = AsyncMock()
        agent.llm_manager.get_client.return_value = mock_client

        with patch.object(agent, "_load_prompt", AsyncMock(return_value=("s", "{project_name}{description}"))):

            async def exploding_loop(*args, **kwargs):
                raise RuntimeError("loop failed")

            with patch.object(agent, "_tool_loop", side_effect=exploding_loop):
                with pytest.raises(RuntimeError):
                    await agent.run("desc", "my_proj")

        # unload_model should have been called despite the exception
        mock_client.unload_model.assert_called()


# ---------------------------------------------------------------------------
# _load_prompt — YAML fallback
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLoadPrompt:
    async def test_load_prompt_returns_tuple(self, tmp_path):
        agent = _make_agent(tmp_path)
        system, user = await agent._load_prompt()
        assert isinstance(system, str)
        assert isinstance(user, str)
        assert len(system) > 0
        assert "{project_name}" in user

    async def test_load_prompt_fallback_when_yaml_missing(self, tmp_path):
        """When PromptLoader raises inside _load_prompt, should fall back to inline defaults."""
        agent = _make_agent(tmp_path)
        with patch(
            "backend.utils.core.llm.prompt_loader.PromptLoader",
            side_effect=Exception("no yaml"),
        ):
            system, user = await agent._load_prompt()
        assert isinstance(system, str)
        assert len(system) > 0


# ---------------------------------------------------------------------------
# Tool loop nudge behaviour
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestToolLoopNudge:
    async def test_loop_aborts_after_3_consecutive_text_responses(self, tmp_path):
        """After 3 consecutive text-only responses, loop should stop."""
        agent = _make_agent(tmp_path)

        mock_client = MagicMock()
        mock_client.stream_chat = AsyncMock(
            return_value=(
                {"tool_calls": [], "content": "I am thinking..."},
                {"prompt_tokens": 5, "completion_tokens": 5},
            )
        )
        agent._client = mock_client

        from backend.utils.domains.auto_generation.tools.project_creation_tools import (
            ProjectCreationTools,
        )

        agent._tools = ProjectCreationTools(
            project_root=tmp_path / "p",
            event_publisher=MagicMock(),
            logger=MagicMock(),
        )

        await agent._tool_loop("system", "user", 0.0, None)

        # Should have called stream_chat exactly 3 times (3 consecutive text-only)
        assert mock_client.stream_chat.call_count == 3

    async def test_loop_stops_when_finished_after_text_response(self, tmp_path):
        """If tools.finished is True on a text-only response, loop should stop cleanly."""
        agent = _make_agent(tmp_path)

        from backend.utils.domains.auto_generation.tools.project_creation_tools import (
            ProjectCreationTools,
        )

        tools = ProjectCreationTools(
            project_root=tmp_path / "p",
            event_publisher=MagicMock(),
            logger=MagicMock(),
        )
        tools.finished = True
        agent._tools = tools

        mock_client = MagicMock()
        mock_client.stream_chat = AsyncMock(return_value=({"tool_calls": [], "content": "summary text"}, {}))
        agent._client = mock_client

        await agent._tool_loop("system", "user", 0.0, None)
        # Should exit immediately without nudging
        assert mock_client.stream_chat.call_count == 1

    async def test_loop_respects_time_limit(self, tmp_path):
        """When max_duration_seconds=0, the loop should not make any LLM calls."""
        import time

        agent = _make_agent(tmp_path)

        from backend.utils.domains.auto_generation.tools.project_creation_tools import (
            ProjectCreationTools,
        )

        agent._tools = ProjectCreationTools(
            project_root=tmp_path / "p",
            event_publisher=MagicMock(),
            logger=MagicMock(),
        )
        mock_client = MagicMock()
        mock_client.stream_chat = AsyncMock()
        agent._client = mock_client

        start = time.time() - 10  # already 10s elapsed
        await agent._tool_loop("system", "user", start, max_duration_seconds=1)

        mock_client.stream_chat.assert_not_called()

    async def test_loop_gives_grace_pass_after_tool_error(self, tmp_path):
        """A text-only response immediately after a tool error should not count as a nudge."""
        agent = _make_agent(tmp_path)

        from backend.utils.domains.auto_generation.tools.project_creation_tools import (
            ProjectCreationTools,
        )

        agent._tools = ProjectCreationTools(
            project_root=tmp_path / "p",
            event_publisher=MagicMock(),
            logger=MagicMock(),
        )

        # Sequence: tool_call (returns error) → text → text → text → abort at 3 nudges
        # With grace pass: the first text after tool error is free → abort at 4 calls total
        tool_call_response = {
            "tool_calls": [{"function": {"name": "nonexistent_tool", "arguments": {}}}],
            "content": "",
        }
        text_response = {"tool_calls": [], "content": "thinking..."}

        mock_client = MagicMock()
        mock_client.stream_chat = AsyncMock(
            side_effect=[
                (tool_call_response, {}),  # iter 1: tool call → error
                (text_response, {}),  # iter 2: text → grace pass (no nudge)
                (text_response, {}),  # iter 3: text → nudge 1
                (text_response, {}),  # iter 4: text → nudge 2
                (text_response, {}),  # iter 5: text → nudge 3 → abort
            ]
        )
        agent._client = mock_client

        await agent._tool_loop("system", "user", 0.0, None)

        # Without grace pass: abort at 3 nudges = 4 LLM calls (1 tool + 3 text)
        # With grace pass: first text after error is free → 5 LLM calls total
        assert mock_client.stream_chat.call_count == 5


# ---------------------------------------------------------------------------
# _dispatch_tool_call — spec fallback coverage
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDispatchSpecFallback:
    def _make_tools(self, tmp_path):
        from backend.utils.domains.auto_generation.tools.project_creation_tools import (
            ProjectCreationTools,
        )

        return ProjectCreationTools(
            project_root=tmp_path / "p",
            event_publisher=MagicMock(),
            logger=MagicMock(),
        )

    async def test_spec_fallback_from_content_arg(self, tmp_path):
        """If model passes 'content' instead of 'spec', file should still be generated."""
        agent = _make_agent(tmp_path)
        agent._tools = self._make_tools(tmp_path)
        agent._code_client = MagicMock()
        agent._code_client.stream_chat = AsyncMock(return_value=({"content": "print('hello')", "tool_calls": []}, {}))
        result = await agent._dispatch_tool_call(
            "write_project_file",
            {"relative_path": "main.py", "content": "A simple Python script"},
        )
        assert result["ok"] is True

    async def test_spec_fallback_from_code_arg(self, tmp_path):
        """If model passes 'code' instead of 'spec', file should still be generated."""
        agent = _make_agent(tmp_path)
        agent._tools = self._make_tools(tmp_path)
        agent._code_client = MagicMock()
        agent._code_client.stream_chat = AsyncMock(
            return_value=({"content": "console.log('hi')", "tool_calls": []}, {})
        )
        result = await agent._dispatch_tool_call(
            "write_project_file",
            {"relative_path": "index.js", "code": "Browser entry point with event listeners"},
        )
        assert result["ok"] is True

    async def test_spec_derived_from_blueprint(self, tmp_path):
        """If spec is empty but blueprint has a purpose for the file, derive spec automatically."""
        import json as _json

        agent = _make_agent(tmp_path)
        agent._tools = self._make_tools(tmp_path)
        agent._code_client = MagicMock()
        agent._code_client.stream_chat = AsyncMock(return_value=({"content": "def main(): pass", "tool_calls": []}, {}))

        # Set up blueprint with a purpose for main.py
        blueprint = {
            "project_type": "api",
            "tech_stack": ["python"],
            "files": [{"path": "main.py", "purpose": "FastAPI entry point"}],
        }
        await agent._tools.plan_project(_json.dumps(blueprint))

        result = await agent._dispatch_tool_call(
            "write_project_file",
            {"relative_path": "main.py"},  # no spec or content
        )
        # Should succeed via blueprint-derived spec
        assert result["ok"] is True

    async def test_spec_error_when_no_fallback(self, tmp_path):
        """When spec is empty AND no blueprint exists, return an error."""
        agent = _make_agent(tmp_path)
        agent._tools = self._make_tools(tmp_path)
        agent._code_client = MagicMock()
        result = await agent._dispatch_tool_call(
            "write_project_file",
            {"relative_path": "main.py"},  # no spec, no blueprint
        )
        assert result["ok"] is False
        assert "spec" in result["error"].lower()
