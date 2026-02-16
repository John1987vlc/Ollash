"""
Proactive Refactoring Analyzer

Analyzes generated code for SOLID principle violations and technical debt,
suggesting design improvements.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List

from backend.utils.core.agent_logger import AgentLogger


@dataclass
class SolidViolation:
    """A detected SOLID principle violation."""

    principle: str  # "SRP", "OCP", "LSP", "ISP", "DIP"
    file_path: str
    description: str
    severity: str  # "low", "medium", "high"
    line_range: str = ""
    code_snippet: str = ""
    confidence: float = 0.7

    def to_dict(self) -> Dict[str, Any]:
        return {
            "principle": self.principle,
            "file_path": self.file_path,
            "description": self.description,
            "severity": self.severity,
            "line_range": self.line_range,
            "code_snippet": self.code_snippet,
            "confidence": self.confidence,
        }


@dataclass
class RefactoringSuggestion:
    """A refactoring suggestion based on violations."""

    violation: SolidViolation
    suggested_change: str
    rationale: str
    effort: str = "medium"  # "low", "medium", "high"
    priority: int = 5  # 1 (highest) to 10 (lowest)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "violation": self.violation.to_dict(),
            "suggested_change": self.suggested_change,
            "rationale": self.rationale,
            "effort": self.effort,
            "priority": self.priority,
        }


# Heuristic thresholds for Python analysis
MAX_CLASS_METHODS = 15  # SRP: classes with too many methods
MAX_METHOD_LINES = 50  # SRP: methods that are too long
MAX_PARAMETERS = 6  # ISP: functions with too many parameters
MAX_IMPORTS = 20  # DIP: too many concrete imports


class RefactoringAnalyzer:
    """Analyzes code for SOLID violations using heuristic analysis.

    Uses pattern matching and code metrics to detect potential violations.
    For deeper analysis, LLM-based review is used in the RefactoringPhase.
    """

    def __init__(self, logger: AgentLogger):
        self.logger = logger

    def analyze_solid(self, file_path: str, content: str, language: str = "python") -> List[SolidViolation]:
        """Analyze a file for SOLID principle violations."""
        violations = []

        if language == "python":
            violations.extend(self._check_srp_python(file_path, content))
            violations.extend(self._check_isp_python(file_path, content))
            violations.extend(self._check_dip_python(file_path, content))
        elif language in ("javascript", "typescript"):
            violations.extend(self._check_srp_js(file_path, content))

        return violations

    def _check_srp_python(self, file_path: str, content: str) -> List[SolidViolation]:
        """Check Single Responsibility Principle for Python."""
        violations = []
        lines = content.split("\n")

        # Check for classes with too many methods
        class_methods: Dict[str, int] = {}
        current_class = None

        for i, line in enumerate(lines):
            class_match = re.match(r"^class\s+(\w+)", line)
            if class_match:
                current_class = class_match.group(1)
                class_methods[current_class] = 0

            if current_class and re.match(r"^\s+def\s+\w+", line):
                class_methods[current_class] += 1

        for cls_name, method_count in class_methods.items():
            if method_count > MAX_CLASS_METHODS:
                violations.append(
                    SolidViolation(
                        principle="SRP",
                        file_path=file_path,
                        description=f"Class '{cls_name}' has {method_count} methods "
                        f"(threshold: {MAX_CLASS_METHODS}). Consider splitting responsibilities.",
                        severity="medium" if method_count < 25 else "high",
                        confidence=0.8,
                    )
                )

        # Check for functions/methods that are too long
        func_name = None
        func_start = 0

        for i, line in enumerate(lines):
            func_match = re.match(r"^(\s*)def\s+(\w+)", line)
            if func_match:
                if func_name and (i - func_start) > MAX_METHOD_LINES:
                    violations.append(
                        SolidViolation(
                            principle="SRP",
                            file_path=file_path,
                            description=f"Function '{func_name}' is {i - func_start} lines long "
                            f"(threshold: {MAX_METHOD_LINES}). Consider breaking it down.",
                            severity="low" if (i - func_start) < 80 else "medium",
                            line_range=f"{func_start + 1}-{i}",
                            confidence=0.7,
                        )
                    )
                func_name = func_match.group(2)
                func_start = i
                len(func_match.group(1))

        # Check last function
        if func_name and (len(lines) - func_start) > MAX_METHOD_LINES:
            violations.append(
                SolidViolation(
                    principle="SRP",
                    file_path=file_path,
                    description=f"Function '{func_name}' is {len(lines) - func_start} lines long.",
                    severity="medium",
                    line_range=f"{func_start + 1}-{len(lines)}",
                    confidence=0.7,
                )
            )

        return violations

    def _check_isp_python(self, file_path: str, content: str) -> List[SolidViolation]:
        """Check Interface Segregation Principle for Python."""
        violations = []

        # Check for functions with too many parameters
        for match in re.finditer(r"def\s+(\w+)\s*\(([^)]*)\)", content):
            func_name = match.group(1)
            params = match.group(2)
            param_list = [p.strip() for p in params.split(",") if p.strip() and p.strip() != "self"]

            if len(param_list) > MAX_PARAMETERS:
                violations.append(
                    SolidViolation(
                        principle="ISP",
                        file_path=file_path,
                        description=f"Function '{func_name}' has {len(param_list)} parameters "
                        f"(threshold: {MAX_PARAMETERS}). Consider using a config object or kwargs.",
                        severity="low" if len(param_list) < 10 else "medium",
                        confidence=0.6,
                    )
                )

        return violations

    def _check_dip_python(self, file_path: str, content: str) -> List[SolidViolation]:
        """Check Dependency Inversion Principle for Python."""
        violations = []

        # Count concrete imports (not from abc or interfaces)
        import_count = 0
        for line in content.split("\n"):
            if re.match(r"^(?:from|import)\s+", line):
                # Skip abstract/interface imports
                if "abc" in line or "interface" in line.lower() or "typing" in line:
                    continue
                import_count += 1

        if import_count > MAX_IMPORTS:
            violations.append(
                SolidViolation(
                    principle="DIP",
                    file_path=file_path,
                    description=f"File has {import_count} concrete imports "
                    f"(threshold: {MAX_IMPORTS}). Consider depending on abstractions.",
                    severity="low",
                    confidence=0.5,
                )
            )

        return violations

    def _check_srp_js(self, file_path: str, content: str) -> List[SolidViolation]:
        """Check SRP for JavaScript/TypeScript files."""
        violations = []
        lines = content.split("\n")

        # Check file length as a proxy for SRP
        if len(lines) > 300:
            violations.append(
                SolidViolation(
                    principle="SRP",
                    file_path=file_path,
                    description=f"File is {len(lines)} lines. Consider splitting into modules.",
                    severity="low" if len(lines) < 500 else "medium",
                    confidence=0.5,
                )
            )

        # Check for large functions
        func_start = None
        func_name = ""
        brace_depth = 0

        for i, line in enumerate(lines):
            func_match = re.match(r".*(?:function|const|let|var)\s+(\w+)\s*(?:=\s*)?(?:\(|=>)", line)
            if func_match and func_start is None:
                func_name = func_match.group(1)
                func_start = i

            if func_start is not None:
                brace_depth += line.count("{") - line.count("}")
                if brace_depth <= 0 and i > func_start:
                    length = i - func_start
                    if length > MAX_METHOD_LINES:
                        violations.append(
                            SolidViolation(
                                principle="SRP",
                                file_path=file_path,
                                description=f"Function '{func_name}' is {length} lines long.",
                                severity="medium",
                                line_range=f"{func_start + 1}-{i + 1}",
                                confidence=0.6,
                            )
                        )
                    func_start = None
                    brace_depth = 0

        return violations

    def suggest_refactoring(self, violations: List[SolidViolation]) -> List[RefactoringSuggestion]:
        """Generate refactoring suggestions from violations."""
        suggestions = []

        for v in violations:
            if v.principle == "SRP" and "class" in v.description.lower():
                suggestions.append(
                    RefactoringSuggestion(
                        violation=v,
                        suggested_change="Extract cohesive method groups into separate classes using composition.",
                        rationale="Large classes often have multiple reasons to change, violating SRP.",
                        effort="high",
                        priority=3,
                    )
                )
            elif v.principle == "SRP" and "function" in v.description.lower():
                suggestions.append(
                    RefactoringSuggestion(
                        violation=v,
                        suggested_change="Break the function into smaller, focused helper functions.",
                        rationale="Long functions are harder to test, understand, and maintain.",
                        effort="medium",
                        priority=4,
                    )
                )
            elif v.principle == "ISP":
                suggestions.append(
                    RefactoringSuggestion(
                        violation=v,
                        suggested_change="Group related parameters into a dataclass or TypedDict.",
                        rationale="Many parameters suggest the function handles multiple concerns.",
                        effort="low",
                        priority=5,
                    )
                )
            elif v.principle == "DIP":
                suggestions.append(
                    RefactoringSuggestion(
                        violation=v,
                        suggested_change="Introduce abstract interfaces and use dependency injection.",
                        rationale="Depending on concrete implementations makes code rigid.",
                        effort="high",
                        priority=6,
                    )
                )

        return suggestions
