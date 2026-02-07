import subprocess
import os
import shlex # Added
from pathlib import Path # Added
from typing import Optional, Dict, List, Any # Added Any for logger
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

    def __init__(self, working_dir: str = None, sandbox: SandboxLevel = SandboxLevel.NONE, logger: Any = None):
        self.working_dir = working_dir or os.getcwd()
        self.sandbox = sandbox
        self.logger = logger # Store logger instance

        self.whitelist = {
            "python": ["python", "python3", "pip", "pip3"],
            "node": ["node", "npm", "npx"],
            "git": ["git"],
            "shell": ["ls", "cat", "echo", "pwd", "cd", "mkdir", "rm", "cp", "mv", "findstr", "grep", "tail", "head", "powershell", "wmic"],
            "build": ["make", "cmake", "cargo", "gradle"],
            "network": ["ping", "traceroute", "tracert", "netstat", "nmap", "nc", "Test-NetConnection"],
            "system": ["systeminfo", "tasklist", "ps", "hostnamectl", "lscpu", "free", "sw_vers", "sysctl", "apt-get", "yum", "choco", "brew"],
            "security": ["hashsum", "md5sum", "sha256sum", "certutil", "openssl", "awk", "find"]
        }

    def _is_allowed(self, command: str | List[str]) -> bool:
        """Verifica si el comando está permitido y sanitiza argumentos."""
        if self.sandbox == SandboxLevel.NONE:
            return True

        if isinstance(command, str):
            try:
                # Handle Windows-specific commands (like powershell) that might not be shlex-friendly
                if os.name == 'nt' and command.strip().startswith("powershell"):
                    # For PowerShell commands, we allow the full string to pass if 'powershell' is whitelisted
                    # but we must still check for malicious content within the argument string
                    parts = [command.split(" ")[0]] # "powershell"
                    # The rest of the string is the argument to powershell -command
                    powershell_arg = " ".join(command.split(" ")[1:])
                    # Basic check for common injection points within the powershell argument
                    if any(c in powershell_arg for c in [';', '&', '|', '`', '$(']):
                        if self.logger: self.logger.warning(f"Rejected PowerShell command due to potential injection in argument: {command}")
                        return False
                    # A more thorough approach would involve parsing PowerShell AST, which is complex.
                    # This basic check limits obvious injections.
                else:
                    parts = shlex.split(command)
            except ValueError as e:
                if self.logger: self.logger.warning(f"Error parsing command with shlex: {e}. Command: '{command}'")
                return False
        else:
            parts = command # Already a list

        if not parts:
            return False

        base_cmd = parts[0].lower() # Normalize for comparison

        # 1. Check if base command is whitelisted
        found_in_whitelist = False
        for group_cmds in self.whitelist.values():
            if base_cmd in group_cmds:
                found_in_whitelist = True
                break
        if not found_in_whitelist:
            if self.logger: self.logger.warning(f"Command '{base_cmd}' not in whitelist. Full command: '{' '.join(parts)}'")
            return False

        # 2. Check arguments for dangerous metacharacters and path traversals (for LIMITED sandbox)
        if self.sandbox == SandboxLevel.LIMITED:
            for arg in parts[1:]: # Iterate through arguments
                if any(c in arg for c in [';', '&', '||', '&&', '`', '$(', '|', '>', '<', '*']):
                    # Allow specific cases like `git log --graph` which has `*` or `grep -E 'a|b'`
                    # This needs to be refined per command context. For now, strict.
                    if self.logger: self.logger.warning(f"Rejected command due to dangerous metacharacter '{arg}' in argument. Full command: '{' '.join(parts)}'")
                    return False
                
                # Path validation: prevent path traversal and absolute paths outside working_dir
                # Apply only to arguments that look like paths and for commands that typically take paths
                if base_cmd in ['ls', 'cat', 'rm', 'cp', 'mv', 'grep', 'find', 'mkdir', 'powershell', 'wmic']:
                    if os.path.isabs(arg): # Disallow absolute paths by default in LIMITED sandbox
                        if self.logger: self.logger.warning(f"Rejected command due to absolute path '{arg}'. Full command: '{' '.join(parts)}'")
                        return False
                    
                    # Resolve path to check if it's within the working directory
                    try:
                        resolved_path = (Path(self.working_dir) / arg).resolve()
                        if not str(resolved_path).startswith(str(Path(self.working_dir).resolve())):
                            if self.logger: self.logger.warning(f"Rejected command due to path traversal '{arg}'. Resolved: '{resolved_path}'. Full command: '{' '.join(parts)}'")
                            return False
                    except Exception as path_err:
                        if self.logger: self.logger.warning(f"Error resolving path '{arg}': {path_err}. Full command: '{' '.join(parts)}'")
                        return False
        return True

    def execute(self, command: str | List[str], timeout: int = 60) -> ExecutionResult:
        """
        Ejecuta un comando y retorna el resultado.
        Prefiere shell=False para seguridad, pero puede usar shell=True si command es un string
        y es una llamada a powershell en Windows.
        """
        use_shell = False
        command_list: List[str]

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
