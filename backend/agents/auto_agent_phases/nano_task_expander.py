"""NanoTaskExpander — per-function task decomposition for nano-tier models (≤8B).

Takes a coarse ``implement_function`` backlog task and the current file content
(if any), uses SignatureExtractor to find function stubs, and returns a list
of per-function nano-tasks. Each nano-task carries the exact signature and
docstring so NanoCoder can focus on one body at a time.

No new services, no DI wiring required.
"""

import re as _re
from pathlib import Path
from typing import Any, Dict, List


class NanoTaskExpander:
    """Stateless helper: converts a coarse implement_function task into per-function nano-tasks."""

    # Extensions where stub extraction is meaningful
    _SUPPORTED_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}

    @staticmethod
    def expand(task: Dict[str, Any], existing_content: str = "") -> List[Dict[str, Any]]:
        """Decompose *task* into per-function nano-tasks.

        If *existing_content* is non-empty (file was scaffolded), extract
        function stubs from it. Otherwise fall back to the logic plan
        ``exports`` list carried inside the task dict.

        Args:
            task: A backlog dict with at minimum ``id``, ``file_path``,
                  and optionally ``logic_plan`` with an ``exports`` key.
            existing_content: Current content of the file being generated
                              (may be empty for brand-new files).

        Returns:
            List of nano-task dicts (one per function stub), or an empty list
            if no stubs can be found (caller should fall back to normal task).
        """
        file_path: str = task.get("file_path", "")
        ext = Path(file_path).suffix.lower()

        if ext not in NanoTaskExpander._SUPPORTED_EXTS:
            return []

        # Only expand code implementation tasks
        if task.get("task_type") not in ("implement_function", "create_file"):
            return []

        # Prefer content-derived stubs; fall back to plan exports
        stubs: List[Dict[str, str]] = []
        if existing_content.strip():
            stubs = NanoTaskExpander._extract_stubs_from_content(existing_content, ext)

        if not stubs:
            # Derive stub names from logic plan exports list
            logic_plan = task.get("logic_plan") or {}
            exports = logic_plan.get("exports")

            # If no exports in plan, but it's a code file, we can't expand without stubs
            if not exports or not isinstance(exports, list):
                return []

            stubs = []
            for name in exports:
                if not name or not isinstance(name, str) or name.startswith("_"):
                    continue

                # Deterministic signature based on extension
                if ext == ".py":
                    sig = f"class {name}:" if name[0].isupper() else f"def {name}():"
                elif ext in (".js", ".ts"):
                    sig = f"export class {name}" if name[0].isupper() else f"export function {name}()"
                else:
                    sig = f"function {name}()"

                stubs.append({"name": name, "signature": sig, "docstring": ""})

        if not stubs:
            return []

        base_id = task.get("id", "TASK-000")
        deps = task.get("dependencies", [])

        nano_tasks: List[Dict[str, Any]] = []
        for i, stub in enumerate(stubs):
            nano_id = f"{base_id}-N{i:02d}"
            nano_tasks.append(
                {
                    "id": nano_id,
                    "title": f"Implement {stub['name']} in {file_path}",
                    "description": stub.get("docstring") or f"Implement function body for {stub['name']}",
                    "file_path": file_path,
                    "task_type": "implement_function",
                    "is_nano_subtask": True,
                    "function_name": stub["name"],
                    "function_signature": stub["signature"],
                    "function_docstring": stub.get("docstring", ""),
                    # First subtask inherits parent deps; subsequent ones chain on previous
                    "dependencies": deps if i == 0 else [f"{base_id}-N{i - 1:02d}"],
                    "context_files": task.get("context_files", []),
                }
            )

        return nano_tasks

    @staticmethod
    def _extract_stubs_from_content(content: str, ext: str) -> List[Dict[str, str]]:
        """Extract function stubs from scaffolded file content.

        For Python: parse with ``ast`` to find only public stub functions (body
        is ``pass`` / ``...`` with an optional docstring). For other languages:
        use regex via ``signature_extractor``.

        Args:
            content: Source code of the scaffolded file.
            ext: File extension including leading dot (e.g. ``".py"``).

        Returns:
            List of dicts with keys ``name``, ``signature``, ``docstring``.
        """
        stubs: List[Dict[str, str]] = []

        if ext == ".py":
            try:
                import ast as _ast

                tree = _ast.parse(content)
                for node in _ast.walk(tree):
                    if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                        continue
                    if node.name.startswith("_"):
                        continue
                    # Only include stubs — body must be pass/... (ignoring docstring node)
                    non_expr_body = [n for n in node.body if not isinstance(n, _ast.Expr)]
                    is_stub = not non_expr_body or all(isinstance(n, _ast.Pass) for n in non_expr_body)
                    if not is_stub:
                        continue
                    # Extract leading docstring if present
                    docstring = ""
                    if (
                        node.body
                        and isinstance(node.body[0], _ast.Expr)
                        and isinstance(node.body[0].value, _ast.Constant)
                    ):
                        docstring = str(node.body[0].value.value)
                    # Rebuild signature string
                    args_parts = []
                    for arg in node.args.args:
                        arg_str = arg.arg
                        if arg.annotation:
                            arg_str += f": {_ast.unparse(arg.annotation)}"
                        args_parts.append(arg_str)
                    returns = f" -> {_ast.unparse(node.returns)}" if node.returns else ""
                    prefix = "async def " if isinstance(node, _ast.AsyncFunctionDef) else "def "
                    sig = f"{prefix}{node.name}({', '.join(args_parts)}){returns}:"
                    stubs.append({"name": node.name, "signature": sig, "docstring": docstring})
            except SyntaxError:
                pass
        else:
            try:
                from backend.utils.domains.auto_generation.utilities.signature_extractor import (
                    extract_signatures_regex,
                )

                sig_text = extract_signatures_regex(content, ext)
                for line in sig_text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # Best-effort name extraction from signature line
                    m = _re.search(r"\b(\w+)\s*\(", line)
                    name = m.group(1) if m else "unknown"
                    if name.startswith("_"):
                        continue
                    stubs.append({"name": name, "signature": line, "docstring": ""})
            except Exception:
                pass

        return stubs
