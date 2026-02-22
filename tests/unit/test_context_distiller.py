import pytest
from backend.utils.core.analysis.context_distiller import ContextDistiller

def test_distill_simple_python():
    code = """
import os
from pathlib import Path

class MyClass:
    \"\"\"This is a test class.\"\"\"
    def my_method(self, a: int, b: str = "default"):
        x = a + 1
        return x

def top_level_func(x):
    \"\"\"Func docstring.\"\"\"
    return x * 2
"""
    distilled = ContextDistiller.distill_file("test.py", code)
    
    assert "# --- Imports ---" in distilled
    assert "import os" in distilled
    assert "from pathlib import Path" in distilled
    assert "class MyClass:" in distilled
    assert "This is a test class." in distilled
    assert "def my_method(self, a: int, b: str = 'default'): ..." in distilled or "def my_method(self, a: int, b: str='default'): ..." in distilled
    assert "def top_level_func(x): ..." in distilled
    assert "Func docstring." in distilled
    # Internal logic should be stripped
    assert "x = a + 1" not in distilled
    assert "return x" not in distilled

def test_distill_syntax_error():
    # Broken code
    code = "class MyClass: def unfinished(self,"
    distilled = ContextDistiller.distill_file("error.py", code)
    
    assert "truncated due to parsing error" in distilled
    assert "class MyClass" in distilled
