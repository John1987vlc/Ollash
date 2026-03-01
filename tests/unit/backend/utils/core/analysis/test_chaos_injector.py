"""Unit tests for chaos_injector.py — Feature 4."""

import pytest

from backend.utils.core.analysis.chaos_injector import ChaosInjector


@pytest.mark.unit
class TestChaosInjectorShouldInject:
    def test_rate_zero_never_injects(self):
        injector = ChaosInjector(injection_rate=0.0)
        for _ in range(20):
            assert not injector.should_inject()

    def test_rate_one_always_injects(self):
        injector = ChaosInjector(injection_rate=1.0)
        for _ in range(20):
            assert injector.should_inject()


@pytest.mark.unit
class TestRemoveImport:
    def test_removes_python_import(self):
        code = "import os\nimport sys\n\ndef foo():\n    pass\n"
        injector = ChaosInjector(injection_rate=1.0)
        corrupted, desc = injector._remove_random_import(code, "python")
        assert "Removed import line" in desc
        assert corrupted.count("import") < code.count("import")

    def test_no_imports_returns_unchanged(self):
        code = "def foo():\n    x = 1\n"
        injector = ChaosInjector(injection_rate=1.0)
        corrupted, desc = injector._remove_random_import(code, "python")
        assert desc == ""
        assert corrupted == code

    def test_js_import_line_removed(self):
        code = "import fs from 'fs';\nimport path from 'path';\nfunction foo() {}\n"
        injector = ChaosInjector(injection_rate=1.0)
        corrupted, desc = injector._remove_random_import(code, "javascript")
        assert "Removed import line" in desc


@pytest.mark.unit
class TestRenameVariable:
    def test_renames_python_local_variable(self):
        code = "def foo():\n    my_var = 42\n    return my_var\n"
        injector = ChaosInjector(injection_rate=1.0)
        corrupted, desc = injector._rename_local_variable(code, "python")
        assert "Renamed variable" in desc
        assert "my_var" in desc
        assert "__chaos_my_var_x" in corrupted

    def test_protected_names_not_renamed(self):
        code = "def foo(self):\n    self.x = 1\n"
        injector = ChaosInjector(injection_rate=1.0)
        corrupted, desc = injector._rename_local_variable(code, "python")
        # 'self' is protected — no match deep enough
        assert desc == "" or "self" not in desc.lower() or corrupted == code

    def test_no_local_var_returns_unchanged(self):
        code = "import os\n"
        injector = ChaosInjector(injection_rate=1.0)
        corrupted, desc = injector._rename_local_variable(code, "python")
        assert desc == ""
        assert corrupted == code


@pytest.mark.unit
class TestInjectFault:
    def test_rate_zero_always_unchanged(self):
        injector = ChaosInjector(injection_rate=0.0)
        code = "import os\ndef foo():\n    x = 1\n"
        corrupted, desc = injector.inject_fault(code, "python")
        assert corrupted == code
        assert desc == ""

    def test_empty_content_returns_unchanged(self):
        injector = ChaosInjector(injection_rate=1.0)
        corrupted, desc = injector.inject_fault("", "python")
        assert corrupted == ""
        assert desc == ""

    def test_returns_two_tuple(self):
        injector = ChaosInjector(injection_rate=1.0)
        result = injector.inject_fault("import os\ndef foo():\n    x=1\n", "python")
        assert isinstance(result, tuple)
        assert len(result) == 2
