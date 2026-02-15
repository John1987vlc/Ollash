import re
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING
from abc import abstractmethod

if TYPE_CHECKING:
    from backend.utils.core.command_executor import CommandExecutor # Avoid circular import at runtime


class ValidationStatus(Enum):
    VALID = "valid"
    SYNTAX_ERROR = "syntax_error"
    TRUNCATED = "truncated"
    EMPTY = "empty"
    UNKNOWN_TYPE = "unknown_type"


@dataclass
class ValidationResult:
    file_path: str
    status: ValidationStatus
    message: str
    line_count: int
    char_count: int


class BaseValidator:
    """Base class for all language-specific validators, providing common utilities."""

    @abstractmethod
    def validate(self, file_path: str, content: str, lines: int, chars: int, ext: str) -> ValidationResult:
        """Abstract method to be implemented by subclasses for language-specific validation."""
        pass

    MIN_LINES = {
        ".py": 3, ".js": 3, ".ts": 3, ".tsx": 3, ".jsx": 3, ".html": 5,
        ".css": 3, ".scss": 3, ".sass": 3, ".less": 3, ".json": 1,
        ".yaml": 1, ".yml": 1, ".toml": 1, ".md": 3, ".txt": 1,
        ".sh": 1, ".bash": 1, ".bat": 1, ".ps1": 1, ".cs": 3,
        ".java": 3, ".go": 3, ".rs": 3, ".rb": 3, ".php": 3,
        ".swift": 3, ".kt": 3, ".scala": 3, ".c": 3, ".cpp": 3,
        ".h": 1, ".hpp": 1, ".r": 1, ".R": 1, ".lua": 1, ".sql": 1,
        ".dockerfile": 1, ".tf": 1, ".cmake": 1,
    }

    MIN_CHARS = {
        ".css": 50, ".md": 30,
    }

    BRACE_LANGUAGES = {
        ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".cs",
        ".go", ".rs", ".swift", ".kt", ".scala", ".php", ".less", ".scss",
    }

    # Patterns that indicate placeholder/stub content
    PLACEHOLDER_PATTERNS = [
        r'\bTODO\b', r'\bFIXME\b', r'\blorem ipsum\b', r'\bplaceholder\b',
        r'\bsample\s+text\b', r'\bput\s+your\b', r'\badd\s+your\b',
        r'\byour\s+.*\s+here\b', r'\binsert\s+.*\s+here\b', r'\.{3,}',
    ]
    _placeholder_re = re.compile('|'.join(PLACEHOLDER_PATTERNS), re.IGNORECASE)


    def __init__(self, logger=None, command_executor: Optional['CommandExecutor'] = None):
        self.logger = logger
        self.command_executor = command_executor

    def basic_validation(self, file_path: str, content: str, ext: str, lines: int, chars: int) -> ValidationResult:
        """Performs basic validation checks common to all file types."""
        min_lines = self.MIN_LINES.get(ext, 1)
        if lines < min_lines:
            return ValidationResult(
                file_path, ValidationStatus.TRUNCATED,
                f"File has {lines} lines, minimum expected {min_lines}",
                lines, chars,
            )

        min_chars = self.MIN_CHARS.get(ext, 0)
        if min_chars and chars < min_chars:
            return ValidationResult(
                file_path, ValidationStatus.TRUNCATED,
                f"File has {chars} chars, minimum expected {min_chars}",
                lines, chars,
            )
        return ValidationResult(file_path, ValidationStatus.VALID, "Basic checks passed", lines, chars)


    def _run_linter_command(
        self,
        file_path: str,
        content: str,
        command: List[str],
        success_message: str,
        lines: int,
        chars: int,
        error_pattern: Optional[re.Pattern] = None,
        line_col_group_indices: Tuple[int, int] = (1, 2),
        timeout: int = 15
    ) -> ValidationResult:
        """
        Runs a linter command and parses its output into a ValidationResult.
        """
        if not self.command_executor:
            return ValidationResult(
                file_path, ValidationStatus.UNKNOWN_TYPE,
                "CommandExecutor not available for linting.", lines, chars
            )

        lint_temp_dir = Path(self.command_executor.working_dir) / ".lint_temp"
        lint_temp_dir.mkdir(parents=True, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", dir=lint_temp_dir, suffix=Path(file_path).suffix) as tmp_f:
            tmp_f.write(content)
            temp_file_path = Path(tmp_f.name)
        
        rel_temp_file_path = temp_file_path.relative_to(self.command_executor.working_dir)

        linter_command = command + [str(rel_temp_file_path)]

        try:
            result = self.command_executor.execute(linter_command, timeout=timeout)
        finally:
            if temp_file_path.exists():
                temp_file_path.unlink()
            if lint_temp_dir.exists() and not any(lint_temp_dir.iterdir()):
                Path(lint_temp_dir).rmdir() # Use Path object for rmdir


        if result.success:
            return ValidationResult(file_path, ValidationStatus.VALID, success_message, lines, chars)
        else:
            error_message = result.stderr.strip() or result.stdout.strip()
            
            # Check if command not found
            if "not found" in error_message.lower() or "is not recognized" in error_message.lower() or \
               "no such file or directory" in error_message.lower():
                return ValidationResult(
                    file_path, ValidationStatus.SYNTAX_ERROR,
                    f"Linter command not found: {command[0]}. " + error_message, lines, chars
                )
            
            if error_message:
                parsed_errors = []
                clean_error_message = []
                for line in error_message.splitlines():
                    if "no issues found" in line.lower() or "completed" in line.lower() or "checking" in line.lower() or "passing" in line.lower() or "running" in line.lower():
                        continue
                    clean_error_message.append(line)
                error_message = "\n".join(clean_error_message)

                if error_pattern:
                    for line in error_message.splitlines():
                        match = error_pattern.search(line)
                        if match:
                            try:
                                line_num = int(match.group(line_col_group_indices[0]))
                                col_num = int(match.group(line_col_group_indices[1]))
                                parsed_errors.append(f"Line {line_num}, Col {col_num}: {line}")
                            except (ValueError, IndexError):
                                parsed_errors.append(line)
                        else:
                            parsed_errors.append(line)
                else:
                    parsed_errors = error_message.splitlines()

                full_error_message = "Linter errors:\n" + "\n".join(parsed_errors[:10])
                if len(parsed_errors) > 10:
                    full_error_message += f"\n... ({len(parsed_errors) - 10} more errors)"
                
                return ValidationResult(
                    file_path, ValidationStatus.SYNTAX_ERROR,
                    full_error_message, lines, chars
                )
            else:
                return ValidationResult(
                    file_path, ValidationStatus.SYNTAX_ERROR,
                    f"Linter command failed with exit code {result.return_code}. No output.", lines, chars
                )

    def _validate_brace_language(self, path, content, lines, chars) -> ValidationResult:
        open_braces = content.count("{")
        close_braces = content.count("}")
        if open_braces > close_braces + 1:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                f"Unmatched braces: {open_braces} open vs {close_braces} close",
                lines, chars,
            )
        open_parens = content.count("(")
        close_parens = content.count(")")
        if open_parens > close_parens + 2:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                f"Unmatched parentheses: {open_parens} open vs {close_parens} close",
                lines, chars,
            )
        open_brackets = content.count("[")
        close_brackets = content.count("]")
        if open_brackets > close_brackets + 2:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                f"Unmatched brackets: {open_brackets} open vs {close_brackets} close",
                lines, chars,
            )
        return ValidationResult(path, ValidationStatus.VALID, "Brace check passed", lines, chars)
