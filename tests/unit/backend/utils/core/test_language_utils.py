"""Unit tests for LanguageUtils."""

import pytest

from backend.utils.core.language_utils import LanguageUtils


@pytest.mark.unit
class TestInferLanguage:
    def test_python(self):
        assert LanguageUtils.infer_language("app.py") == "python"

    def test_javascript(self):
        assert LanguageUtils.infer_language("index.js") == "javascript"

    def test_jsx(self):
        assert LanguageUtils.infer_language("Component.jsx") == "javascript"

    def test_typescript(self):
        assert LanguageUtils.infer_language("server.ts") == "typescript"

    def test_tsx(self):
        assert LanguageUtils.infer_language("App.tsx") == "typescript"

    def test_go(self):
        assert LanguageUtils.infer_language("main.go") == "go"

    def test_rust(self):
        assert LanguageUtils.infer_language("lib.rs") == "rust"

    def test_java(self):
        assert LanguageUtils.infer_language("Main.java") == "java"

    def test_cpp(self):
        assert LanguageUtils.infer_language("main.cpp") == "cpp"

    def test_c(self):
        assert LanguageUtils.infer_language("utils.c") == "c"

    def test_csharp(self):
        assert LanguageUtils.infer_language("Program.cs") == "csharp"

    def test_ruby(self):
        assert LanguageUtils.infer_language("app.rb") == "ruby"

    def test_php(self):
        assert LanguageUtils.infer_language("index.php") == "php"

    def test_swift(self):
        assert LanguageUtils.infer_language("Main.swift") == "swift"

    def test_kotlin(self):
        assert LanguageUtils.infer_language("Main.kt") == "kotlin"

    def test_unknown_extension(self):
        assert LanguageUtils.infer_language("archive.zip") == "unknown"

    def test_no_extension(self):
        assert LanguageUtils.infer_language("Makefile") == "unknown"

    def test_case_insensitive_extension(self):
        assert LanguageUtils.infer_language("SCRIPT.PY") == "python"

    def test_path_with_directories(self):
        assert LanguageUtils.infer_language("src/utils/helper.py") == "python"


@pytest.mark.unit
class TestGroupFilesByLanguage:
    def test_groups_python_files(self):
        files = {"app.py": "code", "utils.py": "code2"}
        result = LanguageUtils.group_files_by_language(files)
        assert "python" in result
        paths = [p for p, _ in result["python"]]
        assert "app.py" in paths
        assert "utils.py" in paths

    def test_excludes_unknown_files(self):
        files = {"app.py": "code", "README.zip": "binary"}
        result = LanguageUtils.group_files_by_language(files)
        assert "unknown" not in result

    def test_mixed_languages(self):
        files = {
            "server.py": "py",
            "client.js": "js",
            "types.ts": "ts",
        }
        result = LanguageUtils.group_files_by_language(files)
        assert "python" in result
        assert "javascript" in result
        assert "typescript" in result

    def test_empty_input(self):
        assert LanguageUtils.group_files_by_language({}) == {}

    def test_content_preserved_in_tuples(self):
        files = {"app.py": "my_content"}
        result = LanguageUtils.group_files_by_language(files)
        assert result["python"][0] == ("app.py", "my_content")


@pytest.mark.unit
class TestGetTestFilePath:
    def test_python(self):
        path = LanguageUtils.get_test_file_path("app.py", "python")
        assert path.endswith("test_app.py")
        assert "tests" in path

    def test_javascript(self):
        path = LanguageUtils.get_test_file_path("component.js", "javascript")
        assert path.endswith("component.test.js")

    def test_typescript(self):
        path = LanguageUtils.get_test_file_path("service.ts", "typescript")
        assert path.endswith("service.test.ts")

    def test_go(self):
        path = LanguageUtils.get_test_file_path("main.go", "go")
        assert path.endswith("main_test.go")

    def test_rust(self):
        path = LanguageUtils.get_test_file_path("lib.rs", "rust")
        assert path.endswith("lib.rs")

    def test_java(self):
        path = LanguageUtils.get_test_file_path("Main.java", "java")
        assert path.endswith("MainTest.java")

    def test_unknown_language_fallback(self):
        path = LanguageUtils.get_test_file_path("script.sh", "bash")
        assert "test_script" in path
