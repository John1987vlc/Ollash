from typing import Optional
import re
from backend.utils.core.validators.base_validator import BaseValidator, ValidationResult, ValidationStatus


class PythonValidator(BaseValidator):
    """Validator for Python files, integrating pylint and flake8."""

    def __init__(self, logger=None, command_executor=None):
        super().__init__(logger, command_executor)

    def validate(self, file_path: str, content: str, lines: int, chars: int, ext: str) -> ValidationResult:
        """
        Validates Python file content using external linters (pylint, flake8) and basic syntax check.
        """
        # Fallback to basic syntax check if no command executor is available
        if not self.command_executor:
            return self._validate_python_syntax_only(file_path, content, lines, chars)

        # Try pylint first
        pylint_cmd = ["pylint", "--disable=all", "--enable=F,E", "--output-format=text"]
        # Example pylint error: file.py:10:0: E0001: some-error-message (some-checker)
        pylint_error_pattern = re.compile(r'^(.*?):(\d+):(\d+): ([FE]\d{4}):(.*)$')
        pylint_result = self._run_linter_command(
            file_path, content, pylint_cmd, "pylint OK", lines, chars,
            error_pattern=pylint_error_pattern, line_col_group_indices=(2, 3)
        )

        if pylint_result.status == ValidationStatus.VALID:
            # If pylint passes, also run flake8 for additional checks focused on syntax errors
            flake8_cmd = ["flake8", "--isolated", "--select=E9,F63,F7,F82", "--max-line-length=120"] # Focus on syntax errors
            # Example flake8 error: file.py:10:5: E901 some-error-message
            flake8_error_pattern = re.compile(r'^(.*?):(\d+):(\d+): (E\d{3}|F\d{3}) (.*)$')
            flake8_result = self._run_linter_command(
                file_path, content, flake8_cmd, "flake8 OK", lines, chars,
                error_pattern=flake8_error_pattern, line_col_group_indices=(2, 3)
            )
            if flake8_result.status == ValidationStatus.VALID:
                return ValidationResult(file_path, ValidationStatus.VALID, "Python syntax and basic linting OK", lines, chars)
            else:
                return flake8_result
        elif pylint_result.status == ValidationStatus.SYNTAX_ERROR:
            # If pylint found errors, return them directly
            return pylint_result
        
        # If pylint failed for other reasons (e.g., not installed), try flake8
        if "command not found" in pylint_result.message.lower() or "not recognized as an internal or external command" in pylint_result.message.lower():
            if self.logger: self.logger.info(f"  pylint not found for {file_path}. Trying flake8...")
            flake8_cmd = ["flake8", "--isolated", "--select=E9,F63,F7,F82", "--max-line-length=120"]
            flake8_error_pattern = re.compile(r'^(.*?):(\d+):(\d+): (E\d{3}|F\d{3}) (.*)$')
            flake8_result = self._run_linter_command(
                file_path, content, flake8_cmd, "flake8 OK", lines, chars,
                error_pattern=flake8_error_pattern, line_col_group_indices=(2, 3)
            )
            if flake8_result.status == ValidationStatus.VALID:
                return ValidationResult(file_path, ValidationStatus.VALID, "Python syntax and basic linting OK (via flake8)", lines, chars)
            elif flake8_result.status == ValidationStatus.SYNTAX_ERROR:
                return flake8_result
            elif "command not found" in flake8_result.message.lower() or "not recognized as an internal or external command" in flake8_result.message.lower():
                if self.logger: self.logger.warning(f"  Neither pylint nor flake8 found for {file_path}. Falling back to basic Python syntax check.")
                return self._validate_python_syntax_only(file_path, content, lines, chars)
            else:
                return flake8_result # Some other error from flake8
        
        return self._validate_python_syntax_only(file_path, content, lines, chars) # Fallback if no linter can be run

    def _validate_python_syntax_only(self, file_path, content, lines, chars) -> ValidationResult:
        """Performs a basic Python syntax check using Python's built-in compile function."""
        try:
            compile(content, file_path, "exec")
            return ValidationResult(file_path, ValidationStatus.VALID, "Python syntax OK", lines, chars)
        except SyntaxError as e:
            return ValidationResult(
                file_path, ValidationStatus.SYNTAX_ERROR,
                f"Python SyntaxError at line {e.lineno}: {e.msg}", lines, chars,
            )
