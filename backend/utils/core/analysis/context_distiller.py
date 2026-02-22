import ast
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class ContextDistiller:
    """
    Distills source code into lightweight skeletons (AST-based) to save tokens.
    Extracts only class names, method signatures, docstrings, and imports.
    """

    @staticmethod
    def distill_file(file_path: str, content: str = None) -> str:
        """
        Parses a file and returns a 'skeleton' version.
        Only uses AST for Python files.
        """
        try:
            if content is None:
                # Use a more robust approach to find the file if path is relative
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            
            # CRITICAL: Only use AST for Python files
            if not str(file_path).lower().endswith(".py"):
                # Non-python files: take first 50 lines as summary context
                lines = content.splitlines() if content else []
                return "\n".join(lines[:50]) + ("\n... [truncated]" if len(lines) > 50 else "")

            # For Python files, use AST
            tree = ast.parse(content)
            distilled_lines = []
            
            # Extract Imports
            imports = []
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.append(ast.unparse(node))
            
            if imports:
                distilled_lines.append("# --- Imports ---")
                distilled_lines.extend(imports)
                distilled_lines.append("")

            # Extract Classes and Functions
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    distilled_lines.append(f"class {node.name}:")
                    # Get class docstring
                    doc = ast.get_docstring(node)
                    if doc:
                        distilled_lines.append(f'    """{doc[:100]}..."""')
                    
                    for subnode in node.body:
                        if isinstance(subnode, ast.FunctionDef):
                            args = ast.unparse(subnode.args)
                            distilled_lines.append(f"    def {subnode.name}({args}): ...")
                    distilled_lines.append("")
                
                elif isinstance(node, ast.FunctionDef):
                    args = ast.unparse(node.args)
                    distilled_lines.append(f"def {node.name}({args}): ...")
                    doc = ast.get_docstring(node)
                    if doc:
                        distilled_lines.append(f'    """{doc[:100]}..."""')
                    distilled_lines.append("")

            return "\n".join(distilled_lines)

        except SyntaxError as e:
            logger.warning(f"AST parsing failed for {file_path}, using fallback: {e}")
            # Fallback: first 30 lines
            lines = content.splitlines() if content else []
            return "\n".join(lines[:30]) + "\n... [truncated due to parsing error]"
        except Exception as e:
            logger.error(f"Error distilling context for {file_path}: {e}")
            return f"# Error distilling {file_path}"

    @classmethod
    def distill_batch(cls, files: Dict[str, str]) -> str:
        """Distills multiple files into a single context string."""
        outputs = []
        for path, content in files.items():
            outputs.append(f"### FILE SKELETON: {path}")
            outputs.append(cls.distill_file(path, content))
            outputs.append("-" * 20)
        return "\n".join(outputs)
