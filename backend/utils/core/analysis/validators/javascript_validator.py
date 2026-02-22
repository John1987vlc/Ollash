import re
import shutil
from typing import List

from backend.utils.core.analysis.validators.base_validator import BaseValidator, ValidationResult, ValidationStatus


class JavascriptValidator(BaseValidator):
    """
    Validator for JavaScript files.
    Performs ESLint linting if available, and always executes a Semantic Integrity Check
    to catch logical errors common in LLM-generated game code.
    """

    def __init__(self, logger=None, command_executor=None):
        super().__init__(logger, command_executor)
        self.eslint_available = self._check_eslint_available()

    def _check_eslint_available(self) -> bool:
        """Check if ESLint is available in the system."""
        return shutil.which("eslint") is not None

    def validate(self, file_path: str, content: str, lines: int, chars: int, ext: str) -> ValidationResult:
        """
        Validates JavaScript file content.
        Combines syntactic checks (ESLint/Braces) with Semantic Integrity checks.
        """
        # 1. Syntactic / Linter Validation
        if not self.eslint_available or not self.command_executor:
            if not self.eslint_available and self.logger:
                self.logger.debug(f"  ESLint not available. Using basic JS brace check for {file_path}.")
            syntax_result = self._validate_brace_language(file_path, content, lines, chars)
        else:
            eslint_cmd = [
                "eslint",
                "--no-eslintrc",
                "--parser-options=ecmaVersion:2021",
                "--format=compact",
            ]
            eslint_error_pattern = re.compile(r"^(.*?): line (\d+), col (\d+), (Error|Warning) - (.*)$")
            syntax_result = self._run_linter_command(
                file_path,
                content,
                eslint_cmd,
                "eslint OK",
                lines,
                chars,
                error_pattern=eslint_error_pattern,
                line_col_group_indices=(2, 3),
            )

        # 2. Semantic Integrity Check (The "Self-Reflection" layer)
        integrity_errors = self._semantic_integrity_check(file_path, content)
        
        if integrity_errors:
            # Enforce semantic quality even if syntax is valid
            combined_message = syntax_result.message
            if syntax_result.status == ValidationStatus.VALID:
                combined_message = "Syntax is OK, but logical integrity issues were found:"
            
            error_list = "\n".join([f"- {err}" for i, err in enumerate(integrity_errors[:5])])
            return ValidationResult(
                file_path,
                ValidationStatus.SYNTAX_ERROR,
                f"{combined_message}\n{error_list}",
                lines,
                chars
            )

        return syntax_result

    def _semantic_integrity_check(self, file_path: str, content: str) -> List[str]:
        """
        Heuristic-based check for common LLM failures in JS.
        """
        errors = []
        
        # A. DOM Integrity: document.getElementById usage
        # Pattern: const x = document.getElementById('...'); x.innerHTML = ... (WITHOUT null check)
        dom_accesses = re.findall(r"(?:const|let|var)\s+(\w+)\s*=\s*document\.getElementById", content)
        for var_name in dom_accesses:
            # Check if there is an 'if (var_name)' or 'var_name ?' or 'var_name &&' nearby
            if not re.search(rf"if\s*\(\s*{var_name}\s*\)|{var_name}\s*\?|{var_name}\s*&&", content):
                # Optimization: check if it's used immediately with dot notation without optional chaining
                if re.search(rf"{var_name}\.(?!\?)", content):
                    errors.append(f"Potential crash: Using DOM element '{var_name}' without null check. Use 'if({var_name})' or optional chaining.")

        # B. Global Scope Pollution: implicit globals
        # Pattern: x = 10; (at the start of a line, not inside a string/comment)
        # Note: Very simplified heuristic
        implicit_globals = re.findall(r"^(?!\s*(?:const|let|var|function|class|if|for|while|return|export|import|//|/\*))\s*([a-zA-Z_$][\w$]*)\s*=", content, re.MULTILINE)
        for glob in implicit_globals:
            if glob not in ["window", "console", "module", "exports", "document"]:
                errors.append(f"Implicit global variable '{glob}'. Use 'const', 'let', or 'var' to declare it.")

        # C. Domain Specific: Poker Logic Consistency
        is_poker_file = any(kw in file_path.lower() or kw in content.lower() for kw in ["poker", "hand", "deck", "card"])
        if is_poker_file:
            # Core functions expected in a game logic file
            core_patterns = {
                "shuffle": r"function\s+shuffle|shuffle\s*=\s*\(|shuffle\s*:",
                "deal": r"function\s+deal|deal\s*=\s*\(|deal\s*:",
                "evaluate": r"evaluate|handValue|rank"
            }
            
            # If it looks like a GameEngine or HandEvaluator, check for specifics
            if "engine" in file_path.lower() or "engine" in content.lower():
                if not re.search(core_patterns["shuffle"], content, re.I):
                    errors.append("Poker logic missing 'shuffle' function.")
                if not re.search(core_patterns["deal"], content, re.I):
                    errors.append("Poker logic missing 'deal' function.")
            
            if "evaluator" in file_path.lower() or "hand" in content.lower():
                if not re.search(core_patterns["evaluate"], content, re.I):
                    errors.append("Hand evaluation logic seems incomplete (no evaluation function found).")

        return errors
