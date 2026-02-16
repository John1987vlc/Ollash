import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class AdvancedCodeTools:
    def __init__(self, project_root: Path, code_analyzer: Any, command_executor: Any, logger: Any):
        self.project_root = project_root
        self.code_analyzer = code_analyzer
        self.exec = command_executor
        self.logger = logger

    def detect_code_smells(self, path: str) -> Dict:
        """
        Analyzes files or folders for code smells (long functions, duplication, dead imports, etc.).
        Performs a basic check for excessively long files.
        """
        self.logger.info(f"Detecting code smells in: {path}")

        smells_found = []
        target_path = Path(path)

        if not target_path.exists():
            return {"ok": False, "result": {"error": f"Path not found: {path}"}}

        if target_path.is_file():
            files_to_check = [target_path]
        elif target_path.is_dir():
            files_to_check = [f for f in target_path.rglob("*") if f.is_file()]
        else:
            return {
                "ok": False,
                "result": {"error": f"Path is neither a file nor a directory: {path}"},
            }

        long_file_threshold = 500  # Lines

        for file_path in files_to_check:
            try:
                if file_path.suffix not in [
                    ".py",
                    ".js",
                    ".ts",
                    ".java",
                    ".cs",
                    ".cpp",
                    ".c",
                    ".go",
                    ".rs",
                ]:  # Only check code files
                    continue

                content = file_path.read_text(encoding="utf-8", errors="ignore")
                line_count = len(content.splitlines())

                if line_count > long_file_threshold:
                    smells_found.append(
                        {
                            "file": str(file_path),
                            "type": "Long File",
                            "details": f"File has {line_count} lines, exceeding the {long_file_threshold} line threshold. This may indicate excessive complexity.",
                            "severity": "medium",
                        }
                    )
            except Exception as e:
                self.logger.warning(f"Could not read file {file_path} for smell detection: {e}")

        if smells_found:
            summary = f"Found {len(smells_found)} potential code smells."
            status = "smells_detected"
        else:
            summary = "No significant code smells detected (basic checks)."
            status = "no_smells_detected"

        return {
            "ok": True,
            "result": {
                "path_analyzed": path,
                "status": status,
                "summary": summary,
                "smells": smells_found,
                "note": "This is a basic line-count based smell detection. Advanced tools would integrate with static analysis tools.",
            },
        }

    def suggest_refactor(self, file_path: str, line_number: Optional[int] = None) -> Dict:
        """
        Proposes concrete refactors (without executing them), indicating benefits and risks.
        Provides a generic suggestion based on whether a line number is specified.
        """
        self.logger.info(f"Suggesting refactor for: {file_path}" + (f":{line_number}" if line_number else ""))

        target_path = Path(file_path)
        if not target_path.is_file():
            return {"ok": False, "result": {"error": f"File not found: {file_path}"}}

        suggestions = []
        if line_number:
            suggestions.append(
                {
                    "type": "Extract Method/Function",
                    "description": f"Consider extracting the code block around line {line_number} into a separate, well-named function or method. This can improve modularity and testability.",
                    "benefits": "Improved readability, easier testing, better code reuse.",
                    "risks": "Low risk if done carefully; ensure correct parameter passing and return values.",
                    "context_line": line_number,
                }
            )
            suggestions.append(
                {
                    "type": "Simplify Conditional",
                    "description": f"Review the conditional logic near line {line_number} for potential simplification or inversion to enhance clarity.",
                    "benefits": "Reduced cognitive load, fewer bugs related to complex conditions.",
                    "risks": "Low risk with proper testing.",
                }
            )
        else:
            suggestions.append(
                {
                    "type": "General Code Structure",
                    "description": "Review the file for opportunities to break down large functions, simplify complex classes, or introduce design patterns. Consider SOLID principles.",
                    "benefits": "Better maintainability, scalability, and extensibility.",
                    "risks": "Medium to high risk depending on the extent of refactoring; requires thorough testing.",
                    "note": "A more specific suggestion would require detailed code analysis (e.g., AST parsing).",
                }
            )
            suggestions.append(
                {
                    "type": "Naming Conventions",
                    "description": "Ensure variable, function, and class names are clear, concise, and follow established project conventions.",
                    "benefits": "Enhanced readability and collaboration.",
                    "risks": "Very low risk.",
                }
            )

        summary = f"Generated {len(suggestions)} refactoring suggestions for {file_path}."

        return {
            "ok": True,
            "result": {
                "file_path": file_path,
                "summary": summary,
                "suggestions": suggestions,
                "note": "These are generic refactoring suggestions. A more advanced tool would use static analysis to generate context-aware proposals.",
            },
        }

    def map_code_dependencies(self, package_or_module: str) -> Dict:
        """
        Builds a logical map of dependencies between modules, services, or packages.
        Performs a basic search for import statements in Python files within the project.
        """
        self.logger.info(f"Mapping dependencies for: {package_or_module}")

        dependencies = set()
        dependents = set()

        # Simple regex to find import statements
        import_pattern = re.compile(
            r"^\s*(?:from\s+([a-zA-Z0-9_.]+)\s+import|\s*import\s+([a-zA-Z0-9_.]+))",
            re.MULTILINE,
        )

        # Assuming project_root is accessible or passed. For now, checking cwd.
        # A more robust solution would integrate with FileManager and CodeAnalyzer

        # Iterate over all Python files in the current working directory (or project_root)
        project_root = Path.os.getcwd()  # Assuming current working directory for simplicity

        for file_path in Path(project_root).rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")

                # Check for dependencies within the file
                for match in import_pattern.finditer(content):
                    if match.group(1):  # from ... import
                        dependencies.add(match.group(1))
                    if match.group(2):  # import ...
                        dependencies.add(match.group(2))

                # Check if this file is a dependent of the target package_or_module
                if f"import {package_or_module}" in content or f"from {package_or_module}" in content:
                    dependents.add(str(file_path.relative_to(project_root)))

            except Exception as e:
                self.logger.warning(f"Could not read file {file_path} for dependency mapping: {e}")

        # Filter out self-imports or standard library modules for a cleaner output
        dependencies = sorted(list(dependencies))
        dependents = sorted(list(dependents))

        return {
            "ok": True,
            "result": {
                "target": package_or_module,
                "dependencies_found": dependencies,
                "dependents_found": dependents,
                "summary": f"Found {len(dependencies)} dependencies and {len(dependents)} dependents for '{package_or_module}' (basic search).",
                "note": "This is a basic keyword/regex-based dependency map for Python files. A robust solution requires AST parsing or dedicated tools and access to the project's root.",
            },
        }

    def compare_configs(self, file_paths: List[str]) -> Dict:
        """
        Compares two or more configuration files and detects relevant semantic differences.
        Prioritizes JSON parsing for comparison; falls back to line-by-line textual diff.
        """
        self.logger.info(f"Comparing configuration files: {', '.join(file_paths)}")

        if len(file_paths) < 2:
            return {
                "ok": False,
                "result": {"error": "At least two file paths are required for comparison."},
            }

        differences_found = []
        parsed_contents = {}

        for f_path in file_paths:
            path_obj = Path(f_path)
            if not path_obj.exists():
                return {"ok": False, "result": {"error": f"File not found: {f_path}"}}
            try:
                content = path_obj.read_text(encoding="utf-8", errors="ignore")
                parsed_contents[f_path] = json.loads(content)
            except json.JSONDecodeError:
                self.logger.info(f"File {f_path} is not valid JSON. Falling back to textual comparison for this file.")
                parsed_contents[f_path] = content  # Store raw text if not JSON
            except Exception as e:
                self.logger.warning(f"Could not read or parse {f_path}: {e}")
                parsed_contents[f_path] = None  # Mark as unreadable

        # Perform comparison
        # Simple case: compare two files
        if len(file_paths) == 2:
            file1, file2 = file_paths[0], file_paths[1]
            content1, content2 = parsed_contents.get(file1), parsed_contents.get(file2)

            if isinstance(content1, dict) and isinstance(content2, dict):
                # Both are JSON, perform semantic diff
                keys1 = set(content1.keys())
                keys2 = set(content2.keys())

                for key in keys1.union(keys2):
                    value1 = content1.get(key)
                    value2 = content2.get(key)
                    if value1 != value2:
                        differences_found.append(
                            {
                                "key": key,
                                "type": "value_mismatch",
                                "values": {file1: value1, file2: value2},
                            }
                        )
            else:
                # Textual diff if not both JSON or parse failed
                lines1 = str(content1).splitlines() if content1 is not None else []
                lines2 = str(content2).splitlines() if content2 is not None else []
                max_lines = max(len(lines1), len(lines2))
                for i in range(max_lines):
                    line_in_file1 = lines1[i].strip() if i < len(lines1) else ""
                    line_in_file2 = lines2[i].strip() if i < len(lines2) else ""
                    if line_in_file1 != line_in_file2:
                        differences_found.append(
                            {
                                "line": i + 1,
                                "type": "textual_mismatch",
                                "values": {file1: line_in_file1, file2: line_in_file2},
                            }
                        )
        else:
            # For more than two files, just compare first to rest textually for simplicity
            base_content = parsed_contents.get(file_paths[0])
            if base_content is None:
                return {
                    "ok": False,
                    "result": {"error": f"Could not read base comparison file: {file_paths[0]}"},
                }

            for i in range(1, len(file_paths)):
                compare_file = file_paths[i]
                compare_content = parsed_contents.get(compare_file)
                if compare_content is None:
                    differences_found.append({"type": "file_unreadable", "file": compare_file})
                    continue

                lines1 = str(base_content).splitlines()
                lines2 = str(compare_content).splitlines()
                max_lines = max(len(lines1), len(lines2))
                for j in range(max_lines):
                    line_in_base = lines1[j].strip() if j < len(lines1) else ""
                    line_in_compare = lines2[j].strip() if j < len(lines2) else ""
                    if line_in_base != line_in_compare:
                        differences_found.append(
                            {
                                "file_pair": f"{file_paths[0]} vs {compare_file}",
                                "line": j + 1,
                                "type": "textual_mismatch",
                                "values": {
                                    file_paths[0]: line_in_base,
                                    compare_file: line_in_compare,
                                },
                            }
                        )

        if differences_found:
            summary = (
                f"Differences detected across {len(file_paths)} files. Found {len(differences_found)} discrepancies."
            )
            status = "differences_found"
        else:
            summary = f"No significant differences detected across {len(file_paths)} files."
            status = "no_differences"

        return {
            "ok": True,
            "result": {
                "status": status,
                "summary": summary,
                "differences": differences_found,
                "files_compared": file_paths,
                "note": "JSON files were compared semantically. Non-JSON files or multi-file comparisons used line-by-line textual diff. Advanced semantic comparison for non-JSON formats is not implemented.",
            },
        }
