"""Dependency reconciliation across multiple programming languages.

Extracted from CoreAgent to give reconciliation its own focused module.
Supports Python (requirements.txt), Node.js (package.json), Go (go.mod),
and Rust (Cargo.toml).
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from backend.utils.core.analysis.scanners.dependency_scanner import DependencyScanner


class DependencyReconciler:
    """Reconciles dependency manifests with actual imports found in source files.

    Uses DependencyScanner as the primary reconciliation engine, with
    language-specific fallback logic if the scanner encounters errors.
    """

    def __init__(self, dependency_scanner: DependencyScanner, logger: Any) -> None:
        self._scanner = dependency_scanner
        self._logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reconcile(self, files: Dict[str, str], project_root: Path, python_version: str) -> Dict[str, str]:
        """Reconcile all dependency files with actual imports.

        Delegates to DependencyScanner for consistent multi-language support,
        falling back to per-language methods if the scanner raises an error.

        Args:
            files: Mapping of relative path → file content.
            project_root: Absolute root of the project.
            python_version: Python version string (e.g. "3.11").

        Returns:
            Updated files mapping (may include modified manifests).
        """
        try:
            files = self._scanner.reconcile_dependencies(files, project_root)
            self._logger.info("✓ Dependency reconciliation completed via DependencyScanner")
            return files
        except Exception as exc:
            self._logger.warning(f"DependencyScanner error, falling back to basic reconciliation: {exc}")
            files = self._reconcile_python_requirements(files, project_root, python_version)
            files = self._reconcile_package_json(files, project_root)
            files = self._reconcile_go_mod(files, project_root)
            files = self._reconcile_cargo_toml(files, project_root)
            return files

    # ------------------------------------------------------------------
    # Per-language fallback helpers
    # ------------------------------------------------------------------

    def _reconcile_python_requirements(
        self, files: Dict[str, str], project_root: Path, python_version: str
    ) -> Dict[str, str]:
        """Reconcile requirements.txt with actual Python imports."""
        req_key = next((p for p in files if Path(p).name == "requirements.txt"), None)
        if not req_key:
            return files

        req_content = files[req_key]
        lines = [line.strip() for line in req_content.splitlines() if line.strip() and not line.strip().startswith("#")]

        scanned_packages = self._scan("python", files)

        if len(lines) > 30 or not scanned_packages:
            if scanned_packages:
                self._logger.info(
                    f"  Regenerating {req_key}: replacing {len(lines)} entries "
                    f"with {len(scanned_packages)} scanned packages"
                )
                new_req = f"# Python {python_version} requirements\n" + "\n".join(scanned_packages) + "\n"
                files[req_key] = new_req
                self._save_file(project_root / req_key, new_req)
            else:
                self._logger.warning(
                    f"  {req_key} has {len(lines)} entries but no Python imports found. Keeping original."
                )
        else:
            self._logger.info(f"  {req_key} looks reasonable ({len(lines)} entries). Keeping as is.")

        return files

    def _reconcile_package_json(self, files: Dict[str, str], project_root: Path) -> Dict[str, str]:
        """Reconcile package.json dependencies with actual JS/TS imports."""
        pkg_key = next(
            (p for p in files if Path(p).name == "package.json" and "node_modules" not in p),
            None,
        )
        if not pkg_key:
            return files

        try:
            pkg_data = json.loads(files[pkg_key])
        except (json.JSONDecodeError, TypeError):
            return files

        declared_deps: set[str] = set(pkg_data.get("dependencies", {}).keys())
        scanned_packages: set[str] = set(self._scan("javascript", files))

        if not scanned_packages:
            self._logger.info(f"  {pkg_key}: no JS/TS imports found. Keeping as is.")
            return files

        if len(declared_deps) > max(len(scanned_packages) * 3, 30):
            self._logger.info(
                f"  Trimming {pkg_key}: {len(declared_deps)} declared deps → {len(scanned_packages)} scanned packages"
            )
            pkg_data["dependencies"] = {pkg: "*" for pkg in sorted(scanned_packages)}
            new_content = json.dumps(pkg_data, indent=2) + "\n"
            files[pkg_key] = new_content
            self._save_file(project_root / pkg_key, new_content)
        else:
            self._logger.info(f"  {pkg_key} looks reasonable ({len(declared_deps)} deps). Keeping as is.")

        return files

    def _reconcile_go_mod(self, files: Dict[str, str], project_root: Path) -> Dict[str, str]:
        """Reconcile go.mod require block with actual Go imports."""
        mod_key = next((p for p in files if Path(p).name == "go.mod"), None)
        if not mod_key:
            return files

        scanned_modules: List[str] = self._scan("go", files)
        if not scanned_modules:
            self._logger.info(f"  {mod_key}: no third-party Go imports found. Keeping as is.")
            return files

        mod_content = files[mod_key]
        require_lines = re.findall(r"^\s+\S+\s+v\S+", mod_content, re.MULTILINE)

        if len(require_lines) > max(len(scanned_modules) * 3, 30):
            self._logger.info(
                f"  Regenerating {mod_key} require block: {len(require_lines)} → {len(scanned_modules)} modules"
            )
            module_line = re.search(r"^module\s+\S+", mod_content, re.MULTILINE)
            go_version = re.search(r"^go\s+\S+", mod_content, re.MULTILINE)

            new_content = ""
            if module_line:
                new_content += module_line.group(0) + "\n\n"
            if go_version:
                new_content += go_version.group(0) + "\n\n"
            new_content += "require (\n"
            for mod in scanned_modules:
                new_content += f"\t{mod} v0.0.0\n"
            new_content += ")\n"

            files[mod_key] = new_content
            self._save_file(project_root / mod_key, new_content)
        else:
            self._logger.info(f"  {mod_key} looks reasonable ({len(require_lines)} requires). Keeping as is.")

        return files

    def _reconcile_cargo_toml(self, files: Dict[str, str], project_root: Path) -> Dict[str, str]:
        """Reconcile Cargo.toml [dependencies] with actual Rust crate usage."""
        cargo_key = next((p for p in files if Path(p).name == "Cargo.toml"), None)
        if not cargo_key:
            return files

        scanned_crates: List[str] = self._scan("rust", files)
        if not scanned_crates:
            self._logger.info(f"  {cargo_key}: no external crate usage found. Keeping as is.")
            return files

        cargo_content = files[cargo_key]
        dep_section = re.search(r"\[dependencies\](.*?)(?=\n\[|\Z)", cargo_content, re.DOTALL)
        dep_lines = (
            [line.strip() for line in dep_section.group(1).splitlines() if line.strip() and "=" in line]
            if dep_section
            else []
        )

        if len(dep_lines) > max(len(scanned_crates) * 3, 20):
            self._logger.info(f"  Trimming {cargo_key} [dependencies]: {len(dep_lines)} → {len(scanned_crates)} crates")
            new_deps = "\n".join(f'{crate} = "*"' for crate in scanned_crates)
            if dep_section:
                new_content = (
                    cargo_content[: dep_section.start(1)] + "\n" + new_deps + "\n" + cargo_content[dep_section.end(1) :]
                )
            else:
                new_content = cargo_content + f"\n[dependencies]\n{new_deps}\n"
            files[cargo_key] = new_content
            self._save_file(project_root / cargo_key, new_content)
        else:
            self._logger.info(f"  {cargo_key} looks reasonable ({len(dep_lines)} deps). Keeping as is.")

        return files

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    def _scan(self, language: str, files: Dict[str, str]) -> List[str]:
        """Return scanned packages for the given language key."""
        return self._scanner.scan_all_imports(files).get(language, [])

    @staticmethod
    def _save_file(file_path: Path, content: str) -> None:
        """Persist content to *file_path*, creating parent directories as needed."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content.strip())
