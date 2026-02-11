from typing import Any, Optional
from src.utils.core.command_executor import CommandExecutor
from src.utils.core.tool_decorator import ollash_tool

class CommandLineTools:
    def __init__(self, command_executor: CommandExecutor, logger: Any):
        self.exec = command_executor
        self.logger = logger

    @ollash_tool(
        name="run_command",
        description="Executes a shell command. Use for running scripts, build tools, or any command-line utility.",
        parameters={
            "command": {"type": "string", "description": "The shell command to execute."},
            "timeout": {"type": "integer", "description": "Optional: Maximum time in seconds to wait for the command to complete. Defaults to 300 seconds."}
        },
        toolset_id="command_line_tools",
        agent_types=["code", "system", "cybersecurity"],
        required=["command"]
    )
    def run_command(self, command: str, timeout: int = 60):
        """Run shell command"""
        self.logger.info(f"🔧 Running: {command}")
        try:
            r = self.exec.execute(command, timeout)
            if r.stdout:
                preview = r.stdout[:200]
                self.logger.info(f"📤 Output: {preview}")
                if len(r.stdout) > 200:
                    self.logger.info("... (truncated)")
            
            return {"ok": r.success, "stdout": r.stdout[:500], "stderr": r.stderr[:500]}
        except Exception as e:
            self.logger.error(f"Command execution error: {e}", e)
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="run_tests",
        description="Runs a specified set of tests or all tests in the project. Useful for verifying changes.",
        parameters={
            "test_path": {"type": "string", "description": "Optional: Path to a specific test file or directory. If not provided, runs all tests."},
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional: Additional arguments to pass to the test runner (e.g., ['-k', 'test_my_feature'])."
            }
        },
        toolset_id="command_line_tools",
        agent_types=["code"],
    )
    def run_tests(self, path: Optional[str] = None):
        """Run pytest"""
        cmd = "pytest -q" + (f" {path}" if path else "")
        self.logger.info(f"🧪 Running tests: {cmd}")
        try:
            r = self.exec.execute(cmd, timeout=120)
            status_icon = "✅" if r.success else "❌"
            status_text = "PASSED" if r.success else "FAILED"
            self.logger.info(f"{status_icon} {status_text}")
            return {"ok": r.success, "output": r.stdout[:500]}
        except Exception as e:
            self.logger.error(f"Test execution error: {e}", e)
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="validate_change",
        description="Runs validation checks (e.g., linting, type-checking, tests) on proposed changes. Use before committing or pushing.",
        parameters={
            "target_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional: List of files to validate. If not provided, validates all changed files or the entire project."
            }
        },
        toolset_id="command_line_tools",
        agent_types=["code"],
    )
    def validate_change(self):
        """Validate changes (run tests and lint)"""
        self.logger.info("🔍 Validating changes...")
        try:
            tests = self.exec.execute("pytest -q", timeout=120)
            lint = self.exec.execute("ruff .", timeout=60) # Assuming 'ruff' is available for linting
            
            test_icon = "✅" if tests.success else "❌"
            lint_icon = "✅" if lint.success else "❌"
            
            self.logger.info(f"  Tests: {test_icon}")
            self.logger.info(f"  Lint: {lint_icon}")
            
            return {"tests_ok": tests.success, "lint_ok": lint.success}
        except Exception as e:
            self.logger.error(f"Validation error: {e}", e)
            return {"tests_ok": False, "lint_ok": False, "error": str(e)}