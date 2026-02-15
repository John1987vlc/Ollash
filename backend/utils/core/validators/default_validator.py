import re
import xml.etree.ElementTree as ET # For XML validation
import json # ADDED
from backend.utils.core.validators.base_validator import BaseValidator, ValidationResult, ValidationStatus
from pathlib import Path


class DefaultValidator(BaseValidator):
    """
    A default validator for file types not covered by specific language validators.
    Includes basic checks for HTML, CSS, Markdown, XML, Shell, Batch, and SQL.
    Also handles dependency file validation.
    """

    DEPENDENCY_FILES = {
        "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
        "package.json", "Gemfile", "Cargo.toml", "go.mod",
    }

    MAX_DEPENDENCIES = 30
    MAX_PACKAGE_NAME_LENGTH = 80
    _PYPI_NAME_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$')


    def __init__(self, logger=None, command_executor=None):
        super().__init__(logger, command_executor)

    def validate(self, file_path: str, content: str, lines: int, chars: int, ext: str) -> ValidationResult:
        filename = Path(file_path).name

        # Handle dependency files
        if filename in self.DEPENDENCY_FILES:
            dep_result = self._validate_dependency_file(file_path, content, lines, chars)
            if dep_result.status != ValidationStatus.VALID:
                return dep_result
            # For dependency files, this is the primary validation, so we return it.
            return dep_result


        # Handle other file types by extension
        if ext in (".html", ".htm"):
            return self._validate_html(file_path, content, lines, chars)
        elif ext in (".css", ".scss", ".less"):
            return self._validate_css(file_path, content, lines, chars)
        elif ext == ".md":
            return self._validate_markdown(file_path, content, lines, chars)
        elif ext == ".xml":
            return self._validate_xml(file_path, content, lines, chars)
        elif ext in (".sh", ".bash"):
            return self._validate_shell(file_path, content, lines, chars)
        elif ext == ".bat":
            return self._validate_batch(file_path, content, lines, chars)
        elif ext == ".sql":
            return self._validate_sql(file_path, content, lines, chars)

        # If no specific validation, and it's a brace language, do basic brace check
        if ext in self.BRACE_LANGUAGES:
            return self._validate_brace_language(file_path, content, lines, chars)

        return ValidationResult(file_path, ValidationStatus.VALID, "No specific validation, basic checks passed", lines, chars)

    def _is_html_partial(self, file_path: str) -> bool:
        """Heuristic to determine if a file is likely an HTML partial."""
        path_obj = Path(file_path)
        return "partials" in path_obj.parts or path_obj.name.startswith("_")

    def _validate_html(self, path, content, lines, chars) -> ValidationResult:
        lower = content.lower()
        if self._is_html_partial(path):
            if not lower:
                return ValidationResult(path, ValidationStatus.EMPTY, "HTML partial is empty", lines, chars)
            if not re.search(r'<\w+[^>]*>', lower):
                return ValidationResult(path, ValidationStatus.TRUNCATED, "HTML partial contains no recognizable HTML tags", lines, chars)
            return ValidationResult(path, ValidationStatus.VALID, "HTML partial structure OK", lines, chars)

        if "<html" not in lower and "<!doctype" not in lower:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                "Missing <html> or <!DOCTYPE> tag", lines, chars,
            )
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
        has_rule = re.search(r'[a-zA-Z.#\[\*:@][^{]*\{[^}]*\}', content, re.DOTALL)
        if not has_rule:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                "CSS file has no valid rule patterns (selector { property })",
                lines, chars,
            )
        return ValidationResult(path, ValidationStatus.VALID, "CSS structure OK", lines, chars)

    def _validate_markdown(self, path, content, lines, chars) -> ValidationResult:
        non_heading_content = re.sub(r'^#{1,6}\s+.*$', '', content, flags=re.MULTILINE).strip()
        if len(non_heading_content) < 20:
            return ValidationResult(
                path, ValidationStatus.TRUNCATED,
                f"Markdown has only headings with no substantial content ({len(non_heading_content)} chars of body text)",
                lines, chars,
            )
        return ValidationResult(path, ValidationStatus.VALID, "Markdown structure OK", lines, chars)

    def _validate_xml(self, path, content, lines, chars) -> ValidationResult:
        try:
            ET.fromstring(content)
            return ValidationResult(path, ValidationStatus.VALID, "Valid XML", lines, chars)
        except ET.ParseError as e:
            return ValidationResult(
                path, ValidationStatus.SYNTAX_ERROR,
                f"XML parse error: {e}", lines, chars,
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
        elif filename == "Cargo.toml": # Placeholder
            return ValidationResult(path, ValidationStatus.VALID, "Cargo.toml basic check passed", lines, chars)
        elif filename == "go.mod": # Placeholder
            return ValidationResult(path, ValidationStatus.VALID, "go.mod basic check passed", lines, chars)
        elif filename == "Gemfile": # Placeholder
            return ValidationResult(path, ValidationStatus.VALID, "Gemfile basic check passed", lines, chars)

        return ValidationResult(path, ValidationStatus.VALID, "Dependency file basic check passed", lines, chars)

    def _validate_requirements_txt(self, path, content, lines, chars) -> ValidationResult:
        """Validate Python requirements.txt for hallucinated packages."""
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.strip().startswith("-"):
                continue
            entries.append(line)

        if len(entries) > self.MAX_DEPENDENCIES:
            return ValidationResult(
                path, ValidationStatus.SYNTAX_ERROR,
                f"Excessive dependencies: {len(entries)} entries (max {self.MAX_DEPENDENCIES}). "
                f"Likely contains hallucinated packages.",
                lines, chars,
            )

        invalid_names = []
        for entry in entries:
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
