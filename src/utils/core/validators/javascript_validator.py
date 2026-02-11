import re
from src.utils.core.validators.base_validator import BaseValidator, ValidationResult, ValidationStatus


class JavascriptValidator(BaseValidator):
    """Validator for JavaScript files, integrating ESLint."""

    def __init__(self, logger=None, command_executor=None):
        super().__init__(logger, command_executor)

    def validate(self, file_path: str, content: str, lines: int, chars: int, ext: str) -> ValidationResult:
        """
        Validates JavaScript file content using ESLint.
        """
        if not self.command_executor:
            return self._validate_brace_language(file_path, content, lines, chars) # Fallback

        eslint_cmd = ["eslint", "--no-eslintrc", "--parser-options=ecmaVersion:2021", "--format=compact"]
        eslint_error_pattern = re.compile(r'^(.*?): line (\d+), col (\d+), (Error|Warning) - (.*)$')
        eslint_result = self._run_linter_command(
            file_path, content, eslint_cmd, "eslint OK", lines, chars,
            error_pattern=eslint_error_pattern, line_col_group_indices=(2, 3)
        )
        if eslint_result.status == ValidationStatus.VALID:
            return ValidationResult(file_path, ValidationStatus.VALID, "JavaScript syntax and linting OK", lines, chars)
        elif "command not found" in eslint_result.message.lower() or "not recognized as an internal or external command" in eslint_result.message.lower():
            if self.logger: self.logger.warning(f"  eslint not found for {file_path}. Falling back to basic JS brace check.")
            return self._validate_brace_language(file_path, content, lines, chars)
        else:
            return eslint_result