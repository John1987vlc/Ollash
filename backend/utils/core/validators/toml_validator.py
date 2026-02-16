from backend.utils.core.validators.base_validator import BaseValidator, ValidationResult, ValidationStatus


class TomlValidator(BaseValidator):
    """Validator for TOML files."""

    def __init__(self, logger=None, command_executor=None):
        super().__init__(logger, command_executor)

    def validate(self, file_path: str, content: str, lines: int, chars: int, ext: str) -> ValidationResult:
        """
        Validates TOML file content.
        """
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return ValidationResult(
                    file_path,
                    ValidationStatus.UNKNOWN_TYPE,
                    "No TOML parser available",
                    lines,
                    chars,
                )
        try:
            tomllib.loads(content)
            return ValidationResult(file_path, ValidationStatus.VALID, "Valid TOML", lines, chars)
        except Exception as e:
            return ValidationResult(
                file_path,
                ValidationStatus.SYNTAX_ERROR,
                f"TOML error: {e}",
                lines,
                chars,
            )
