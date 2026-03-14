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
        ctx.event_publisher.publish = MagicMock()
        ctx.event_publisher.publish_sync = MagicMock()
        ctx.file_manager = MagicMock()
        ctx.llm_manager.get_client.return_value.chat = MagicMock(return_value=({"content": ""}, {}))
        ctx.response_parser.extract_code = MagicMock(return_value="")
        ctx._is_small_model.return_value = True
        return ctx

    def test_execute_runs_even_without_js(self, mock_context):
        phase = JavaScriptOptimizationPhase(mock_context)
        files = {"index.html": "<html></html>", "style.css": "body {}"}
        new_files, _, _ = phase.execute("", "", Path("."), "", {}, files)
        # It should publish start and complete events
        assert mock_context.event_publisher.publish_sync.call_count == 2
        assert new_files == files

    def test_html_js_integration_check(self, mock_context):
        phase = JavaScriptOptimizationPhase(mock_context)
        html_content = "<html><body><script src='wrong.js'></script></body></html>"
        files = {"src/index.html": html_content, "src/app.js": "console.log('hi');"}

        fixed_html = "<html><body><script src='app.js'></script></body></html>"

        mock_context.llm_manager.get_client.return_value.chat.return_value = ({"content": fixed_html}, {})
        mock_context.response_parser.extract_code.return_value = fixed_html

        with patch(_PROMPT_LOADER_PATH) as ml:
            ml.return_value.load_prompt = MagicMock(return_value=_HTML_PROMPTS)
            new_files, _, _ = phase.execute("", "", Path("."), "", {}, files)

        assert "app.js" in new_files["src/index.html"]

    def test_cross_js_coherence_check(self, mock_context):
        phase = JavaScriptOptimizationPhase(mock_context)
        mock_context.logic_plan = {"src/engine.js": {"exports": ["Engine", "start"]}}

        files = {
            "src/app.js": "const engine = new Engine(); engine.start();" + "\n" * 25,
            "src/engine.js": "class Engine { init() {} }" + "\n" * 25,
        }
        fixed_code = "class Engine { init() {} start() {} }" + "\n" * 25

        mock_context.llm_manager.get_client.return_value.chat.return_value = ({"content": fixed_code}, {})
        mock_context.response_parser.extract_code.return_value = fixed_code

        with patch(_PROMPT_LOADER_PATH) as ml:
            ml.return_value.load_prompt = MagicMock(return_value=_CROSS_JS_PROMPTS)
            new_files, _, _ = phase.execute("", "", Path("."), "", {}, files)

        assert "start() {}" in new_files["src/engine.js"]
        mock_context.file_manager.write_file.assert_called()
