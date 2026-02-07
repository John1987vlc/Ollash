from typing import Any, Optional
from src.utils.command_executor import CommandExecutor
# Assuming AgentLogger will be passed during initialization
# from src.agents.code_agent import AgentLogger # This will be changed

class CommandLineTools:
    def __init__(self, command_executor: CommandExecutor, logger: Any):
        self.exec = command_executor
        self.logger = logger

    def run_command(self, command: str, timeout: int = 60):
        """Run shell command"""
        self.logger.info(f"🔧 Running: {command}")
        try:
            r = self.exec.execute(command, timeout)
            if r.stdout:
                preview = r.stdout[:200]
                self.logger.info(f"📤 Output: {preview}")
                if len(r.stdout) > 200:
                    self.logger.info(f"... (truncated)")
            
            return {"ok": r.success, "stdout": r.stdout[:500], "stderr": r.stderr[:500]}
        except Exception as e:
            self.logger.error(f"Command execution error: {e}", e)
            return {"ok": False, "error": str(e)}

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

    def validate_change(self):
        """Validate changes (run tests and lint)"""
        self.logger.info(f"🔍 Validating changes...")
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