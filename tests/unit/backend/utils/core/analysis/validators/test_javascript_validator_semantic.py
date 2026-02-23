import pytest
from unittest.mock import MagicMock
from backend.utils.core.analysis.validators.javascript_validator import JavascriptValidator


@pytest.mark.unit
class TestJavascriptValidatorSemantic:
    @pytest.fixture
    def validator(self):
        # Mock command executor to avoid checking for eslint binary in unit tests
        return JavascriptValidator(logger=MagicMock(), command_executor=MagicMock())

    def test_dom_integrity_check_failure(self, validator):
        """Should detect dangerous usage of document.getElementById without null checks."""
        content = """
        const btn = document.getElementById('submit-btn');
        btn.innerHTML = 'Loading...'; // Dangerous!
        """
        result = validator.validate("script.js", content, 2, len(content), ".js")

        assert "Potential crash" in result.message
        assert "Using DOM element 'btn' without null check" in result.message

    def test_dom_integrity_check_success_if(self, validator):
        """Should produce no errors when there is a null check using 'if'."""
        content = """
        const btn = document.getElementById('submit-btn');
        if (btn) {
            btn.innerHTML = 'Loading...';
        }
        """
        # _semantic_integrity_check returns (errors, warnings)
        errors, _warnings = validator._semantic_integrity_check("script.js", content)
        assert not errors

    def test_dom_integrity_check_success_optional_chaining(self, validator):
        """Should produce no errors when optional chaining is used."""
        content = """
        const btn = document.getElementById('submit-btn');
        btn?.innerHTML = 'Loading...';
        """
        errors, _warnings = validator._semantic_integrity_check("script.js", content)
        assert not errors

    def test_poker_integrity_check_failure(self, validator):
        """Missing core poker functions are reported as warnings (non-blocking)."""
        content = """
        class PokerGame {
            start() { console.log('started'); }
        }
        """
        # Poker issues are warnings, not hard errors — they don't fail validate()
        _errors, warnings = validator._semantic_integrity_check("PokerEngine.js", content)
        assert any("shuffle" in w for w in warnings), f"Expected shuffle warning, got: {warnings}"
        assert any("deal" in w for w in warnings), f"Expected deal warning, got: {warnings}"

    def test_poker_integrity_check_success(self, validator):
        """Should produce no errors when core poker functions are present."""
        content = """
        class PokerGame {
            shuffle() { /* ... */ }
            deal() { /* ... */ }
        }
        """
        errors, _warnings = validator._semantic_integrity_check("PokerEngine.js", content)
        assert not errors

    def test_implicit_globals(self, validator):
        """Should detect implicit global variables."""
        content = """
        function setup() {
            score = 0; // Implicit global
            let health = 100;
        }
        """
        result = validator.validate("game.js", content, 4, len(content), ".js")
        assert "Implicit global variable 'score'" in result.message
