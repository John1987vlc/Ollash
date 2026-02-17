import asyncio
import os
import py_compile
import shlex
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional

import docker  # ADDED
from docker.errors import APIError, ContainerError, ImageNotFound  # ADDED


class SandboxLevel(Enum):
    """Nivel de restricción para ejecución."""

    NONE = "none"  # Sin restricciones
    LIMITED = "limited"  # Solo directorio del proyecto
    STRICT = "strict"  # Solo comandos whitelist


@dataclass
class ExecutionResult:
    """Resultado de ejecución de comando."""

    success: bool
    stdout: str
    stderr: str
    return_code: int
    command: str


class CommandExecutor:
    """Ejecuta comandos de forma controlada."""

    def __init__(
        self,
        working_dir: str = None,
        sandbox: SandboxLevel = SandboxLevel.NONE,
        logger: Any = None,
        policy_manager: Any = None,
        use_docker_sandbox: bool = False,
    ):
        self.working_dir = working_dir or os.getcwd()
        self.sandbox = sandbox
        self.logger = logger  # Store logger instance
        self.policy_manager = policy_manager  # Store policy_manager instance
        self.use_docker_sandbox = use_docker_sandbox
        self.docker_client = None
        if self.use_docker_sandbox:
            try:
                self.docker_client = docker.from_env()
                self.logger.info("Docker client initialized successfully.")
            except Exception as e:
                self.logger.error(f"Failed to initialize Docker client: {e}. Docker sandboxing will be disabled.")
                self.use_docker_sandbox = False

    def _is_allowed(self, command: str | List[str]) -> bool:
        """Verifica si el comando está permitido y sanitiza argumentos usando PolicyManager."""
        if self.sandbox == SandboxLevel.NONE:
            return True

        if not self.policy_manager:
            if self.logger:
                self.logger.error(
                    "CommandExecutor is in sandboxed mode but no PolicyManager is configured. Denying all commands for safety."
                )
            return False  # Always deny if in sandbox and no policy manager

        # Extract base command and args for PolicyManager
        base_cmd: str
        args: List[str]

        if isinstance(command, str):
            if os.name == "nt" and command.strip().lower().startswith("powershell"):
                # For PowerShell, the entire command string is the 'command', subsequent parts are args to it
                base_cmd = command.split(" ")[0].lower()
                args = shlex.split(command)[1:]  # For argument checks, shlex.split is safer
            else:
                try:
                    parts = shlex.split(command)
                    base_cmd = parts[0].lower()
                    args = parts[1:]
                except ValueError as e:
                    if self.logger:
                        self.logger.warning(f"Error parsing command with shlex: {e}. Command: '{command}'")
                    return False
        else:  # command is already a list
            base_cmd = command[0].lower()
            args = command[1:]

        return self.policy_manager.is_command_allowed(base_cmd, args)

    def _pre_validate_command(self, command: str | List[str]) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Performs a pre-validation (dry run) of the command.
        Returns (is_valid, suggested_correction, error_message).
        """
        command_str = shlex.join(command) if isinstance(command, list) else command

        # Basic typo correction
        if command_str.strip().startswith("pyton "):
            suggested = command_str.replace("pyton", "python", 1)
            return False, suggested, "Typo detected: 'pyton' should be 'python'."

        # Python syntax check using py_compile
        if command_str.strip().startswith("python "):
            parts = shlex.split(command_str)
            if len(parts) > 1 and parts[1].endswith(".py"):
                script_path = Path(self.working_dir) / parts[1]
                if script_path.exists():
                    try:
                        py_compile.compile(str(script_path), doraise=True)
                    except py_compile.PyCompileError as e:
                        return (
                            False,
                            None,
                            f"Python syntax error in '{script_path}': {e}",
                        )

        return True, None, None

    def execute(
        self,
        command: str | List[str],
        timeout: int = 60,
        dir_path: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Ejecuta un comando y retorna el resultado.
        Prefiere shell=False para seguridad, pero puede usar shell=True si command es un string
        y es una llamada a powershell en Windows.
        """
        use_shell = False
        command_list: List[str]
        original_command = command
        execution_dir = dir_path or self.working_dir

        if isinstance(command, str):
            # Special handling for Windows PowerShell calls
            if os.name == "nt" and command.strip().lower().startswith("powershell"):
                use_shell = True  # PowerShell requires shell=True for some complex cmdlets via string
                command_list = command  # Pass as string
            else:
                try:
                    command_list = shlex.split(command)
                except ValueError as e:
                    if self.logger:
                        self.logger.error(f"Error splitting command with shlex: {e}. Command: '{command}'")
                    return ExecutionResult(False, "", str(e), 1, command)
        else:  # command is already a list
            command_list = command

        # Pre-validation
        is_valid, suggestion, error_msg = self._pre_validate_command(command_list)
        if not is_valid:
            if suggestion:
                # For now, we will just return the error. A more advanced implementation
                # could ask for confirmation to run the suggestion.
                return ExecutionResult(
                    False,
                    "",
                    f"Pre-validation failed: {error_msg}\nSuggested fix: '{suggestion}'",
                    -1,
                    original_command,
                )
            return ExecutionResult(False, "", f"Pre-validation failed: {error_msg}", -1, original_command)

        if not self._is_allowed(
            command_list
        ):  # _is_allowed now handles both string and list, internally converting string.
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Comando no permitido: {' '.join(command_list) if isinstance(command_list, list) else command}",
                return_code=1,
                command=command,
            )

        if self.use_docker_sandbox:
            self.logger.info(f"Executing command in Docker sandbox: '{command}'")
            return self.execute_in_docker(
                original_command, timeout, execution_dir
            )  # Pass original_command and execution_dir

        try:
            result = subprocess.run(
                command_list,  # Pass as list to subprocess.run
                shell=use_shell,
                cwd=execution_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                command=command,
            )
        except subprocess.TimeoutExpired:
            stderr_msg = "Timeout: comando excedió el límite de tiempo"
            if self.logger:
                self.logger.error(f"{stderr_msg}. Command: '{command}'")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=stderr_msg,
                return_code=-1,
                command=command,
            )
        except FileNotFoundError:
            stderr_msg = (
                f"Comando no encontrado: '{command_list[0]}'"
                if isinstance(command_list, list)
                else f"Comando no encontrado: '{command}'"
            )
            if self.logger:
                self.logger.error(stderr_msg)
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=stderr_msg,
                return_code=1,
                command=command,
            )
        except Exception as e:
            stderr_msg = str(e)
            if self.logger:
                self.logger.error(
                    f"Error al ejecutar comando '{command}': {stderr_msg}",
                    exc_info=True,
                )
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=stderr_msg,
                return_code=-1,
                command=command,
            )

    def execute_python(self, code: str, timeout: int = 30) -> ExecutionResult:
        """Ejecuta código Python de forma segura."""
        safe_code = f"""
import sys
import os
os.chdir('{self.working_dir}')
try:
{chr(10).join("    " + line for line in code.split(chr(10)))}
except Exception as e:
    print(f"ERROR: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
        return self.execute(f"python - <<'PY'\n{safe_code}\nPY", timeout=timeout)

    def _pull_image_if_not_exists(self, image_name: str):
        """Pulls a Docker image if it's not already present."""
        try:
            self.docker_client.images.get(image_name)
        except ImageNotFound:
            self.logger.info(f"Docker image '{image_name}' not found locally. Pulling...")
            self.docker_client.images.pull(image_name)
            self.logger.info(f"Docker image '{image_name}' pulled successfully.")

    def execute_in_docker(
        self,
        command: str | List[str],
        timeout: int = 60,
        dir_path: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Executes a command inside a Docker container.
        The project's working directory is mounted into the container.
        """
        if not self.docker_client:
            return ExecutionResult(False, "", "Docker client not initialized.", 1, command)

        target_dir = Path(dir_path) if dir_path else Path(self.working_dir)
        # Ensure target_dir is absolute and within the project root for mounting
        if not target_dir.is_absolute():
            target_dir = Path(self.working_dir) / target_dir

        # Use a generic Python image for now; could be made dynamic
        image_name = "python:3.9-slim-buster"
        try:
            self._pull_image_if_not_exists(image_name)

            # Convert command to list for exec_run
            command_list: List[str]
            if isinstance(command, str):
                command_list = shlex.split(command)
            else:
                command_list = command

            # Mount the project root into the container
            # Make sure the container's working directory matches the mounted host directory
            mount_path = "/app"
            bind_mount = f"{self.working_dir}:{mount_path}"

            # Use exec_run on a temporary container to mimic subprocess.run
            # This is simpler than run() for single commands and easier cleanup
            container = self.docker_client.containers.run(
                image_name,
                command=[
                    "tail",
                    "-f",
                    "/dev/null",
                ],  # Keep container running briefly for exec_run
                detach=True,
                remove=True,  # Automatically remove on exit
                volumes=[bind_mount],
                working_dir=mount_path,
                name=f"ollash_sandbox_{os.urandom(4).hex()}",  # Unique name
            )
            self.logger.info(f"  Docker container '{container.name}' started for command: '{command}'")

            # Calculate the relative path for workdir inside the container
            container_workdir = Path(mount_path) / target_dir.relative_to(self.working_dir)

            exit_code, output = container.exec_run(
                cmd=command_list,
                stream=False,
                demux=True,  # Separate stdout and stderr
                user="root",  # Run as root to avoid permission issues with mounted volumes
                workdir=str(container_workdir),  # Set working dir inside container
            )

            stdout_output = output[0].decode("utf-8") if output[0] else ""
            stderr_output = output[1].decode("utf-8") if output[1] else ""

            # Ensure container is stopped and removed
            container.stop()

            return ExecutionResult(
                success=exit_code == 0,
                stdout=stdout_output,
                stderr=stderr_output,
                return_code=exit_code,
                command=command,
            )
        except ImageNotFound:
            stderr_msg = f"Docker image '{image_name}' not found. Please ensure it's available."
            self.logger.error(stderr_msg)
            return ExecutionResult(False, "", stderr_msg, 1, command)
        except ContainerError as e:
            stderr_msg = f"Docker container error: {e.stderr.decode('utf-8')}"
            self.logger.error(stderr_msg)
            return ExecutionResult(False, "", stderr_msg, e.exit_status, command)
        except APIError as e:
            stderr_msg = f"Docker API error: {e}"
            self.logger.error(stderr_msg)
            return ExecutionResult(False, "", stderr_msg, 1, command)
        except Exception as e:
            stderr_msg = f"Unexpected Docker execution error: {e}"
            self.logger.error(stderr_msg)
            return ExecutionResult(False, "", stderr_msg, 1, command)

    async def async_execute(
        self,
        command: str | List[str],
        timeout: int = 60,
        dir_path: Optional[str] = None,
    ) -> ExecutionResult:
        """Async version of execute() using asyncio.create_subprocess_exec.

        Non-blocking alternative for use in async contexts (phases, web handlers).
        """
        execution_dir = dir_path or self.working_dir
        command_str: str
        command_list: List[str]

        if isinstance(command, str):
            command_str = command
            try:
                command_list = shlex.split(command)
            except ValueError as e:
                return ExecutionResult(False, "", str(e), 1, command)
        else:
            command_str = shlex.join(command)
            command_list = command

        if not self._is_allowed(command_list):
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Comando no permitido: {command_str}",
                return_code=1,
                command=command_str,
            )

        try:
            process = await asyncio.create_subprocess_exec(
                *command_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=execution_dir,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else "",
                stderr=stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else "",
                return_code=process.returncode or 0,
                command=command_str,
            )
        except asyncio.TimeoutError:
            if process:
                process.kill()
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Timeout: comando excedio el limite de tiempo",
                return_code=-1,
                command=command_str,
            )
        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Comando no encontrado: '{command_list[0]}'",
                return_code=1,
                command=command_str,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                command=command_str,
            )

    def get_python_packages(self) -> List[str]:
        """Lista paquetes Python instalados."""
        result = self.execute("pip list --format=freeze")
        if result.success:
            return [pkg.split("==")[0] for pkg in result.stdout.strip().split("\n")]
        return []
