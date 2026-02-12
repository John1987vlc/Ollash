import re
import shutil
import tempfile
from pathlib import Path
from src.utils.core.validators.base_validator import BaseValidator, ValidationResult, ValidationStatus


class TypescriptValidator(BaseValidator):
    """Validator for TypeScript files, integrating ESLint with TypeScript parser."""

    def __init__(self, logger=None, command_executor=None):
        super().__init__(logger, command_executor)
        self.eslint_available = self._check_eslint_available()

    def _check_eslint_available(self) -> bool:
        """Check if ESLint is available in the system."""
        return shutil.which("eslint") is not None

    def validate(self, file_path: str, content: str, lines: int, chars: int, ext: str) -> ValidationResult:
        """
        Validates TypeScript file content using ESLint with TypeScript parser, or falls back to basic checks.
        """
        # If ESLint is not available, use basic checks
        if not self.eslint_available or not self.command_executor:
            if not self.eslint_available and self.logger:
                self.logger.debug(f"  ESLint not available. Using basic TS brace check for {file_path}.")
            return self._validate_brace_language(file_path, content, lines, chars)

        # Check if tsconfig.json exists or create a minimal one for eslint to work with TypeScript
        # This will be created in the current working directory of the command executor.
        tsconfig_path = Path(self.command_executor.working_dir) / "tsconfig.json"
        temp_tsconfig = False
        if not tsconfig_path.exists():
            temp_tsconfig = True
            minimal_tsconfig_content = """
            {
              "compilerOptions": {
                "target": "es2021",
                "module": "commonjs",
                "jsx": "react",
                "strict": true,
                "esModuleInterop": true,
                "skipLibCheck": true,
                "forceConsistentCasingInFileNames": true,
                "lib": ["es2021", "dom"]
              },
              "include": ["**/*.ts", "**/*.tsx"]
            }
            """
            with open(tsconfig_path, "w", encoding="utf-8") as f:
                f.write(minimal_tsconfig_content)
            if self.logger: self.logger.info(f"  Created temporary tsconfig.json for TypeScript linting at {tsconfig_path}")


        eslint_cmd = ["eslint", "--no-eslintrc", "--parser-options=ecmaVersion:2021,sourceType:module,project:./tsconfig.json", "--ext=.ts,.tsx", "--format=compact"]
        eslint_error_pattern = re.compile(r'^(.*?): line (\d+), col (\d+), (Error|Warning) - (.*)$')
        
        eslint_result = self._run_linter_command(
            file_path, content, eslint_cmd, "eslint (TypeScript) OK", lines, chars,
            error_pattern=eslint_error_pattern, line_col_group_indices=(2, 3)
        )

        if temp_tsconfig and tsconfig_path.exists():
            tsconfig_path.unlink() # Clean up temporary tsconfig.json
            if self.logger: self.logger.info(f"  Removed temporary tsconfig.json at {tsconfig_path}")


        if eslint_result.status == ValidationStatus.VALID:
            return ValidationResult(file_path, ValidationStatus.VALID, "TypeScript syntax and linting OK", lines, chars)
        elif "command not found" in eslint_result.message.lower() or "not recognized" in eslint_result.message.lower():
            if self.logger: self.logger.warning(f"  eslint not found for {file_path}. Falling back to basic TS brace check.")
            self.eslint_available = False
            return self._validate_brace_language(file_path, content, lines, chars)
        else:
            return eslint_result