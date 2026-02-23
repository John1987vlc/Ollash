import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from backend.agents.auto_agent_phases.javascript_optimization_phase import JavaScriptOptimizationPhase

_PROMPT_LOADER_PATH = "backend.utils.core.llm.prompt_loader.PromptLoader"
_HTML_PROMPTS = {"html_js_dom_fix": {"system": "Fix HTML", "user": "Fix {missing_ids} in {html}"}}
_CROSS_JS_PROMPTS = {"cross_js_coherence": {"system": "Fix JS", "user": "Fix {project_summary}"}}


@pytest.mark.unit
class TestJavaScriptOptimizationPhase:
    @pytest.fixture
    def mock_context(self):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.event_publisher = MagicMock()
        ctx.file_manager = MagicMock()
        ctx.llm_manager.get_client.return_value.chat = MagicMock(return_value=({"content": ""}, {}))
        ctx.response_parser.extract_raw_content = MagicMock(return_value="")
        return ctx

    @pytest.mark.asyncio
    async def test_execute_skips_no_js(self, mock_context):
        phase = JavaScriptOptimizationPhase(mock_context)
        files = {"index.html": "<html></html>", "style.css": "body {}"}
        new_files, _, _ = await phase.execute("", "", Path("."), "", {}, files)
        mock_context.event_publisher.publish.assert_not_called()
        assert new_files == files

    @pytest.mark.asyncio
    async def test_html_js_integration_check(self, mock_context):
        phase = JavaScriptOptimizationPhase(mock_context)
        js_content = "document.getElementById('missing-id ').innerHTML = 'hi ';"
        html_content = "<html><body><div id='existing-id '></div></body></html>"
        files = {"src/script.js": js_content, "src/index.html": html_content}
        fixed_html = "<html><body><div id='existing-id '></div><div id='missing-id '></div></body></html>"
        mock_context.llm_manager.get_client.return_value.chat.return_value = ({"content": fixed_html}, {})
        mock_context.response_parser.extract_raw_content.return_value = fixed_html
        with patch(_PROMPT_LOADER_PATH) as ml:
            ml.return_value.load_prompt.return_value = _HTML_PROMPTS
            new_files, _, _ = await phase.execute("", "", Path("."), "", {}, files)
        assert new_files["src/index.html"] == fixed_html
        mock_context.file_manager.write_file.assert_called()
        logged = [str(c) for c in mock_context.logger.info.call_args_list]
        assert any("index.html" in c for c in logged)

    @pytest.mark.asyncio
    async def test_cross_js_coherence_check(self, mock_context):
        phase = JavaScriptOptimizationPhase(mock_context)
        files = {
            "src/game.js": "const engine = new Engine(); engine.start();",
            "src/engine.js": "class Engine { init() {} }",
        }
        fix_xml = "<fix file='src/engine.js'>class Engine { init() {} start() {} }</fix>"
        mock_context.llm_manager.get_client.return_value.chat.return_value = ({"content": fix_xml}, {})
        with patch(_PROMPT_LOADER_PATH) as ml:
            ml.return_value.load_prompt.return_value = _CROSS_JS_PROMPTS
            new_files, _, _ = await phase.execute("", "", Path("."), "", {}, files)
        assert "start() {}" in new_files["src/engine.js"]
        mock_context.file_manager.write_file.assert_called()
