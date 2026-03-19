"""Unit tests for TechStackDetector (E2)."""

import pytest

from backend.utils.domains.auto_generation.utilities.tech_stack_detector import TechStackDetector


@pytest.mark.unit
class TestTechStackDetector:
    """Tests for TechStackDetector.detect()."""

    def test_detect_flask_from_requirements_txt(self):
        files = {"requirements.txt": "flask==2.3.0\nrequests>=2.28\npytest==7.4.0\n"}
        info = TechStackDetector().detect(files)

        assert info.framework == "Flask"
        assert info.framework_version == "2.3.0"
        assert info.primary_language == "python"

    def test_detect_fastapi_from_requirements_txt(self):
        files = {"requirements.txt": "fastapi>=0.100.0\nuvicorn[standard]\npydantic>=2.0\n"}
        info = TechStackDetector().detect(files)

        assert info.framework == "FastAPI"
        assert info.primary_language == "python"

    def test_detect_react_from_package_json(self):
        import json

        pkg = json.dumps({"dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"}})
        info = TechStackDetector().detect({"package.json": pkg})

        assert info.framework == "React"
        assert info.primary_language == "javascript"

    def test_detect_nextjs_from_package_json(self):
        import json

        pkg = json.dumps({"dependencies": {"next": "14.0.0", "react": "^18.0.0"}})
        info = TechStackDetector().detect({"package.json": pkg})

        # next has higher priority than react
        assert info.framework == "Next.js"

    def test_detect_pytest_test_framework(self):
        files = {"requirements.txt": "flask==2.3.0\npytest==7.4.0\n"}
        info = TechStackDetector().detect(files)

        assert info.test_framework == "pytest"

    def test_unknown_stack_on_empty_files(self):
        info = TechStackDetector().detect({})

        assert info.framework == "unknown"
        assert info.primary_language == "unknown"
        assert info.prompt_hints == []

    def test_unknown_stack_on_unrecognised_files(self):
        info = TechStackDetector().detect({"README.md": "# Hello World"})

        assert info.framework == "unknown"

    def test_prompt_hints_not_empty_for_flask(self):
        files = {"requirements.txt": "flask==2.3.0\npytest==7.4.0\n"}
        info = TechStackDetector().detect(files)

        assert len(info.prompt_hints) > 0
        assert any("Flask" in h for h in info.prompt_hints)

    def test_prompt_hints_include_test_framework(self):
        files = {"requirements.txt": "flask==2.3.0\npytest==7.4.0\n"}
        info = TechStackDetector().detect(files)

        assert any("pytest" in h.lower() for h in info.prompt_hints)

    def test_to_dict_contains_expected_keys(self):
        files = {"requirements.txt": "flask==2.3.0\n"}
        info = TechStackDetector().detect(files)
        d = info.to_dict()

        assert "primary_language" in d
        assert "framework" in d
        assert "prompt_hints" in d

    def test_detect_poetry_build_tool(self):
        pyproject = """
[tool.poetry]
name = "myapp"

[tool.poetry.dependencies]
python = "^3.11"
flask = "^2.3.0"
"""
        info = TechStackDetector().detect({"pyproject.toml": pyproject})

        assert info.primary_language == "python"

    def test_detect_go_project(self):
        go_mod = "module github.com/user/myapp\n\ngo 1.21\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.0\n)\n"
        info = TechStackDetector().detect({"go.mod": go_mod})

        assert info.primary_language == "go"

    def test_key_dependencies_populated(self):
        files = {"requirements.txt": "flask==2.3.0\nrequests>=2.28\nsqlalchemy==2.0\n"}
        info = TechStackDetector().detect(files)

        assert "flask" in info.key_dependencies
        assert info.key_dependencies["flask"] == "2.3.0"
