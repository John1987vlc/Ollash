import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.command_executor import CommandExecutor
from backend.utils.core.llm_response_parser import LLMResponseParser
from backend.utils.core.ollama_client import OllamaClient
from backend.utils.domains.auto_generation.prompt_templates import \
    AutoGenPrompts


class TestGenerator:
    """
    Generates unit tests (using pytest) for new code and executes them.
    Handles parsing test results and reporting failures.
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
        self, file_path: str, content: str, readme_context: str
    ) -> Optional[str]:
        """
        Generates pytest unit tests for a given file content.
        Returns the generated test file content or None if generation fails.
        """
        self.logger.info(f"  Generating tests for {file_path}...")

        system_prompt, user_prompt = AutoGenPrompts.generate_unit_tests(
            file_path, content, readme_context
        )

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
                self.logger.info(f"  Tests generated for {file_path}.")
                return test_content
            else:
                self.logger.warning(
                    f"  LLM did not return test content for {file_path}."
                )
                return None
        except Exception as e:
            self.logger.error(f"  Error generating tests for {file_path}: {e}")
            return None

    def execute_tests(
        self, project_root: Path, test_file_paths: List[Path]
    ) -> Dict[str, Any]:
        """
        Executes pytest tests and returns a structured result.
        Returns a dict with 'success' (bool) and 'output' (str) and 'failures' (list of dicts).
        """
        self.logger.info(
            f"  Executing tests in {project_root} for {len(test_file_paths)} files..."
        )

        if not test_file_paths:
            self.logger.info("  No test files to execute.")
            return {"success": True, "output": "No test files.", "failures": []}

        # Construct the pytest command
        # Use --json-report to get structured output
        # Use -x to stop on first failure for quicker feedback
        # Use -s to show stdout from print statements
        # Explicitly pass test file paths
        pytest_command = [
            "pytest",
            "--json-report",
            "--json-report-file=.pytest_report.json",
            "-s",
        ] + [str(p.relative_to(project_root)) for p in test_file_paths]

        try:
            # Execute pytest from the project_root
            result = self.command_executor.execute(
                pytest_command, dir_path=str(project_root), timeout=120
            )

            report_path = project_root / ".pytest_report.json"
            if report_path.exists():
                with open(report_path, "r", encoding="utf-8") as f:
                    report_data = json.load(f)
                report_path.unlink()  # Clean up the report file
            else:
                report_data = None
                self.logger.warning("  Pytest JSON report not found after execution.")

            if result.success:
                self.logger.info(
                    f"  Tests executed successfully for {len(test_file_paths)} files."
                )
                return {
                    "success": True,
                    "output": result.stdout,
                    "failures": self._parse_json_report_failures(report_data),
                }
            else:
                self.logger.warning(f"  Tests failed for {len(test_file_paths)} files.")
                return {
                    "success": False,
                    "output": result.stderr or result.stdout,
                    "failures": self._parse_json_report_failures(report_data),
                }

        except Exception as e:
            self.logger.error(f"  Error executing tests: {e}")
            return {"success": False, "output": str(e), "failures": []}

    def _parse_json_report_failures(
        self, report_data: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Parses the pytest JSON report to extract failure details."""
        failures = []
        if not report_data or "tests" not in report_data:
            return failures

        for test_item in report_data["tests"]:
            if test_item["outcome"] == "failed":
                details = {
                    "nodeid": test_item["nodeid"],
                    "path": test_item["call"]["longrepr"].get("path"),
                    "lineno": test_item["call"]["longrepr"].get("lineno"),
                    "message": test_item["call"]["longrepr"].get("message"),
                    "traceback": test_item["call"]["longrepr"].get("traceback"),
                }
                failures.append(details)
        return failures
