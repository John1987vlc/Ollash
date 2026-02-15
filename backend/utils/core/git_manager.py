import subprocess
from typing import Dict, List, Any


class GitManager:
    """Gestiona operaciones de Git."""

    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or "."

    def _run_git(self, *args) -> Dict[str, Any]:
        """Ejecuta un comando git."""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip()
            }
        except FileNotFoundError:
            return {"success": False, "output": "", "error": "Git no instalado"}

    def status(self) -> Dict[str, Any]:
        """Estado del repositorio."""
        return self._run_git("status", "--porcelain")

    def diff(self) -> str:
        """Muestra diferencias."""
        result = self._run_git("diff")
        return result.get("output", "")

    def diff_staged(self) -> str:
        """Muestra diferencias staged."""
        result = self._run_git("diff", "--cached")
        return result.get("output", "")

    def log(self, n: int = 5) -> str:
        """Historial de commits."""
        result = self._run_git("log", "--oneline", f"-n{n}")
        return result.get("output", "")

    def branches(self) -> List[str]:
        """Lista ramas."""
        result = self._run_git("branch", "--list")
        if result["success"]:
            return [b.strip() for b in result["output"].split("\n") if b]
        return []

    def current_branch(self) -> str:
        """Rama actual."""
        result = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        return result.get("output", "")

    def add(self, files: List[str] = None) -> Dict[str, Any]:
        """Stage archivos."""
        if files:
            return self._run_git("add", *files)
        return self._run_git("add", "-A")

    def commit(self, message: str) -> Dict[str, Any]:
        """Hace commit."""
        return self._run_git("commit", "-m", message)

    def push(self, remote: str = "origin", branch: str = None) -> Dict[str, Any]:
        """Hace push."""
        b = branch or self.current_branch()
        return self._run_git("push", remote, b)

    def pull(self, remote: str = "origin", branch: str = None) -> Dict[str, Any]:
        """Hace pull."""
        b = branch or self.current_branch()
        return self._run_git("pull", remote, b)

    def checkout(self, branch: str, create: bool = False) -> Dict[str, Any]:
        """Cambia de rama."""
        if create:
            return self._run_git("checkout", "-b", branch)
        return self._run_git("checkout", branch)

    def create_commit_with_all(self, message: str) -> Dict[str, Any]:
        """Hace add all y commit en uno."""
        result = self.add()
        if not result["success"]:
            return result
        return self.commit(message)

    def get_stashed_changes(self) -> List[str]:
        """Lista cambios guardados."""
        result = self._run_git("stash", "list")
        if result["success"]:
            return result["output"].split("\n")
        return []

    def diff_numstat(self, path: str = None, staged: bool = False) -> Dict[str, Any]:
        """
        Obtiene el número de líneas añadidas/borradas y la lista de archivos afectados.
        Si staged es True, usa --cached para cambios staged.
        """
        cmd_args = ["diff", "--numstat"]
        if staged:
            cmd_args.append("--cached")
        if path:
            cmd_args.append(path)

        result = self._run_git(*cmd_args)

        if not result["success"]:
            return {"success": False, "output": result["error"]}

        output_lines = result["output"].splitlines()
        total_added = 0
        total_deleted = 0
        affected_files = []

        for line in output_lines:
            parts = line.split('\t')
            if len(parts) == 3:
                try:
                    added = int(parts[0])
                    deleted = int(parts[1])
                    file_path = parts[2]
                    total_added += added
                    total_deleted += deleted
                    affected_files.append(file_path)
                except ValueError:
                    # Handle lines that might not be numstat (e.g., binary files)
                    pass

        return {
            "success": True,
            "added": total_added,
            "deleted": total_deleted,
            "total": total_added + total_deleted,
            "files": affected_files
        }

