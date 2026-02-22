import pytest
from unittest.mock import MagicMock
from backend.utils.core.analysis.validators.javascript_validator import JavascriptValidator
from backend.utils.core.analysis.validators.base_validator import ValidationStatus

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
        """Should pass if there is a null check using 'if'."""
        content = """
        const btn = document.getElementById('submit-btn');
        if (btn) {
            btn.innerHTML = 'Loading...';
        }
        """
        # We manually call the semantic check since validate might try to run eslint
        errors = validator._semantic_integrity_check("script.js", content)
        assert not errors

    def test_dom_integrity_check_success_optional_chaining(self, validator):
        """Should pass if there is usage of optional chaining."""
        content = """
        const btn = document.getElementById('submit-btn');
        btn?.innerHTML = 'Loading...';
        """
        errors = validator._semantic_integrity_check("script.js", content)
        assert not errors

    def test_poker_integrity_check_failure(self, validator):
        """Should detect missing core functions in Poker files."""
        content = """
        class PokerGame {
            start() { console.log('started'); }
        }
        """
        result = validator.validate("PokerEngine.js", content, 3, len(content), ".js")
        
        assert "Poker logic missing 'shuffle'" in result.message
        assert "Poker logic missing 'deal'" in result.message

    def test_poker_integrity_check_success(self, validator):
        """Should pass if core functions are present."""
        content = """
        class PokerGame {
            shuffle() { /* ... */ }
            deal() { /* ... */ }
        }
        """
        errors = validator._semantic_integrity_check("PokerEngine.js", content)
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
