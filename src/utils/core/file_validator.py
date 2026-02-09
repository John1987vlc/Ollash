import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


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


class FileValidator:
    """Validates generated file content for syntax correctness and completeness."""

    MIN_LINES = {
        ".py": 3,
        ".js": 3,
        ".ts": 3,
        ".tsx": 3,
        ".jsx": 3,
        ".html": 5,
        ".css": 3,
        ".scss": 3,
        ".sass": 3,
        ".less": 3,
        ".json": 1,
        ".yaml": 1,
        ".yml": 1,
        ".toml": 1,
        ".md": 3,
        ".txt": 1,
        ".sh": 1,
        ".bash": 1,
        ".bat": 1,
        ".ps1": 1,
        ".cs": 3,
        ".java": 3,
        ".go": 3,
        ".rs": 3,
        ".rb": 3,
        ".php": 3,
        ".swift": 3,
        ".kt": 3,
        ".scala": 3,
        ".c": 3,
        ".cpp": 3,
        ".h": 1,
        ".hpp": 1,
        ".r": 1,
        ".R": 1,
        ".lua": 1,
        ".sql": 1,
        ".dockerfile": 1,
        ".tf": 1,
        ".cmake": 1,
    }

    MIN_CHARS = {
        ".css": 50,
        ".md": 30,
    }

    # Extensions where brace-matching is meaningful
    BRACE_LANGUAGES = {
        ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".cs",
        ".go", ".rs", ".swift", ".kt", ".scala", ".php", ".less", ".scss",
    }

    # Patterns that indicate placeholder/stub content
    PLACEHOLDER_PATTERNS = [
        r'\bTODO\b',
        r'\bFIXME\b',
        r'\blorem ipsum\b',
        r'\bplaceholder\b',
        r'\bsample\s+text\b',
        r'\bput\s+your\b',
        r'\badd\s+your\b',
        r'\byour\s+.*\s+here\b',
        r'\binsert\s+.*\s+here\b',
        r'\.{3,}',  # Three or more dots (ellipsis as placeholder)
    ]

    # Filenames that are dependency manifests (checked by name, not extension)
    DEPENDENCY_FILES = {
        "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
        "package.json", "Gemfile", "Cargo.toml", "go.mod",
    }

    # Max reasonable number of dependencies for a single generated project
    MAX_DEPENDENCIES = 30

    # Max reasonable length for a single package name
    MAX_PACKAGE_NAME_LENGTH = 80

    # Pattern for valid PyPI package names (PEP 508)
    _PYPI_NAME_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$')

    def __init__(self, logger=None):
        self.logger = logger
        self._validators = {
            ".py": self._validate_python,
            ".json": self._validate_json,
            ".yaml": self._validate_yaml,
            ".yml": self._validate_yaml,
            ".toml": self._validate_toml,
            ".html": self._validate_html,
            ".xml": self._validate_xml,
            ".css": self._validate_css,
            ".scss": self._validate_css,
            ".less": self._validate_css,
            ".md": self._validate_markdown,
            ".sh": self._validate_shell,
            ".bash": self._validate_shell,
            ".bat": self._validate_batch,
            ".sql": self._validate_sql,
        }
        self._placeholder_re = re.compile(
            '|'.join(self.PLACEHOLDER_PATTERNS), re.IGNORECASE
        )

    def validate(self, file_path: str, content: str) -> ValidationResult:
        """Validate a file's content based on its extension."""
        ext = Path(file_path).suffix.lower()
        stripped = content.strip() if content else ""
        line_count = len(stripped.splitlines()) if stripped else 0
        char_count = len(stripped)

        if char_count == 0:
            return ValidationResult(file_path, ValidationStatus.EMPTY, "File is empty", 0, 0)

        min_lines = self.MIN_LINES.get(ext, 1)
        if line_count < min_lines:
            return ValidationResult(
                file_path, ValidationStatus.TRUNCATED,
                f"File has {line_count} lines, minimum expected {min_lines}",
                line_count, char_count,
            )

        min_chars = self.MIN_CHARS.get(ext, 0)
        if min_chars and char_count < min_chars:
            return ValidationResult(
                file_path, ValidationStatus.TRUNCATED,
                f"File has {char_count} chars, minimum expected {min_chars}",
                line_count, char_count,
            )

        # Check dependency manifests by filename (before extension-based dispatch)
        filename = Path(file_path).name
        if filename in self.DEPENDENCY_FILES:
            dep_result = self._validate_dependency_file(file_path, stripped, line_count, char_count)
            if dep_result.status != ValidationStatus.VALID:
                return dep_result
            # For dependency files, also run extension-based validation if available,
            # but prefer the dependency result message if both pass
            validator = self._validators.get(ext)
            if validator:
                ext_result = validator(file_path, stripped, line_count, char_count)
                if ext_result.status != ValidationStatus.VALID:
                    return ext_result
            return dep_result

        validator = self._validators.get(ext)
        if validator:
            return validator(file_path, stripped, line_count, char_count)

        if ext in self.BRACE_LANGUAGES:
            return self._validate_brace_language(file_path, stripped, line_count, char_count)

        return ValidationResult(file_path, ValidationStatus.VALID, "Basic checks passed", line_count, char_count)

    def validate_batch(self, files: Dict[str, str]) -> List[ValidationResult]:
        """Validate a dict of {path: content}."""
        return [self.validate(path, content) for path, content in files.items()]

    def check_content_completeness(self, file_path: str, content: str) -> Optional[str]:
        """Check if content has excessive placeholder/stub patterns.

        Returns a warning message if >30% of non-empty lines are placeholders, else None.
        """
        if not content or not content.strip():
            return None

        lines = [ln for ln in content.splitlines() if ln.strip()]
        if not lines:
            return None

        placeholder_lines = sum(
            1 for ln in lines if self._placeholder_re.search(ln)
        )
        ratio = placeholder_lines / len(lines)

        if ratio > 0.3:
            return (
                f"File appears incomplete: {placeholder_lines}/{len(lines)} lines "
                f"({ratio:.0%}) contain placeholder content (TODO, FIXME, placeholder, etc.)"
            )
        return None

    # -- Language-specific validators --

    def _validate_python(self, path, content, lines, chars) -> ValidationResult:
        try:
            compile(content, path, "exec")
            return ValidationResult(path, ValidationStatus.VALID, "Syntax OK", lines, chars)
        except SyntaxError as e:
            return ValidationResult(
                path, ValidationStatus.SYNTAX_ERROR,
                f"SyntaxError at line {e.lineno}: {e.msg}", lines, chars,
            )

    def _validate_json(self, path, content, lines, chars) -> ValidationResult:
        try:
            json.loads(content)
            return ValidationResult(path, ValidationStatus.VALID, "Valid JSON", lines, chars)
        except json.JSONDecodeError as e:
            return ValidationResult(
                path, ValidationStatus.SYNTAX_ERROR,
                f"JSONDecodeError: {e.msg} at line {e.lineno}", lines, chars,
            )

    def _validate_yaml(self, path, content, lines, chars) -> ValidationResult:
        try:
            import yaml
            yaml.safe_load(content)
            return ValidationResult(path, ValidationStatus.VALID, "Valid YAML", lines, chars)
        except ImportError:
            return ValidationResult(path, ValidationStatus.UNKNOWN_TYPE, "PyYAML not installed", lines, chars)
        except Exception as e:
            return ValidationResult(
                path, ValidationStatus.SYNTAX_ERROR,
                f"YAML error: {e}", lines, chars,
            )

    def _validate_html(self, path, content, lines, chars) -> ValidationResult:
        lower = content.lower()
        if "<html" not in lower and "<!doctype" not in lower:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                "Missing <html> or <!DOCTYPE> tag", lines, chars,
            )
        # Check for unclosed major tags
        for tag in ["html", "head", "body"]:
            open_count = len(re.findall(rf'<{tag}[\s>]', lower))
            close_count = len(re.findall(rf'</{tag}\s*>', lower))
            if open_count > close_count:
                return ValidationResult(
                    path, ValidationStatus.TRUNCATED,
                    f"Unclosed <{tag}> tag: {open_count} open vs {close_count} close",
                    lines, chars,
                )
        return ValidationResult(path, ValidationStatus.VALID, "HTML structure OK", lines, chars)

    def _validate_css(self, path, content, lines, chars) -> ValidationResult:
        # Check brace matching
        open_braces = content.count("{")
        close_braces = content.count("}")
        if open_braces == 0:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                "CSS file has no rule blocks (no { found)",
                lines, chars,
            )
        if open_braces > close_braces + 1:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                f"Unmatched braces: {open_braces} open vs {close_braces} close",
                lines, chars,
            )
        # Check for at least one CSS rule pattern (selector { ... })
        has_rule = re.search(r'[a-zA-Z.#\[\*:@][^{]*\{[^}]*\}', content, re.DOTALL)
        if not has_rule:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                "CSS file has no valid rule patterns (selector { property })",
                lines, chars,
            )
        return ValidationResult(path, ValidationStatus.VALID, "CSS structure OK", lines, chars)

    def _validate_markdown(self, path, content, lines, chars) -> ValidationResult:
        # Strip heading lines and check remaining content has substance
        non_heading_content = re.sub(r'^#{1,6}\s+.*$', '', content, flags=re.MULTILINE).strip()
        if len(non_heading_content) < 20:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                f"Markdown has only headings with no substantial content ({len(non_heading_content)} chars of body text)",
                lines, chars,
            )
        return ValidationResult(path, ValidationStatus.VALID, "Markdown structure OK", lines, chars)

    def _validate_xml(self, path, content, lines, chars) -> ValidationResult:
        import xml.etree.ElementTree as ET
        try:
            ET.fromstring(content)
            return ValidationResult(path, ValidationStatus.VALID, "Valid XML", lines, chars)
        except ET.ParseError as e:
            return ValidationResult(
                path, ValidationStatus.SYNTAX_ERROR,
                f"XML parse error: {e}", lines, chars,
            )

    def _validate_toml(self, path, content, lines, chars) -> ValidationResult:
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return ValidationResult(path, ValidationStatus.UNKNOWN_TYPE, "No TOML parser available", lines, chars)
        try:
            tomllib.loads(content)
            return ValidationResult(path, ValidationStatus.VALID, "Valid TOML", lines, chars)
        except Exception as e:
            return ValidationResult(
                path, ValidationStatus.SYNTAX_ERROR,
                f"TOML error: {e}", lines, chars,
            )

    def _validate_shell(self, path, content, lines, chars) -> ValidationResult:
        first_line = content.splitlines()[0] if content.splitlines() else ""
        if not first_line.startswith("#!") and not first_line.startswith("#"):
            return ValidationResult(
                path, ValidationStatus.VALID,
                "Shell script (no shebang, but content present)", lines, chars,
            )
        return ValidationResult(path, ValidationStatus.VALID, "Shell script OK", lines, chars)

    def _validate_batch(self, path, content, lines, chars) -> ValidationResult:
        # Basic check: batch files should have some commands
        lower = content.lower()
        if "@echo" in lower or "set " in lower or "echo " in lower or "rem " in lower or "call " in lower:
            return ValidationResult(path, ValidationStatus.VALID, "Batch file OK", lines, chars)
        return ValidationResult(path, ValidationStatus.VALID, "Batch file (basic check passed)", lines, chars)

    def _validate_sql(self, path, content, lines, chars) -> ValidationResult:
        upper = content.upper()
        sql_keywords = ["SELECT", "CREATE", "INSERT", "UPDATE", "DELETE", "ALTER", "DROP", "BEGIN", "DECLARE"]
        if any(kw in upper for kw in sql_keywords):
            return ValidationResult(path, ValidationStatus.VALID, "SQL syntax OK", lines, chars)
        return ValidationResult(path, ValidationStatus.VALID, "SQL file (basic check passed)", lines, chars)

    def _validate_dependency_file(self, path, content, lines, chars) -> ValidationResult:
        """Validate dependency manifest files for hallucinated or excessive entries."""
        filename = Path(path).name

        if filename.startswith("requirements") and filename.endswith(".txt"):
            return self._validate_requirements_txt(path, content, lines, chars)
        elif filename == "package.json":
            return self._validate_package_json_deps(path, content, lines, chars)

        # For other dependency files (Gemfile, Cargo.toml, go.mod), just do basic checks
        return ValidationResult(path, ValidationStatus.VALID, "Dependency file basic check passed", lines, chars)

    def _validate_requirements_txt(self, path, content, lines, chars) -> ValidationResult:
        """Validate Python requirements.txt for hallucinated packages."""
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            entries.append(line)

        if len(entries) > self.MAX_DEPENDENCIES:
            return ValidationResult(
                path, ValidationStatus.SYNTAX_ERROR,
                f"Excessive dependencies: {len(entries)} entries (max {self.MAX_DEPENDENCIES}). "
                f"Likely contains hallucinated packages.",
                lines, chars,
            )

        # Check for invalid package names
        invalid_names = []
        for entry in entries:
            # Extract package name (before version specifier)
            pkg_name = re.split(r'[><=!~\[]', entry)[0].strip()
            if len(pkg_name) > self.MAX_PACKAGE_NAME_LENGTH:
                invalid_names.append(pkg_name[:50] + "...")
            elif not self._PYPI_NAME_RE.match(pkg_name):
                invalid_names.append(pkg_name)

        if invalid_names:
            return ValidationResult(
                path, ValidationStatus.SYNTAX_ERROR,
                f"Invalid package names found: {', '.join(invalid_names[:5])}"
                f"{f' (and {len(invalid_names) - 5} more)' if len(invalid_names) > 5 else ''}",
                lines, chars,
            )

        # Check for duplicates
        seen = set()
        duplicates = []
        for entry in entries:
            pkg_name = re.split(r'[><=!~\[]', entry)[0].strip().lower()
            if pkg_name in seen:
                duplicates.append(pkg_name)
            seen.add(pkg_name)

        if duplicates:
            return ValidationResult(
                path, ValidationStatus.SYNTAX_ERROR,
                f"Duplicate packages: {', '.join(duplicates[:5])}",
                lines, chars,
            )

        return ValidationResult(path, ValidationStatus.VALID, f"Requirements OK ({len(entries)} packages)", lines, chars)

    def _validate_package_json_deps(self, path, content, lines, chars) -> ValidationResult:
        """Validate package.json dependencies for excessive entries."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Let the JSON validator handle parse errors
            return ValidationResult(path, ValidationStatus.VALID, "Deferred to JSON validator", lines, chars)

        total_deps = 0
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            deps = data.get(key, {})
            if isinstance(deps, dict):
                total_deps += len(deps)

        if total_deps > self.MAX_DEPENDENCIES:
            return ValidationResult(
                path, ValidationStatus.SYNTAX_ERROR,
                f"Excessive dependencies in package.json: {total_deps} total (max {self.MAX_DEPENDENCIES}). "
                f"Likely contains hallucinated packages.",
                lines, chars,
            )

        return ValidationResult(path, ValidationStatus.VALID, f"package.json OK ({total_deps} deps)", lines, chars)

    def _validate_brace_language(self, path, content, lines, chars) -> ValidationResult:
        open_braces = content.count("{")
        close_braces = content.count("}")
        if open_braces > close_braces + 1:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                f"Unmatched braces: {open_braces} open vs {close_braces} close",
                lines, chars,
            )
        # Also check parentheses and brackets
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
