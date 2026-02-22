import pytest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
from backend.agents.auto_agent_phases.javascript_optimization_phase import JavaScriptOptimizationPhase

class TestJavaScriptOptimizationPhase:

    @pytest.fixture
    def mock_context(self):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.event_publisher = MagicMock()
        ctx.file_manager = MagicMock()
        ctx.llm_manager.get_client.return_value.chat = AsyncMock(return_value=({"content": ""}, {}))
        ctx.response_parser.extract_code = MagicMock(return_value="")
        return ctx

    @pytest.mark.asyncio
    async def test_execute_skips_no_js(self, mock_context):
        phase = JavaScriptOptimizationPhase(mock_context)
        files = {"index.html": "<html></html>", "style.css": "body {}"}
        
        new_files, _, _ = await phase.execute("", "", Path("."), "", {}, files)
        
        # Should verify optimization wasn't triggered
        mock_context.event_publisher.publish.assert_not_called()
        assert new_files == files

    @pytest.mark.asyncio
    async def test_html_js_integration_check(self, mock_context):
        phase = JavaScriptOptimizationPhase(mock_context)
        
        # Setup: JS uses an ID that is missing in HTML
        js_content = "document.getElementById('missing-id').innerHTML = 'hi';"
        html_content = "<html><body><div id='existing-id'></div></body></html>"
        
        files = {
            "src/script.js": js_content,
            "src/index.html": html_content
        }
        
        # Mock LLM response to "fix" the HTML
        fixed_html = "<html><body><div id='existing-id'></div><div id='missing-id'></div></body></html>"
        # Use single line string with \n to avoid syntax errors
        llm_response_content = f"Here is code:\n```html\n{fixed_html}\n```"
        
        mock_context.llm_manager.get_client.return_value.chat.return_value = (
            {"content": llm_response_content}, {}
        )
        mock_context.response_parser.extract_code.return_value = fixed_html

        new_files, _, _ = await phase.execute("", "", Path("."), "", {}, files)
        
        # Verification
        assert new_files["src/index.html"] == fixed_html
        mock_context.file_manager.write_file.assert_called()
        mock_context.logger.info.assert_any_call("    ✓ index.html updated with missing IDs.")

    @pytest.mark.asyncio
    async def test_cross_js_coherence_check(self, mock_context):
        phase = JavaScriptOptimizationPhase(mock_context)
        
        files = {
            "src/game.js": "const engine = new Engine(); engine.start();",
            "src/engine.js": "class Engine { init() {} }" # Missing start()
        }
        
        # Mock LLM detecting the issue and providing a fix
        fix_xml = "<fix file='src/engine.js'>class Engine { init() {} start() {} }</fix>"
        mock_context.llm_manager.get_client.return_value.chat.return_value = (
            {"content": f"I found an error. {fix_xml}"}, {}
        )

        new_files, _, _ = await phase.execute("", "", Path("."), "", {}, files)
        
        assert "start() {}" in new_files["src/engine.js"]
        mock_context.file_manager.write_file.assert_called()
