import subprocess
import os
from typing import Optional, Dict, List
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

    def __init__(self, working_dir: str = None, sandbox: SandboxLevel = SandboxLevel.NONE):
        self.working_dir = working_dir or os.getcwd()
        self.sandbox = sandbox

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

    def _is_allowed(self, cmd: str) -> bool:
        """Verifica si el comando está permitido."""
        if self.sandbox == SandboxLevel.NONE:
            return True

        base_cmd = cmd.split()[0] if cmd else ""
        for group in self.whitelist.values():
            if base_cmd in group:
                return True
        return False

    def execute(self, command: str, timeout: int = 60) -> ExecutionResult:
        """Ejecuta un comando y retorna el resultado."""
        if not self._is_allowed(command):
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Comando no permitido: {command}",
                return_code=1,
                command=command
            )

        try:
            result = subprocess.run(
                command,
                shell=True,
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
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Timeout: comando excedió el límite de tiempo",
                return_code=-1,
                command=command
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
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
