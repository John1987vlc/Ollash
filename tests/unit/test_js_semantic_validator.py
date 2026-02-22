import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.utils.core.analysis.validators.javascript_validator import JavascriptValidator
from backend.utils.core.analysis.validators.base_validator import ValidationStatus

def test_js_integrity():
    validator = JavascriptValidator()
    
    # Case 1: Potential DOM crash
    bad_js = "const btn = document.getElementById('myBtn'); btn.onclick = () => {};"
    result = validator.validate("test.js", bad_js, 1, len(bad_js), ".js")
    print(f"DOM Test: {result.status} - {result.message}")
    assert "Potential crash" in result.message
    
    # Case 2: Missing Poker logic
    poker_js = "// Poker Game Engine\nfunction init() { console.log('start'); }"
    result = validator.validate("PokerEngine.js", poker_js, 2, len(poker_js), ".js")
    print(f"Poker Test: {result.status} - {result.message}")
    assert "missing 'shuffle'" in result.message

if __name__ == "__main__":
    try:
        test_js_integrity()
        print("\n✅ All validator tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
