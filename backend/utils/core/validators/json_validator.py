import json

from backend.utils.core.validators.base_validator import BaseValidator, ValidationResult, ValidationStatus


class JsonValidator(BaseValidator):
    """Validator for JSON files."""

    def __init__(self, logger=None, command_executor=None):
        super().__init__(logger, command_executor)

    def validate(self, file_path: str, content: str, lines: int, chars: int, ext: str) -> ValidationResult:
        """
        Validates JSON file content.
        """
        try:
            json.loads(content)
            return ValidationResult(file_path, ValidationStatus.VALID, "Valid JSON", lines, chars)
        except json.JSONDecodeError as e:
            return ValidationResult(
                file_path,
                ValidationStatus.SYNTAX_ERROR,
                f"JSONDecodeError: {e.msg} at line {e.lineno}",
                lines,
                chars,
            )
