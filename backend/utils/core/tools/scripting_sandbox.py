import subprocess
import tempfile
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.exceptions import SandboxUnavailableError

class ScriptingSandbox:
    """
    A persistent Docker sandbox for interactive script development and testing.
    Unlike DockerSandbox which is ephemeral per command, this maintains a container
    session to allow 'create file' -> 'run file' -> 'modify file' workflows.
    """

    def __init__(self, logger: Optional[AgentLogger] = None, image: str = "mcr.microsoft.com/powershell:lts-debian-12"):
        self.logger = logger
        self.image = image
        self.container_name: Optional[str] = None
        self.work_dir: Optional[Path] = None
        self._is_active = False

    def start(self) -> None:
        """Starts the sandbox container."""
        if self._is_active:
            return

        self._check_docker()

        session_id = str(uuid.uuid4())[:8]
        self.container_name = f"ollash_script_env_{session_id}"
        self.work_dir = Path(tempfile.mkdtemp(prefix=f"ollash_script_work_{session_id}_"))

        # Ensure work dir works for Docker mounting (absolute path)
        abs_work_dir = self.work_dir.resolve()

        if self.logger:
            self.logger.info(f"Starting scripting sandbox: {self.container_name}")

        try:
            # Start container in detached mode, keeping it alive with tail -f /dev/null
            subprocess.run(
                [
                    "docker", "run", "-d", "--rm",
                    "--name", self.container_name,
                    "--network", "none", # Network isolation for safety
                    "--memory", "512m",
                    "--cpus", "1",
                    "-v", f"{abs_work_dir}:/workspace",
                    "-w", "/workspace",
                    self.image,
                    "tail", "-f", "/dev/null"
                ],
                check=True,
                capture_output=True
            )
            self._is_active = True
        except subprocess.CalledProcessError as e:
            if self.logger:
                self.logger.error(f"Failed to start sandbox: {e.stderr.decode()}")
            self.stop() # Cleanup if failed
            raise SandboxUnavailableError(["docker"])

    def stop(self) -> None:
        """Stops and removes the sandbox container and temporary directory."""
        if self.container_name:
            if self.logger:
                self.logger.info(f"Stopping sandbox: {self.container_name}")
            try:
                subprocess.run(["docker", "rm", "-f", self.container_name], capture_output=True, timeout=10)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error stopping container: {e}")
            self.container_name = None

        if self.work_dir and self.work_dir.exists():
            try:
                shutil.rmtree(str(self.work_dir), ignore_errors=True)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error cleaning work dir: {e}")
            self.work_dir = None

        self._is_active = False

    def write_file(self, filename: str, content: str) -> None:
        """Writes a file to the sandbox workspace."""
        if not self._is_active or not self.work_dir:
            raise RuntimeError("Sandbox is not active. Call start() first.")

        target_path = self.work_dir / filename
        # Security check: ensure path is within work_dir
        if not str(target_path.resolve()).startswith(str(self.work_dir.resolve())):
             raise ValueError(f"Invalid filename: {filename}")

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

    def execute_command(self, command: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Executes a command inside the running sandbox container."""
        if not self._is_active or not self.container_name:
            raise RuntimeError("Sandbox is not active.")

        if self.logger:
            self.logger.info(f"Executing in sandbox: {' '.join(command)}")

        try:
            # use docker exec to run command in existing container
            exec_cmd = ["docker", "exec", self.container_name] + command

            result = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e)
            }

    def _check_docker(self):
        try:
            subprocess.run(["docker", "info"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise SandboxUnavailableError(["docker"])
