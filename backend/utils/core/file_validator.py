from pathlib import Path
from typing import Dict, List, Optional

# Import all specific validators
from backend.utils.core.validators.base_validator import ValidationResult, ValidationStatus
from backend.utils.core.validators.python_validator import PythonValidator
from backend.utils.core.validators.javascript_validator import JavascriptValidator
from backend.utils.core.validators.typescript_validator import TypescriptValidator
from backend.utils.core.validators.json_validator import JsonValidator
from backend.utils.core.validators.yaml_validator import YamlValidator
from backend.utils.core.validators.toml_validator import TomlValidator
from backend.utils.core.validators.default_validator import DefaultValidator


class FileValidator:
    """
    Orchestrates file content validation by dispatching to language-specific validators.
    """

    def __init__(self, logger=None, command_executor=None):
        self.logger = logger
        self.command_executor = command_executor

        # Initialize specific validators
        self._python_validator = PythonValidator(logger=logger, command_executor=command_executor)
        self._javascript_validator = JavascriptValidator(logger=logger, command_executor=command_executor)
        self._typescript_validator = TypescriptValidator(logger=logger, command_executor=command_executor)
        self._json_validator = JsonValidator(logger=logger, command_executor=command_executor)
        self._yaml_validator = YamlValidator(logger=logger, command_executor=command_executor)
        self._toml_validator = TomlValidator(logger=logger, command_executor=command_executor)
        self._default_validator = DefaultValidator(logger=logger, command_executor=command_executor) # Handles HTML, CSS, Markdown, XML, Shell, Batch, SQL, and Dependency files

        # Map file extensions to their respective validator instances
        self._validators_map = {
            ".py": self._python_validator,
            ".js": self._javascript_validator,
            ".jsx": self._javascript_validator,
            ".ts": self._typescript_validator,
            ".tsx": self._typescript_validator,
            ".json": self._json_validator,
            ".yaml": self._yaml_validator,
            ".yml": self._yaml_validator,
            ".toml": self._toml_validator,
            ".html": self._default_validator,
            ".htm": self._default_validator,
            ".css": self._default_validator,
            ".scss": self._default_validator,
            ".less": self._default_validator,
            ".md": self._default_validator,
            ".xml": self._default_validator,
            ".sh": self._default_validator,
            ".bash": self._default_validator,
            ".bat": self._default_validator,
            ".sql": self._default_validator,
            # Dependency files are handled explicitly in default_validator based on filename,
            # but also map here for dispatch if needed, falling back to default.
            "requirements.txt": self._default_validator,
            "package.json": self._default_validator,
            "Cargo.toml": self._default_validator,
            "go.mod": self._default_validator,
            "Gemfile": self._default_validator,
        }

    def validate(self, file_path: str, content: str) -> ValidationResult:
        """
        Validates a file's content by dispatching to the appropriate language-specific validator.
        """
        ext = Path(file_path).suffix.lower()
        stripped = content.strip() if content else ""
        line_count = len(stripped.splitlines()) if stripped else 0
        char_count = len(stripped)

        if char_count == 0:
            return ValidationResult(file_path, ValidationStatus.EMPTY, "File is empty", 0, 0)
        
        # Perform basic validation first
        basic_result = self._default_validator.basic_validation(file_path, stripped, ext, line_count, char_count)
        if basic_result.status != ValidationStatus.VALID:
            return basic_result

        # Get specific validator, fall back to default if none found
        validator = self._validators_map.get(ext)
        if validator:
            # For dependency files, the default validator needs the full filename, not just extension
            if Path(file_path).name in self._default_validator.DEPENDENCY_FILES:
                return self._default_validator.validate(file_path, stripped, line_count, char_count, ext)
            return validator.validate(file_path, stripped, line_count, char_count, ext)
        
        # Fallback to default validator if no specific extension match
        return self._default_validator.validate(file_path, stripped, line_count, char_count, ext)


    def validate_batch(self, files: Dict[str, str]) -> List[ValidationResult]:
        """Validate a dict of {path: content}."""
        return [self.validate(path, content) for path, content in files.items()]

    def check_content_completeness(self, file_path: str, content: str) -> Optional[str]:
        """Check if content has excessive placeholder/stub patterns."""
        if not content or not content.strip():
            return None

        lines = [ln for ln in content.splitlines() if ln.strip()]
        if not lines:
            return None

        placeholder_lines = sum(
            1 for ln in lines if self._default_validator._placeholder_re.search(ln)
        )
        ratio = placeholder_lines / len(lines)

        if ratio > 0.3:
            return (
                f"File appears incomplete: {placeholder_lines}/{len(lines)} lines "
                f"({ratio:.0%}) contain placeholder content (TODO, FIXME, placeholder, etc.)"
            )
        return None