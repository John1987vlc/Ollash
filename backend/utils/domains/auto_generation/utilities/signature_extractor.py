"""Signature extraction helpers for the Signature-Only RAG feature.

Extracted from ``phase_context.py`` (module-level helpers). Kept as pure
functions with no I/O dependencies so they can be tested and reused
independently of the full PhaseContext object.
"""

import ast
import re as _re
from pathlib import Path
from typing import Dict, List


def extract_signatures_regex(content: str, ext: str) -> List[str]:
    """Regex-based signature extraction for non-Python or unparseable files.

    Parameters
    ----------
    content:
        Raw source text of the file.
    ext:
        Lowercase file extension including the dot (e.g. ``".ts"``).

    Returns
    -------
    List of matched signature lines.
    """
    patterns: Dict[str, List[str]] = {
        ".ts": [
            r"^(?:export\s+)?(?:async\s+)?function\s+\w+\s*\([^)]*\)\s*(?::\s*\S+)?\s*\{",
            r"^(?:export\s+)?(?:abstract\s+)?class\s+\w+(?:\s+extends\s+\w+)?(?:\s+implements\s+\S+)?\s*\{",
            r"^\s*(?:public|private|protected)?\s*(?:async\s+)?\w+\s*\([^)]*\)\s*(?::\s*\S+)?\s*\{",
        ],
        ".js": [
            r"^(?:export\s+)?(?:async\s+)?function\s+\w+\s*\([^)]*\)\s*\{",
            r"^(?:export\s+)?class\s+\w+(?:\s+extends\s+\w+)?\s*\{",
            r"^(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\([^)]*\)\s*=>",
        ],
        ".go": [
            r"^func\s+(?:\(\w+\s+\*?\w+\)\s+)?\w+\s*\([^)]*\)\s*(?:\([^)]*\)|\S+)?\s*\{",
            r"^type\s+\w+\s+(?:struct|interface)\s*\{",
        ],
        ".rs": [
            r"^pub\s+(?:async\s+)?fn\s+\w+.*?->",
            r"^(?:pub\s+)?struct\s+\w+",
            r"^(?:pub\s+)?trait\s+\w+",
        ],
    }
    used = patterns.get(ext, [r"(?:function|class|def)\s+\w+\s*\("])
    found: List[str] = []
    for line in content.splitlines():
        for pat in used:
            if _re.match(pat, line.strip()):
                found.append(line.rstrip())
                break
    return found


def extract_signatures(content: str, file_path: str) -> str:
    """Extract function/class signatures from source code.

    For Python files uses ``ast.parse()`` for accuracy; for other languages
    uses regex heuristics. Returns ``content[:500]`` if no signatures are found,
    so callers always receive something useful.

    Parameters
    ----------
    content:
        Source file content.
    file_path:
        File path (used to infer language by extension).

    Returns
    -------
    Newline-separated signature lines, or the first 500 chars as fallback.
    """
    ext = Path(file_path).suffix.lower()
    lines: List[str] = []

    if ext == ".py":
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    args_parts = []
                    for arg in node.args.args:
                        arg_str = arg.arg
                        if arg.annotation:
                            arg_str += f": {ast.unparse(arg.annotation)}"
                        args_parts.append(arg_str)
                    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
                    lines.append(f"{prefix}{node.name}({', '.join(args_parts)}){returns}:")
                elif isinstance(node, ast.ClassDef):
                    bases = ", ".join(ast.unparse(b) for b in node.bases)
                    lines.append(f"class {node.name}({bases}):")
        except SyntaxError:
            lines = extract_signatures_regex(content, ext)
    else:
        lines = extract_signatures_regex(content, ext)

    return "\n".join(lines) if lines else content[:500]
