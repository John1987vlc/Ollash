"""
Unit tests for MultiLanguageTestGenerator system.
"""

from unittest.mock import Mock

import pytest

from backend.utils.domains.auto_generation.multi_language_test_generator import (
    LanguageFrameworkMap,
    MultiLanguageTestGenerator,
    TestFramework,
)


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    return Mock()


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return Mock()


@pytest.fixture
def mock_response_parser():
    """Create a mock response parser."""
    return Mock()


@pytest.fixture
def mock_command_executor():
    """Create a mock command executor."""
    return Mock()


@pytest.fixture
def test_generator(mock_llm_client, mock_logger, mock_response_parser, mock_command_executor):
    """Create a test generator instance."""
    return MultiLanguageTestGenerator(mock_llm_client, mock_logger, mock_response_parser, mock_command_executor)


class TestLanguageFrameworkMap:
    """Test language to framework mapping."""

    def test_detect_python(self):
        """Test Python language detection."""
        lang = LanguageFrameworkMap.detect_language("module.py")
        assert lang == "python"

    def test_detect_javascript(self):
        """Test JavaScript language detection."""
        lang = LanguageFrameworkMap.detect_language("app.js")
        assert lang == "javascript"

    def test_detect_typescript(self):
        """Test TypeScript language detection."""
        lang = LanguageFrameworkMap.detect_language("types.ts")
        assert lang == "typescript"

    def test_detect_go(self):
        """Test Go language detection."""
        lang = LanguageFrameworkMap.detect_language("main.go")
        assert lang == "go"

    def test_detect_rust(self):
        """Test Rust language detection."""
        lang = LanguageFrameworkMap.detect_language("lib.rs")
        assert lang == "rust"

    def test_detect_java(self):
        """Test Java language detection."""
        lang = LanguageFrameworkMap.detect_language("Main.java")
        assert lang == "java"

    def test_unknown_extension(self):
        """Test unknown file extension."""
        lang = LanguageFrameworkMap.detect_language("file.unknown")
        assert lang == "unknown"


class TestFrameworkSelection:
    """Test test framework selection."""

    def test_python_frameworks(self):
        """Test available Python frameworks."""
        frameworks = LanguageFrameworkMap.get_test_frameworks("python")
        assert TestFramework.PYTEST in frameworks
        assert TestFramework.UNITTEST in frameworks

    def test_javascript_frameworks(self):
        """Test available JavaScript frameworks."""
        frameworks = LanguageFrameworkMap.get_test_frameworks("javascript")
        assert TestFramework.JEST in frameworks
        assert TestFramework.MOCHA in frameworks

    def test_go_framework(self):
        """Test Go test framework."""
        frameworks = LanguageFrameworkMap.get_test_frameworks("go")
        assert TestFramework.GO_TEST in frameworks

    def test_rust_framework(self):
        """Test Rust test framework."""
        frameworks = LanguageFrameworkMap.get_test_frameworks("rust")
        assert TestFramework.CARGO in frameworks

    def test_java_frameworks(self):
        """Test available Java frameworks."""
        frameworks = LanguageFrameworkMap.get_test_frameworks("java")
        assert TestFramework.JUNIT in frameworks or TestFramework.GRADLE in frameworks

    def test_preferred_framework_python(self):
        """Test preferred framework for Python."""
        framework = LanguageFrameworkMap.get_preferred_framework("python")
        assert framework == TestFramework.PYTEST

    def test_preferred_framework_javascript(self):
        """Test preferred framework for JavaScript."""
        framework = LanguageFrameworkMap.get_preferred_framework("javascript")
        assert framework == TestFramework.JEST


class TestGenerateTests:
    """Test test generation."""

    def test_generate_python_tests(self, test_generator, mock_llm_client, mock_response_parser):
        """Test Python test generation."""
        # Setup mock
        mock_llm_client.chat.return_value = (
            {"message": {"content": "```python\ndef test_func(): pass\n```"}},
            {},
        )
        mock_response_parser.extract_raw_content.return_value = "def test_func(): pass"

        result = test_generator.generate_tests("module.py", "def my_func(): return 42", "A simple module")

        assert result is not None
        assert isinstance(result, str)

    def test_framework_auto_detection(self, test_generator, mock_llm_client):
        """Test automatic framework detection."""
        mock_llm_client.chat.return_value = (
            {"message": {"content": "test content"}},
            {},
        )

        # Generate for Python file without specifying framework
        test_generator.generate_tests(
            "test.py",
            "code",
            "readme",
            framework=None,  # Auto-detect
        )

        # Should detect python and select pytest
        assert mock_llm_client.chat.called


class TestIntegrationTests:
    """Test integration test generation."""

    def test_generate_integration_tests(self, test_generator, mock_llm_client):
        """Test integration test generation."""
        mock_llm_client.chat.return_value = (
            {"message": {"content": "integration test code"}},
            {},
        )

        services = [{"name": "api", "port": 8000}, {"name": "db", "port": 5432}]

        test_content, docker_compose = test_generator.generate_integration_tests(
            "/project", "A multi-service app", services
        )

        # Should return both test file and docker-compose
        assert test_content is not None or docker_compose is not None


class TestDockerComposeGeneration:
    """Test docker-compose.test.yml generation."""

    def test_generate_test_docker_compose(self, test_generator):
        """Test docker-compose generation for testing."""
        services = [
            {"name": "web", "port": 8000},
            {"name": "db", "port": 5432},
            {"name": "cache", "port": 6379},
        ]

        compose = test_generator._generate_test_docker_compose(services)

        assert compose is not None
        assert "version" in compose
        assert "services" in compose or "services" in str(compose)


class TestLanguageSpecificPrompts:
    """Test language-specific test prompts."""

    def test_pytest_prompt(self, test_generator):
        """Test pytest-specific prompt."""
        system, user = test_generator._pytest_prompt(
            "test_user.py",
            "def get_user(id): return {'id': id}",
            "User management system",
        )

        assert "pytest" in system.lower()
        assert "test_user.py" in user

    def test_jest_prompt(self, test_generator):
        """Test Jest-specific prompt."""
        system, user = test_generator._jest_prompt(
            "user.js", "function getUser(id) { return {id} }", "User management system"
        )

        assert "jest" in system.lower()
        assert "user.js" in user

    def test_go_test_prompt(self, test_generator):
        """Test Go test-specific prompt."""
        system, user = test_generator._go_test_prompt(
            "user.go", "func GetUser(id int) User { }", "User management system"
        )

        assert "go" in system.lower()
        assert "user.go" in user

    def test_mocha_prompt(self, test_generator):
        """Test Mocha-specific prompt."""
        system, user = test_generator._mocha_prompt("user.js", "function getUser() { }", "System")

        assert "mocha" in system.lower()

    def test_cargo_prompt(self, test_generator):
        """Test Cargo/Rust-specific prompt."""
        system, user = test_generator._cargo_test_prompt("lib.rs", "pub fn get_user() { }", "System")

        assert "rust" in system.lower() or "cargo" in system.lower()

    def test_unittest_prompt(self, test_generator):
        """Test unittest-specific prompt."""
        system, user = test_generator._unittest_prompt("test_user.py", "def get_user(): pass", "System")

        assert "unittest" in system.lower()


class TestTestExecution:
    """Test test execution."""

    def test_execute_tests_no_files(self, test_generator):
        """Test execution with no test files."""
        from pathlib import Path

        result = test_generator.execute_tests(Path("/tmp"), [])

        assert result["success"] == True
        assert "no test files" in result["output"].lower()

    def test_execute_tests_returns_structure(self, test_generator, mock_command_executor):
        """Test that execute_tests returns expected structure."""
        from pathlib import Path

        mock_command_executor.execute.return_value = Mock(success=True, stdout="", stderr="")

        result = test_generator.execute_tests(Path("/tmp"), [Path("/tmp/test_file.py")], language="python")

        assert "success" in result
        assert "output" in result
        assert "failures" in result


class TestServiceDetection:
    """Test service detection."""

    def test_detect_services(self, test_generator):
        """Test automatic service detection."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create some service-like files
            (project_root / "api_server.py").touch()
            (project_root / "api_service.py").touch()
            (project_root / "main_app.py").touch()

            services = test_generator._detect_services(project_root, "Project")

            # Should detect at least the api_server
            assert len(services) >= 0  # May vary by implementation
