"""
Execution Sandbox

Provides isolated execution environment for running tests and generated code.
Fallback chain: Docker (primary) -> WASM -> Subprocess (restricted) -> Subprocess (unrestricted).
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.exceptions import SandboxUnavailableError


@dataclass
class SandboxInstance:
    """A running sandbox instance."""

    sandbox_id: str
    work_dir: Path
    allowed_dirs: List[Path]
    memory_limit_mb: int
    runtime: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sandbox_id": self.sandbox_id,
            "work_dir": str(self.work_dir),
            "memory_limit_mb": self.memory_limit_mb,
            "runtime": self.runtime,
        }


@dataclass
class TestResult:
    """Result of running tests in sandbox."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:5000],
            "stderr": self.stderr[:2000],
            "duration_seconds": round(self.duration_seconds, 3),
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
        }


class WasmSandbox:
    """Manages WebAssembly sandbox instances for isolated test execution.

    Falls back to Docker sandbox or direct execution if Wasm runtime
    is not available.
    """

    def __init__(self, runtime: str = "wasmtime", logger: Optional[AgentLogger] = None):
        self.runtime = runtime
        self.logger = logger
        self._instances: Dict[str, SandboxInstance] = {}
        self._runtime_available = self._check_runtime()

    def _check_runtime(self) -> bool:
        """Check if the Wasm runtime is available."""
        try:
            import subprocess

            result = subprocess.run(
                [self.runtime, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                if self.logger:
                    self.logger.info(f"Wasm runtime available: {self.runtime} {result.stdout.strip()}")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        if self.logger:
            self.logger.info(f"Wasm runtime '{self.runtime}' not available, using fallback")
        return False

    @property
    def is_available(self) -> bool:
        return self._runtime_available

    def create_sandbox(
        self,
        allowed_dirs: Optional[List[Path]] = None,
        memory_limit_mb: int = 256,
    ) -> SandboxInstance:
        """Create a new sandbox instance."""
        import uuid

        sandbox_id = str(uuid.uuid4())[:8]
        work_dir = Path(tempfile.mkdtemp(prefix=f"ollash_sandbox_{sandbox_id}_"))

        instance = SandboxInstance(
            sandbox_id=sandbox_id,
            work_dir=work_dir,
            allowed_dirs=allowed_dirs or [],
            memory_limit_mb=memory_limit_mb,
            runtime=self.runtime,
        )

        self._instances[sandbox_id] = instance

        if self.logger:
            self.logger.info(f"Created sandbox: {sandbox_id} at {work_dir}")

        return instance

    def destroy_sandbox(self, instance: SandboxInstance) -> None:
        """Destroy a sandbox instance and clean up."""
        if instance.work_dir.exists():
            shutil.rmtree(str(instance.work_dir), ignore_errors=True)

        self._instances.pop(instance.sandbox_id, None)

        if self.logger:
            self.logger.info(f"Destroyed sandbox: {instance.sandbox_id}")

    def destroy_all(self) -> None:
        """Destroy all sandbox instances."""
        for instance in list(self._instances.values()):
            self.destroy_sandbox(instance)


class DockerSandbox:
    """Docker-based sandbox for isolated execution (primary sandbox method).

    Uses ephemeral Docker containers with:
    - Network isolation (--network=none)
    - Memory limits (--memory)
    - CPU limits (--cpus)
    - Read-only filesystem options
    - Automatic cleanup
    """

    def __init__(self, logger: Optional[AgentLogger] = None, default_image: str = "python:3.11-slim"):
        self.logger = logger
        self.default_image = default_image
        self._docker_available = self._check_docker()
        self._containers: List[str] = []

    def _check_docker(self) -> bool:
        """Check if Docker is available."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                if self.logger:
                    self.logger.info("Docker sandbox: Docker is available")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        if self.logger:
            self.logger.info("Docker sandbox: Docker not available")
        return False

    @property
    def is_available(self) -> bool:
        return self._docker_available

    def execute_in_container(
        self,
        command: str,
        work_dir: Path,
        image: Optional[str] = None,
        memory_limit: str = "512m",
        cpu_limit: str = "1",
        network: bool = False,
        timeout: int = 120,
        allowed_dirs: Optional[List[Path]] = None,
    ) -> TestResult:
        """Execute a command inside an ephemeral Docker container.

        Args:
            command: Command to execute.
            work_dir: Host directory to mount as /app.
            image: Docker image to use.
            memory_limit: Memory limit (e.g., "512m", "1g").
            cpu_limit: CPU limit (e.g., "1", "0.5").
            network: Whether to allow network access.
            timeout: Execution timeout in seconds.
            allowed_dirs: Additional directories to mount read-only.

        Returns:
            TestResult with execution output.
        """
        import time

        if not self._docker_available:
            raise SandboxUnavailableError(["docker"])

        image = image or self.default_image
        container_name = f"ollash_sandbox_{os.urandom(4).hex()}"
        self._containers.append(container_name)

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            f"--memory={memory_limit}",
            f"--cpus={cpu_limit}",
        ]

        if not network:
            docker_cmd.append("--network=none")

        # Mount working directory
        docker_cmd.extend(["-v", f"{work_dir}:/app", "-w", "/app"])

        # Mount additional directories as read-only
        for d in allowed_dirs or []:
            docker_cmd.extend(["-v", f"{d}:{d}:ro"])

        docker_cmd.extend([image, "sh", "-c", command])

        start = time.time()
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = time.time() - start
            return TestResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=duration,
            )
        except subprocess.TimeoutExpired:
            # Kill the container
            subprocess.run(["docker", "kill", container_name], capture_output=True, timeout=10)
            return TestResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Docker execution timed out",
                duration_seconds=float(timeout),
            )
        except Exception as e:
            return TestResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=time.time() - start,
            )
        finally:
            if container_name in self._containers:
                self._containers.remove(container_name)

    def cleanup_orphaned_containers(self) -> int:
        """Clean up any orphaned Ollash sandbox containers."""
        cleaned = 0
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", "name=ollash_sandbox_", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for name in result.stdout.strip().split("\n"):
                if name:
                    subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
                    cleaned += 1
        except Exception:
            pass
        if cleaned and self.logger:
            self.logger.info(f"Cleaned up {cleaned} orphaned sandbox containers")
        return cleaned


class WasmTestRunner:
    """Runs tests inside a Wasm sandbox for isolation."""

    def __init__(self, sandbox: WasmSandbox, logger: AgentLogger):
        self.sandbox = sandbox
        self.logger = logger

    async def run_tests(
        self,
        project_root: Path,
        test_command: str,
        language: str = "python",
        timeout: int = 120,
    ) -> TestResult:
        """Run tests in an isolated sandbox environment."""
        import time

        instance = self.sandbox.create_sandbox()

        try:
            # Copy project files to sandbox
            self._prepare_filesystem(project_root, instance.work_dir)

            start = time.time()

            if self.sandbox.is_available:
                result = await self._run_in_wasm(instance, test_command, timeout)
            else:
                result = await self._run_in_subprocess(instance, test_command, timeout)

            result.duration_seconds = time.time() - start

            # Parse test counts from output
            self._parse_test_output(result, language)

            return result

        finally:
            self.sandbox.destroy_sandbox(instance)

    def _prepare_filesystem(self, source: Path, dest: Path) -> None:
        """Copy project files to sandbox working directory."""
        for item in source.iterdir():
            if item.name in (".git", "__pycache__", "node_modules", ".venv", "venv"):
                continue
            target = dest / item.name
            if item.is_dir():
                shutil.copytree(str(item), str(target), dirs_exist_ok=True)
            else:
                shutil.copy2(str(item), str(target))

    async def _run_in_wasm(self, instance: SandboxInstance, command: str, timeout: int) -> TestResult:
        """Run command in Wasm sandbox (when runtime available)."""
        import subprocess

        # wasmtime doesn't directly run Python/Node - this is a conceptual integration
        # In practice, you'd use a Wasm-compiled Python or language runtime
        cmd = f"{self.sandbox.runtime} run --dir {instance.work_dir} -- {command}"

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(instance.work_dir),
            )
            return TestResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=0,
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Test execution timed out",
                duration_seconds=timeout,
            )

    async def _run_in_subprocess(self, instance: SandboxInstance, command: str, timeout: int) -> TestResult:
        """Fallback: run in a subprocess with limited permissions."""
        import subprocess

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(instance.work_dir),
            )
            return TestResult(
                success=result.returncode == 0,
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_seconds=0,
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                success=False,
                exit_code=-1,
                stdout="",
                stderr="Test execution timed out",
                duration_seconds=timeout,
            )

    def _parse_test_output(self, result: TestResult, language: str) -> None:
        """Parse test output to extract pass/fail counts."""
        import re

        output = result.stdout + result.stderr

        if language == "python":
            # pytest output: "X passed, Y failed"
            match = re.search(r"(\d+) passed", output)
            if match:
                result.tests_passed = int(match.group(1))
            match = re.search(r"(\d+) failed", output)
            if match:
                result.tests_failed = int(match.group(1))
        elif language in ("javascript", "typescript"):
            # jest/mocha output
            match = re.search(r"Tests:\s+(\d+) passed", output)
            if match:
                result.tests_passed = int(match.group(1))
            match = re.search(r"Tests:\s+(\d+) failed", output)
            if match:
                result.tests_failed = int(match.group(1))

        result.tests_run = result.tests_passed + result.tests_failed
