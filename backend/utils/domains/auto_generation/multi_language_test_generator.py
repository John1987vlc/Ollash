"""
Multi-Language Test Generator with Framework Support

Extended test generation that supports multiple languages:
- Python (pytest, unittest)
- JavaScript/TypeScript (Jest, Mocha)
- Go (go test)
- Rust (cargo test)
- Java (JUnit, Gradle)

Also handles integration test generation and docker-compose orchestration.
"""

import json
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.command_executor import CommandExecutor
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.llm.ollama_client import OllamaClient
from backend.utils.domains.auto_generation.prompt_templates import AutoGenPrompts


class TestFramework(Enum):
    """Supported test frameworks."""

    PYTEST = "pytest"  # Python
    UNITTEST = "unittest"  # Python
    JEST = "jest"  # JavaScript
    MOCHA = "mocha"  # JavaScript
    GO_TEST = "go test"  # Go
    CARGO = "cargo"  # Rust
    JUNIT = "junit"  # Java
    GRADLE = "gradle"  # Java


class LanguageFrameworkMap:
    """Maps file extensions/languages to test frameworks."""

    LANGUAGE_FRAMEWORKS = {
        "python": [TestFramework.PYTEST, TestFramework.UNITTEST],
        "javascript": [TestFramework.JEST, TestFramework.MOCHA],
        "typescript": [TestFramework.JEST, TestFramework.MOCHA],
        "go": [TestFramework.GO_TEST],
        "rust": [TestFramework.CARGO],
        "java": [TestFramework.JUNIT, TestFramework.GRADLE],
    }

    EXT_TO_LANGUAGE = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
    }

    @classmethod
    def detect_language(cls, file_path: str) -> str:
        """Detect language from file extension."""
        ext = Path(file_path).suffix.lower()
        return cls.EXT_TO_LANGUAGE.get(ext, "unknown")

    @classmethod
    def get_test_frameworks(cls, language: str) -> List[TestFramework]:
        """Get recommended test frameworks for language."""
        return cls.LANGUAGE_FRAMEWORKS.get(language.lower(), [])

    @classmethod
    def get_preferred_framework(cls, language: str) -> Optional[TestFramework]:
        """Get preferred (first) test framework for language."""
        frameworks = cls.get_test_frameworks(language)
        return frameworks[0] if frameworks else None


class MultiLanguageTestGenerator:
    """
    Generates and executes unit tests for multiple languages.

    Features:
    - Auto-detect language and select appropriate framework
    - Generate framework-specific test files
    - Execute tests with proper environment setup
    - Parse results in a unified format
    - Support integration test generation
    """

    DEFAULT_OPTIONS = {
        "num_ctx": 4096,
        "num_predict": 2048,
        "temperature": 0.7,
        "keep_alive": "0s",
    }

    def __init__(
        self,
        llm_client: OllamaClient,
        logger: AgentLogger,
        response_parser: LLMResponseParser,
        command_executor: CommandExecutor,
        options: dict = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.parser = response_parser
        self.command_executor = command_executor
        self.options = options or self.DEFAULT_OPTIONS.copy()

    def generate_tests(
        self,
        file_path: str,
        content: str,
        readme_context: str,
        framework: Optional[TestFramework] = None,
    ) -> Optional[str]:
        """
        Generate tests for a file in any supported language.

        Args:
            file_path: Path to source file
            content: Source code content
            readme_context: Project description
            framework: Specific framework to use (auto-detected if None)

        Returns:
            Generated test file content or None
        """
        language = LanguageFrameworkMap.detect_language(file_path)

        if framework is None:
            framework = LanguageFrameworkMap.get_preferred_framework(language)

        if not framework:
            self.logger.warning(f"No test framework available for {language}")
            return None

        self.logger.info(f"Generating {framework.value} tests for {file_path} ({language})...")

        # Get language-specific prompts
        system_prompt, user_prompt = self._get_test_prompts(file_path, content, readme_context, language, framework)

        try:
            response_data, usage = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=[],
                options_override=self.options,
            )
            raw_response = response_data["message"]["content"]
            test_content = self.parser.extract_raw_content(raw_response)

            if test_content:
                self.logger.info(f"Tests generated for {file_path} using {framework.value}")
                return test_content
            else:
                self.logger.warning(f"LLM returned no test content for {file_path}")
                return None

        except Exception as e:
            self.logger.error(f"Error generating tests for {file_path}: {e}")
            return None

    def generate_integration_tests(
        self,
        project_root: Path,
        readme_context: str,
        services: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate integration tests and docker-compose orchestration.

        Args:
            project_root: Root directory of project
            readme_context: Project description
            services: List of services with names and ports

        Returns:
            (integration_test_content, docker_compose_test_content)
        """
        self.logger.info("Generating integration tests...")

        # Scan project to find services and APIs
        services = services or self._detect_services(project_root, readme_context)

        system_prompt = """You are an expert test architect.
Create comprehensive integration tests that validate service interactions."""

        user_prompt = f"""Create integration tests for this project:

Project: {readme_context[:500]}
Services: {json.dumps(services, indent=2)}

Include:
1. End-to-end API tests
2. Service interaction tests
3. Error handling and edge cases
4. Load scenarios

Format as a single test file with clear organization."""

        try:
            response_data, _ = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=[],
                options_override=self.options,
            )

            test_content = self.parser.extract_raw_content(response_data["message"]["content"])

            # Generate docker-compose for test orchestration
            docker_compose = self._generate_test_docker_compose(services)

            return (test_content, docker_compose)

        except Exception as e:
            self.logger.error(f"Error generating integration tests: {e}")
            return (None, None)

    def execute_tests(
        self,
        project_root: Path,
        test_file_paths: List[Path],
        language: Optional[str] = None,
        framework: Optional[TestFramework] = None,
    ) -> Dict[str, Any]:
        """
        Execute tests for any language/framework.

        Returns standardized result format.
        """
        if not test_file_paths:
            return {"success": True, "output": "No test files", "failures": []}

        # Detect language from test files
        if language is None and test_file_paths:
            language = LanguageFrameworkMap.detect_language(str(test_file_paths[0]))

        if framework is None:
            framework = LanguageFrameworkMap.get_preferred_framework(language)

        if not framework:
            return {
                "success": False,
                "output": f"No test framework for {language}",
                "failures": [],
            }

        self.logger.info(f"Executing {framework.value} tests...")

        # Framework-specific execution
        if framework == TestFramework.PYTEST:
            return self._execute_pytest(project_root, test_file_paths)
        elif framework in (TestFramework.JEST, TestFramework.MOCHA):
            return self._execute_nodejs_tests(project_root, test_file_paths, framework)
        elif framework == TestFramework.GO_TEST:
            return self._execute_go_tests(project_root)
        elif framework == TestFramework.CARGO:
            return self._execute_rust_tests(project_root)
        elif framework == TestFramework.JUNIT:
            return self._execute_java_tests(project_root, framework)
        else:
            return {
                "success": False,
                "output": f"Unsupported framework: {framework.value}",
                "failures": [],
            }

    def _execute_pytest(self, project_root: Path, test_file_paths: List[Path]) -> Dict[str, Any]:
        """Execute pytest tests."""
        try:
            cmd = [
                "pytest",
                "--json-report",
                "--json-report-file=.pytest_report.json",
                "-v",
            ] + [str(p.relative_to(project_root)) for p in test_file_paths]

            result = self.command_executor.execute(cmd, dir_path=str(project_root), timeout=120)

            failures = self._parse_pytest_failures(project_root)

            return {
                "success": result.success,
                "output": result.stdout or result.stderr,
                "failures": failures,
                "framework": "pytest",
            }

        except Exception as e:
            self.logger.error(f"Error executing pytest: {e}")
            return {
                "success": False,
                "output": str(e),
                "failures": [],
                "framework": "pytest",
            }

    def _execute_nodejs_tests(
        self, project_root: Path, test_file_paths: List[Path], framework: TestFramework
    ) -> Dict[str, Any]:
        """Execute Jest or Mocha tests."""
        import shutil
        if not shutil.which("npm"):
            self.logger.warning("  npm command not found. Skipping Node.js test execution.")
            return {
                "success": True, # Skip with success to not block generation
                "output": "npm not found in environment. Skipping tests.",
                "failures": [],
                "framework": framework.value,
                "skipped": True
            }

        try:
            if framework == TestFramework.JEST:
                cmd = ["npm", "test", "--", "--json"]  # Jest JSON output
            else:  # MOCHA
                cmd = ["npm", "test"]

            result = self.command_executor.execute(cmd, dir_path=str(project_root), timeout=120)

            failures = self._parse_nodejs_failures(result.stdout or result.stderr)

            return {
                "success": result.success,
                "output": result.stdout or result.stderr,
                "failures": failures,
                "framework": framework.value,
            }

        except Exception as e:
            self.logger.error(f"Error executing {framework.value}: {e}")
            return {
                "success": False,
                "output": str(e),
                "failures": [],
                "framework": framework.value,
            }

    def _execute_go_tests(self, project_root: Path) -> Dict[str, Any]:
        """Execute Go tests."""
        try:
            cmd = ["go", "test", "-v", "./..."]
            result = self.command_executor.execute(cmd, dir_path=str(project_root), timeout=120)

            failures = self._parse_go_failures(result.stdout or result.stderr)

            return {
                "success": result.success,
                "output": result.stdout or result.stderr,
                "failures": failures,
                "framework": "go test",
            }

        except Exception as e:
            self.logger.error(f"Error executing go test: {e}")
            return {
                "success": False,
                "output": str(e),
                "failures": [],
                "framework": "go test",
            }

    def _execute_rust_tests(self, project_root: Path) -> Dict[str, Any]:
        """Execute Cargo tests."""
        try:
            cmd = ["cargo", "test", "--", "--nocapture"]
            result = self.command_executor.execute(cmd, dir_path=str(project_root), timeout=180)

            failures = self._parse_rust_failures(result.stdout or result.stderr)

            return {
                "success": result.success,
                "output": result.stdout or result.stderr,
                "failures": failures,
                "framework": "cargo",
            }

        except Exception as e:
            self.logger.error(f"Error executing cargo test: {e}")
            return {
                "success": False,
                "output": str(e),
                "failures": [],
                "framework": "cargo",
            }

    def _execute_java_tests(self, project_root: Path, framework: TestFramework) -> Dict[str, Any]:
        """Execute Java tests (JUnit or Gradle)."""
        try:
            if framework == TestFramework.GRADLE:
                cmd = ["gradle", "test"]
            else:  # JUNIT
                cmd = ["mvn", "test"]

            result = self.command_executor.execute(cmd, dir_path=str(project_root), timeout=180)

            failures = self._parse_java_failures(result.stdout or result.stderr)

            return {
                "success": result.success,
                "output": result.stdout or result.stderr,
                "failures": failures,
                "framework": framework.value,
            }

        except Exception as e:
            self.logger.error(f"Error executing Java tests: {e}")
            return {
                "success": False,
                "output": str(e),
                "failures": [],
                "framework": framework.value,
            }

    def _get_test_prompts(
        self,
        file_path: str,
        content: str,
        readme: str,
        language: str,
        framework: TestFramework,
    ) -> Tuple[str, str]:
        """Get language and framework specific test prompts."""
        framework_templates = {
            TestFramework.PYTEST: self._pytest_prompt,
            TestFramework.UNITTEST: self._unittest_prompt,
            TestFramework.JEST: self._jest_prompt,
            TestFramework.MOCHA: self._mocha_prompt,
            TestFramework.GO_TEST: self._go_test_prompt,
            TestFramework.CARGO: self._cargo_test_prompt,
            TestFramework.JUNIT: self._junit_prompt,
        }

        template_fn = framework_templates.get(framework)
        if template_fn:
            return template_fn(file_path, content, readme)
        else:
            # Fallback to generic
            return AutoGenPrompts.generate_unit_tests(file_path, content, readme)

    def _pytest_prompt(self, file_path: str, content: str, readme: str) -> Tuple[str, str]:
        """Generate pytest-specific prompt."""
        system = """You are an expert Python test engineer using pytest.
Create comprehensive pytest unit tests with fixtures, mocking, and edge cases."""

        user = f"""File: {file_path}
Code:
```python
{content}
```

Project: {readme[:300]}

Generate pytest tests with:
1. Test class organization
2. Setup/teardown fixtures
3. Mocking where appropriate
4. Edge cases and error scenarios"""

        return system, user

    def _jest_prompt(self, file_path: str, content: str, readme: str) -> Tuple[str, str]:
        """Generate Jest-specific prompt."""
        system = """You are an expert JavaScript test engineer using Jest.
Create comprehensive Jest unit tests with describe blocks and mocking."""

        user = f"""File: {file_path}
Code:
```javascript
{content}
```

Project: {readme[:300]}

Generate Jest tests with:
1. describe blocks for organization
2. beforeEach/afterEach hooks
3. Mock functions using jest.fn()
4. Edge cases and error scenarios"""

        return system, user

    def _go_test_prompt(self, file_path: str, content: str, readme: str) -> Tuple[str, str]:
        """Generate Go test-specific prompt."""
        system = """You are an expert Go test engineer.
Create comprehensive Go tests using the testing package."""

        user = f"""File: {file_path}
Code:
```go
{content}
```

Project: {readme[:300]}

Generate Go tests with:
1. Table-driven tests
2. Test helpers and setup
3. Error cases
4. Benchmark tests where appropriate"""

        return system, user

    def _mocha_prompt(self, file_path: str, content: str, readme: str) -> Tuple[str, str]:
        """Generate Mocha-specific prompt."""
        system = """You are an expert JavaScript test engineer using Mocha.
Create comprehensive Mocha tests with assertions."""

        user = f"""File: {file_path}
Code:
```javascript
{content}
```

Project: {readme[:300]}

Generate Mocha tests with:
1. describe and it blocks
2. before/beforeEach hooks
3. Assert statements
4. Edge cases"""

        return system, user

    def _cargo_test_prompt(self, file_path: str, content: str, readme: str) -> Tuple[str, str]:
        """Generate Rust/Cargo test prompt."""
        system = """You are an expert Rust test engineer.
Create comprehensive Cargo tests using #[cfg(test)]."""

        user = f"""File: {file_path}
Code:
```rust
{content}
```

Project: {readme[:300]}

Generate Cargo tests with:
1. #[test] attributes
2. Test organization
3. Error cases
4. Integration tests where appropriate"""

        return system, user

    def _unittest_prompt(self, file_path: str, content: str, readme: str) -> Tuple[str, str]:
        """Generate unittest-specific prompt."""
        system = """You are an expert Python test engineer using unittest.
Create comprehensive unittest tests with setUp/tearDown."""

        user = f"""File: {file_path}
Code:
```python
{content}
```

Project: {readme[:300]}

Generate unittest tests with:
1. TestCase class organization
2. setUp/tearDown methods
3. Mock objects where appropriate
4. Edge cases"""

        return system, user

    def _junit_prompt(self, file_path: str, content: str, readme: str) -> Tuple[str, str]:
        """Generate JUnit-specific prompt."""
        system = """You are an expert Java test engineer using JUnit.
Create comprehensive JUnit tests with annotations."""

        user = f"""File: {file_path}
Code:
```java
{content}
```

Project: {readme[:300]}

Generate JUnit tests with:
1. @Test annotations
2. @Before/@After setup
3. Assertions
4. Test organization"""

        return system, user

    def _detect_services(self, project_root: Path, readme: str) -> List[Dict[str, str]]:
        """Scan project to detect services."""
        services = []

        # Look for common service patterns
        for file_path in project_root.rglob("*"):
            if file_path.is_file():
                name = file_path.stem.lower()
                if any(x in name for x in ["server", "service", "api", "app"]):
                    services.append(
                        {
                            "name": name,
                            "path": str(file_path.relative_to(project_root)),
                            "port": 8000 + len(services),
                        }
                    )

        return services

    def _generate_test_docker_compose(self, services: List[Dict]) -> str:
        """Generate docker-compose.test.yml for test orchestration."""
        compose = {
            "version": "3.8",
            "services": {},
            "networks": {"test-network": {"driver": "bridge"}},
        }

        for service in services:
            compose["services"][service.get("name", "service")] = {
                "build": ".",
                "ports": [f"{service.get('port', 8000)}:8000"],
                "networks": ["test-network"],
                "environment": {"TEST_MODE": "true"},
            }

        return json.dumps(compose, indent=2)

    def _parse_pytest_failures(self, project_root: Path) -> List[Dict]:
        """Parse pytest failures from JSON report."""
        try:
            report_path = project_root / ".pytest_report.json"
            if report_path.exists():
                with open(report_path) as f:
                    report = json.load(f)

                failures = []
                for test in report.get("tests", []):
                    if test["outcome"] == "failed":
                        failures.append(
                            {
                                "name": test["nodeid"],
                                "message": test.get("call", {}).get("longrepr", ""),
                                "path": test["nodeid"].split("::")[0],
                            }
                        )
                return failures
        except Exception as e:
            self.logger.error(f"Error parsing pytest failures: {e}")
        return []

    def _parse_nodejs_failures(self, output: str) -> List[Dict]:
        """Parse Node.js test output for failures."""
        failures = []
        # Simple regex-based parsing
        for match in re.finditer(r"(\d+\) (.+))", output):
            failures.append({"message": match.group(2)})
        return failures

    def _parse_go_failures(self, output: str) -> List[Dict]:
        """Parse Go test output for failures."""
        failures = []
        for match in re.finditer(r"--- FAIL: (\w+)", output):
            failures.append({"name": match.group(1)})
        return failures

    def _parse_rust_failures(self, output: str) -> List[Dict]:
        """Parse Rust test output for failures."""
        failures = []
        for match in re.finditer(r"test .+ FAILED", output):
            failures.append({"message": match.group(0)})
        return failures

    def _parse_java_failures(self, output: str) -> List[Dict]:
        """Parse Java test output for failures."""
        failures = []
        for match in re.finditer(r"FAILURE.+", output):
            failures.append({"message": match.group(0)})
        return failures
