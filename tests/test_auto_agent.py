"""Tests for AutoAgent pipeline phases."""
import json

from src.utils.core.llm_response_parser import LLMResponseParser
from src.utils.core.file_validator import FileValidator


class TestAutoAgentInitialization:
    """Tests for AutoAgent initialization and configuration."""

    def test_init_creates_llm_clients(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "settings.json").write_text(json.dumps({
            "ollama_url": "http://localhost:11434",
            "auto_agent_llms": {
                "prototyper_model": "test-proto",
                "coder_model": "test-coder",
                "planner_model": "test-planner",
                "generalist_model": "test-gen",
                "suggester_model": "test-sug",
                "improvement_planner_model": "test-imp",
                "senior_reviewer_model": "test-sr"
            },
            "auto_agent_timeouts": {}
        }))

        from src.agents.auto_agent import AutoAgent
        agent = AutoAgent(config_path=str(config_dir / "settings.json"))
        assert len(agent.llm_clients) == 10
        assert "prototyper" in agent.llm_clients
        assert "coder" in agent.llm_clients
        assert "planner" in agent.llm_clients

    def test_init_uses_env_var_url(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OLLASH_OLLAMA_URL", "http://custom:11434")
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "settings.json").write_text(json.dumps({
            "ollama_url": "http://default:11434",
            "auto_agent_llms": {},
            "auto_agent_timeouts": {}
        }))

        from src.agents.auto_agent import AutoAgent
        agent = AutoAgent(config_path=str(config_dir / "settings.json"))
        assert agent.url == "http://custom:11434"


class TestLLMResponseParserIntegration:
    """Tests for LLM response parsing used by AutoAgent phases."""

    def test_extract_raw_content_strips_markdown(self):
        response = "```python\nprint('hello')\n```"
        result = LLMResponseParser.extract_raw_content(response)
        assert result == "print('hello')"

    def test_extract_json_from_llm_response(self):
        response = 'Here is the structure:\n```json\n{"files": ["main.py"], "folders": ["src"]}\n```'
        result = LLMResponseParser.extract_json(response)
        assert result is not None
        assert "files" in result
        assert "main.py" in result["files"]

    def test_extract_multiple_files(self):
        response = (
            "# filename: app.py\n"
            "```python\n"
            "from flask import Flask\napp = Flask(__name__)\n"
            "```\n"
            "# filename: requirements.txt\n"
            "```\n"
            "flask>=2.0\n"
            "```"
        )
        files = LLMResponseParser.extract_multiple_files(response)
        assert "app.py" in files
        assert "requirements.txt" in files
        assert "Flask" in files["app.py"]


class TestFileValidatorIntegration:
    """Tests for file validation used in AutoAgent Phase 5.5."""

    def setup_method(self):
        self.validator = FileValidator()

    def test_validate_valid_python(self):
        code = "def main():\n    print('hello')\n\nmain()"
        result = self.validator.validate("main.py", code)
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.VALID

    def test_validate_invalid_python(self):
        code = "def main(\n    print 'hello'\n    return None"
        result = self.validator.validate("bad.py", code)
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.SYNTAX_ERROR

    def test_validate_valid_json(self):
        result = self.validator.validate("config.json", '{"port": 3000}')
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.VALID

    def test_validate_empty_file(self):
        result = self.validator.validate("empty.py", "")
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.EMPTY

    def test_batch_validation(self):
        files = {
            "main.py": "x = 1\ny = 2\nz = 3",
            "config.json": '{"key": "value"}',
            "readme.md": "# Hello\nWorld"
        }
        results = self.validator.validate_batch(files)
        assert len(results) == 3


class TestDependencyFileValidation:
    """Tests for dependency file validation (requirements.txt, package.json)."""

    def setup_method(self):
        self.validator = FileValidator()

    def test_valid_requirements_txt(self):
        content = "Flask==3.0.0\nFlask-SQLAlchemy==3.0.5\nFlask-CORS==4.0.0\n"
        result = self.validator.validate("requirements.txt", content)
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.VALID
        assert "3 packages" in result.message

    def test_excessive_requirements_txt(self):
        # Simulate hallucinated deps (>30 entries)
        lines = [f"fake-package-{i}==1.0.0" for i in range(50)]
        content = "\n".join(lines) + "\n"
        result = self.validator.validate("requirements.txt", content)
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.SYNTAX_ERROR
        assert "Excessive dependencies" in result.message

    def test_invalid_package_name_in_requirements(self):
        content = "Flask==3.0.0\nthis is not a valid package name==1.0\nrequests==2.0.0\n"
        result = self.validator.validate("requirements.txt", content)
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.SYNTAX_ERROR
        assert "Invalid package names" in result.message

    def test_duplicate_packages_in_requirements(self):
        content = "Flask==3.0.0\nrequests==2.0.0\nflask==2.0.0\n"
        result = self.validator.validate("requirements.txt", content)
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.SYNTAX_ERROR
        assert "Duplicate packages" in result.message

    def test_requirements_ignores_comments_and_flags(self):
        content = "# My project deps\n-r base.txt\nFlask==3.0.0\nrequests>=2.0\n"
        result = self.validator.validate("requirements.txt", content)
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.VALID

    def test_valid_package_json(self):
        content = json.dumps({
            "name": "my-app",
            "dependencies": {"express": "^4.18.0", "cors": "^2.8.5"},
            "devDependencies": {"jest": "^29.0.0"}
        })
        result = self.validator.validate("package.json", content)
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.VALID

    def test_excessive_package_json_deps(self):
        deps = {f"fake-pkg-{i}": "^1.0.0" for i in range(40)}
        content = json.dumps({"name": "bloated", "dependencies": deps})
        result = self.validator.validate("package.json", content)
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.SYNTAX_ERROR
        assert "Excessive dependencies" in result.message

    def test_long_package_name_rejected(self):
        long_name = "a" * 100
        content = f"{long_name}==1.0.0\n"
        result = self.validator.validate("requirements.txt", content)
        from src.utils.core.file_validator import ValidationStatus
        assert result.status == ValidationStatus.SYNTAX_ERROR


class TestAutoAgentSaveFile:
    """Tests for the static _save_file helper."""

    def test_save_file_creates_parents(self, tmp_path):
        from src.agents.auto_agent import AutoAgent
        target = tmp_path / "deep" / "nested" / "file.txt"
        AutoAgent._save_file(target, "  hello world  ")
        assert target.exists()
        assert target.read_text() == "hello world"

    def test_save_file_overwrites(self, tmp_path):
        from src.agents.auto_agent import AutoAgent
        target = tmp_path / "file.txt"
        target.write_text("old")
        AutoAgent._save_file(target, "new content")
        assert target.read_text() == "new content"
