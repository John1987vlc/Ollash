import subprocess
import os
import shlex
import py_compile
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class SandboxLevel(Enum):
    """Nivel de restricción para ejecución."""
    NONE = "none"           # Sin restricciones
    LIMITED = "limited"     # Solo directorio del proyecto
    STRICT = "strict"       # Solo comandos whitelist


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

    def __init__(self, working_dir: str = None, sandbox: SandboxLevel = SandboxLevel.NONE, logger: Any = None, policy_manager: Any = None):
        self.working_dir = working_dir or os.getcwd()
        self.sandbox = sandbox
        self.logger = logger # Store logger instance
        self.policy_manager = policy_manager # Store policy_manager instance

    def _is_allowed(self, command: str | List[str]) -> bool:
        """Verifica si el comando está permitido y sanitiza argumentos usando PolicyManager."""
        if self.sandbox == SandboxLevel.NONE:
            return True

        if not self.policy_manager:
            if self.logger: self.logger.error("CommandExecutor is in sandboxed mode but no PolicyManager is configured. Denying all commands for safety.")
            return False # Always deny if in sandbox and no policy manager

        cmd_string = command if isinstance(command, str) else shlex.join(command)
        
        # Extract base command and args for PolicyManager
        base_cmd: str
        args: List[str]
        
        if isinstance(command, str):
            if os.name == 'nt' and command.strip().lower().startswith("powershell"):
                # For PowerShell, the entire command string is the 'command', subsequent parts are args to it
                base_cmd = command.split(" ")[0].lower()
                args = shlex.split(command)[1:] # For argument checks, shlex.split is safer
            else:
                try:
                    parts = shlex.split(command)
                    base_cmd = parts[0].lower()
                    args = parts[1:]
                except ValueError as e:
                    if self.logger: self.logger.warning(f"Error parsing command with shlex: {e}. Command: '{command}'")
                    return False
        else: # command is already a list
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
                        return False, None, f"Python syntax error in '{script_path}': {e}"
        
        return True, None, None

    def execute(self, command: str | List[str], timeout: int = 60) -> ExecutionResult:
        """
        Ejecuta un comando y retorna el resultado.
        Prefiere shell=False para seguridad, pero puede usar shell=True si command es un string
        y es una llamada a powershell en Windows.
        """
        use_shell = False
        command_list: List[str]
        original_command = command

        if isinstance(command, str):
            # Special handling for Windows PowerShell calls
            if os.name == 'nt' and command.strip().lower().startswith("powershell"):
                use_shell = True # PowerShell requires shell=True for some complex cmdlets via string
                command_list = command # Pass as string
            else:
                try:
                    command_list = shlex.split(command)
                except ValueError as e:
                    if self.logger: self.logger.error(f"Error splitting command with shlex: {e}. Command: '{command}'")
                    return ExecutionResult(False, "", str(e), 1, command)
        else: # command is already a list
            command_list = command

        # Pre-validation
        is_valid, suggestion, error_msg = self._pre_validate_command(command_list)
        if not is_valid:
            if suggestion:
                # For now, we will just return the error. A more advanced implementation
                # could ask for confirmation to run the suggestion.
                return ExecutionResult(False, "", f"Pre-validation failed: {error_msg}\nSuggested fix: '{suggestion}'", -1, original_command)
            return ExecutionResult(False, "", f"Pre-validation failed: {error_msg}", -1, original_command)


        if not self._is_allowed(command_list): # _is_allowed now handles both string and list, internally converting string.
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Comando no permitido: {' '.join(command_list) if isinstance(command_list, list) else command}",
                return_code=1,
                command=command
            )

        try:
            result = subprocess.run(
                command_list, # Pass as list to subprocess.run
                shell=use_shell,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return ExecutionResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                command=command
            )
        except subprocess.TimeoutExpired:
            stderr_msg = "Timeout: comando excedió el límite de tiempo"
            if self.logger: self.logger.error(f"{stderr_msg}. Command: '{command}'")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=stderr_msg,
                return_code=-1,
                command=command
            )
        except FileNotFoundError:
            stderr_msg = f"Comando no encontrado: '{command_list[0]}'" if isinstance(command_list, list) else f"Comando no encontrado: '{command}'"
            if self.logger: self.logger.error(f"{stderr_msg}")
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=stderr_msg,
                return_code=1,
                command=command
            )
        except Exception as e:
            stderr_msg = str(e)
            if self.logger: self.logger.error(f"Error al ejecutar comando '{command}': {stderr_msg}", exc_info=True)
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=stderr_msg,
                return_code=-1,
                command=command
            )

    def execute_python(self, code: str, timeout: int = 30) -> ExecutionResult:
        """Ejecuta código Python de forma segura."""
        safe_code = f"""
import sys
import os
os.chdir('{self.working_dir}')
try:
{chr(10).join('    ' + line for line in code.split(chr(10)))}
except Exception as e:
    print(f"ERROR: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
        return self.execute(f"python - <<'PY'\n{safe_code}\nPY", timeout=timeout)

    def get_python_packages(self) -> List[str]:
        """Lista paquetes Python instalados."""
        result = self.execute("pip list --format=freeze")
        if result.success:
            return [pkg.split("==")[0] for pkg in result.stdout.strip().split("\n")]
        return []