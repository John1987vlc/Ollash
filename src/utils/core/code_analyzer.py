import ast
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class Language(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    HTML = "html"
    CSS = "css"
    JAVA = "java"
    CSHARP = "csharp"
    CPP = "cpp"
    C = "c"
    UNKNOWN = "unknown"


@dataclass
class CodeInfo:
    """Información extraída del código."""
    language: Language
    functions: List[str]
    classes: List[str]
    imports: List[str]
    dependencies: List[str]
    line_count: int
    has_tests: bool
    has_docs: bool
    file_path: str


class CodeAnalyzer:
    """Analiza estructura de código."""

    EXTENSION_MAP = {
        ".py": Language.PYTHON,
        ".js": Language.JAVASCRIPT,
        ".ts": Language.TYPESCRIPT,
        ".html": Language.HTML,
        ".css": Language.CSS,
        ".java": Language.JAVA,
        ".cs": Language.CSHARP,
        ".cpp": Language.CPP,
        ".c": Language.C,
    }

    def __init__(self, project_root: str = None):
        self.root = Path(project_root) if project_root else Path.cwd()

    def detect_language(self, file_path: str) -> Language:
        """Detecta el lenguaje por extensión."""
        ext = Path(file_path).suffix.lower()
        return self.EXTENSION_MAP.get(ext, Language.UNKNOWN)

    def analyze_python(self, file_path: str) -> CodeInfo:
        """Analiza código Python."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)

        functions = []
        classes = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                else:
                    imports.append(node.module or "")

        has_docs = '"""' in content or "'''" in content
        has_tests = "test" in file_path.lower() or "spec" in file_path.lower()

        return CodeInfo(
            language=Language.PYTHON,
            functions=functions,
            classes=classes,
            imports=imports,
            dependencies=self._extract_python_deps(content),
            line_count=len(content.splitlines()),
            has_tests=has_tests,
            has_docs=has_docs,
            file_path=file_path
        )

    def _extract_python_deps(self, content: str) -> List[str]:
        """Extrae dependencias de requirements."""
        deps = []
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("import ") or line.startswith("from "):
                pkg = line.split()[1].split(".")[0]
                if pkg and not pkg.startswith("_"):
                    deps.append(pkg)
        return list(set(deps))

    def analyze_file(self, file_path: str) -> CodeInfo:
        """Analiza un archivo según su tipo."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        lang = self.detect_language(file_path)

        if lang == Language.PYTHON:
            return self.analyze_python(file_path)

        return CodeInfo(
            language=lang,
            functions=[],
            classes=[],
            imports=[],
            dependencies=[],
            line_count=path.stat().st_size,
            has_tests=False,
            has_docs=False,
            file_path=str(path)
        )

    def scan_project(self) -> Dict[str, CodeInfo]:
        """Escanea todo el proyecto."""
        results = {}
        for py_file in self.root.rglob("*.py"):
            if "venv" not in str(py_file) and "__pycache__" not in str(py_file):
                try:
                    results[str(py_file)] = self.analyze_python(str(py_file))
                except (SyntaxError, UnicodeDecodeError, OSError):
                    pass  # Skip files that can't be parsed or read
        return results

    def get_project_stats(self) -> Dict[str, Any]:
        """Estadísticas del proyecto."""
        files = self.scan_project()
        total_lines = sum(f.line_count for f in files.values())
        total_files = len(files)

        return {
            "total_files": total_files,
            "total_lines": total_lines,
            "total_functions": len(set(f for info in files.values() for f in info.functions)),
            "total_classes": len(set(f for info in files.values() for f in info.classes)),
            "languages": list(set(info.language.value for info in files.values())),
            "test_coverage": sum(1 for f in files.values() if f.has_tests) / max(total_files, 1) * 100
        }
