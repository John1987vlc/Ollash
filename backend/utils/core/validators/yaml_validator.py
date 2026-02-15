from backend.utils.core.validators.base_validator import (BaseValidator,
                                                          ValidationResult,
                                                          ValidationStatus)


class YamlValidator(BaseValidator):
    """Validator for YAML files."""

    def __init__(self, logger=None, command_executor=None):
        super().__init__(logger, command_executor)

    def validate(
        self, file_path: str, content: str, lines: int, chars: int, ext: str
    ) -> ValidationResult:
        """
        Validates YAML file content.
        """
        try:
            import yaml

            yaml.safe_load(content)
            return ValidationResult(
                file_path, ValidationStatus.VALID, "Valid YAML", lines, chars
            )
        except ImportError:
            return ValidationResult(
                file_path,
                ValidationStatus.UNKNOWN_TYPE,
                "PyYAML not installed",
                lines,
                chars,
            )
        except Exception as e:
            return ValidationResult(
                file_path,
                ValidationStatus.SYNTAX_ERROR,
                f"YAML error: {e}",
                lines,
                chars,
            )
