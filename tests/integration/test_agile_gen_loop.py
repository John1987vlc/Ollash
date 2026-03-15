"""Integration test for CodeFillPhase — file generation with syntax validation and retry."""

from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.code_fill_phase import CodeFillPhase
from backend.agents.auto_agent_phases.phase_context import FilePlan, PhaseContext


def _make_ctx(tmp_path, llm_responses: list):
    """Create a PhaseContext where client.chat() returns pre-set responses in order.

    BasePhase._llm_call expects: response_data.get("message", {}).get("content", "")
    so each mock response must be {"message": {"content": "..."}, "eval_count": N}.
    """
    llm_manager = MagicMock()
    mock_client = MagicMock()
    mock_client.model = "qwen3.5:4b"

    responses = iter(llm_responses)

    def _chat(*a, **kw):
        try:
            content = next(responses)
        except StopIteration:
            content = llm_responses[-1]
        return ({"message": {"content": content}, "eval_count": len(content.split())}, {})

    mock_client.chat.side_effect = _chat
    llm_manager.get_client.return_value = mock_client

    return PhaseContext(
        project_name="test_project",
        project_description="A simple test project",
        project_root=tmp_path,
        llm_manager=llm_manager,
        file_manager=MagicMock(),
        event_publisher=MagicMock(),
        logger=MagicMock(),
        project_type="cli",
        tech_stack=["python"],
    )


@pytest.mark.integration
def test_code_fill_phase_generates_file(tmp_path):
    """CodeFillPhase writes generated content to disk and updates ctx.generated_files."""
    code = "def hello():\n    return 'hello'\n"
    ctx = _make_ctx(tmp_path, [code])
    ctx.blueprint = [
        FilePlan(
            path="src/hello.py",
            purpose="Hello world function",
            exports=["hello"],
            imports=[],
            key_logic="Returns the string 'hello'",
            priority=1,
        )
    ]

    CodeFillPhase().run(ctx)

    assert "src/hello.py" in ctx.generated_files
    assert "hello" in ctx.generated_files["src/hello.py"]
    assert ctx.file_manager.write_file.called


@pytest.mark.integration
def test_code_fill_phase_retries_on_syntax_error(tmp_path):
    """CodeFillPhase retries once if generated Python has a syntax error."""
    ctx = _make_ctx(
        tmp_path,
        [
            "def broken(:\n    pass\n",  # syntax error — triggers retry
            "def fixed():\n    return True\n",  # valid
        ],
    )
    ctx.blueprint = [
        FilePlan(
            path="src/fixed.py",
            purpose="Fixed function",
            exports=["fixed"],
            imports=[],
            key_logic="Returns True",
            priority=1,
        )
    ]

    CodeFillPhase().run(ctx)

    assert "src/fixed.py" in ctx.generated_files
    assert "fixed" in ctx.generated_files["src/fixed.py"]
    # LLM should have been called twice (initial + 1 retry)
    client = ctx.llm_manager.get_client.return_value
    assert client.chat.call_count == 2
