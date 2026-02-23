"""Standalone smoke tests for JavascriptValidator.

These mirror the inline ``if __name__ == "__main__"`` block that used to live
in the source file, ported to proper pytest tests so CI can pick them up.
"""

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent))

from backend.utils.core.analysis.validators.javascript_validator import JavascriptValidator


@pytest.mark.unit
def test_js_dom_crash_detection():
    """validate() must flag a DOM element used without a null-check."""
    validator = JavascriptValidator()
    bad_js = "const btn = document.getElementById('myBtn'); btn.onclick = () => {};"
    result = validator.validate("test.js", bad_js, 1, len(bad_js), ".js")
    assert "Potential crash" in result.message


@pytest.mark.unit
def test_js_poker_warnings():
    """Missing core poker functions are emitted as warnings (non-blocking)."""
    validator = JavascriptValidator()
    poker_js = "// Poker Game Engine\nfunction init() { console.log('start'); }"
    _errors, warnings = validator._semantic_integrity_check("PokerEngine.js", poker_js)
    assert any("shuffle" in w for w in warnings), f"Expected shuffle warning, got: {warnings}"


# Keep the original script entrypoint so the file can still be run directly.
@pytest.mark.unit
def test_js_integrity():
    """Backward-compat test that runs the original two cases."""
    test_js_dom_crash_detection()
    test_js_poker_warnings()
