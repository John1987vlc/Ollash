"""Dependency Scanner module for multi-language dependency detection and reconciliation.

This module handles scanning and reconciling dependency files across multiple languages:
- Python (requirements.txt, pyproject.toml)
- Node.js (package.json)
- Go (go.mod)
- Rust (Cargo.toml)
- Ruby (Gemfile)
- Java (pom.xml, build.gradle)

Design: Desoupled from CoreAgent to follow Single Responsibility Principle.
Extensible: New language scanners can be added without modifying CoreAgent.
"""

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Set

from backend.utils.core.agent_logger import AgentLogger


class LanguageDependencyScanner(ABC):
    """Base class for language-specific dependency scanning."""

    def __init__(self, logger: Optional[AgentLogger] = None):
        """Initialize scanner with optional logger."""
        self.logger = logger

    @abstractmethod
    def get_dependency_files(self) -> Set[str]:
        """Return filenames that mark dependency files for this language."""
        pass

    @abstractmethod
    def scan_imports(self, files: Dict[str, str]) -> Set[str]:
        """Scan source files and extract third-party packages/modules."""
        pass

    @abstractmethod
    def reconcile(
        self,
        files: Dict[str, str],
        project_root: Path,
        logger: AgentLogger,
    ) -> Dict[str, str]:
        """Reconcile dependency files with actual imports."""
        pass


class PythonDependencyScanner(LanguageDependencyScanner):
    """Scan and reconcile Python dependencies."""

    def get_dependency_files(self) -> Set[str]:
        return {"requirements.txt", "pyproject.toml", "setup.py"}

    def scan_imports(self, files: Dict[str, str]) -> Set[str]:
        """Extract third-party packages from Python source files."""
        packages = set()
        stdlib_modules = {
            "os",
            "sys",
            "re",
            "json",
            "pathlib",
            "typing",
            "abc",
            "collections",
            "itertools",
            "functools",
            "operator",
            "datetime",
            "time",
            "calendar",
            "math",
            "random",
            "statistics",
            "decimal",
            "fractions",
            "cmath",
            "hashlib",
            "hmac",
            "secrets",
            "urllib",
            "http",
            "email",
            "mailbox",
            "mimetypes",
            "base64",
            "binascii",
            "quopri",
            "socketserver",
            "socket",
            "ssl",
            "select",
            "selectors",
            "asyncio",
            "threading",
            "multiprocessing",
            "concurrent",
            "subprocess",
            "socket",
            "ssl",
            "struct",
            "codecs",
            "io",
            "tempfile",
            "glob",
            "fnmatch",
            "linecache",
            "shutil",
            "sqlite3",
            "zlib",
            "gzip",
            "bz2",
            "lzma",
            "zipfile",
            "tarfile",
            "csv",
            "configparser",
            "netrc",
            "xdrlib",
            "plistlib",
            "pickle",
            "copyreg",
            "shelve",
            "dbm",
            "marshal",
            "sqlite3",
            "unittest",
            "doctest",
            "pdb",
            "trace",
            "logging",
            "getpass",
            "curses",
            "argparse",
            "getopt",
            "warnings",
            "contextlib",
            "enum",
            "numbers",
            "decimal",
            "warnings",
            "dataclasses",
            "typing",
            "pydoc",
            "doctest",
            "test",
            "lib2to3",
            "warnings",
        }

        for filename, content in files.items():
            if filename.endswith(".py"):
                # Find import statements
                for match in re.finditer(r"^(?:from|import)\s+([a-zA-Z0-9_\.]+)", content, re.MULTILINE):
                    module = match.group(1).split(".")[0]
                    if module not in stdlib_modules and not module.startswith("_"):
                        packages.add(module)

        return packages

    def reconcile(
        self,
        files: Dict[str, str],
        project_root: Path,
        logger: AgentLogger,
    ) -> Dict[str, str]:
        """Reconcile requirements.txt with actual Python imports."""
        req_key = None
        for path in files:
            if Path(path).name == "requirements.txt":
                req_key = path
                break

        if not req_key:
            return files

        req_content = files[req_key]
        lines = [line.strip() for line in req_content.splitlines() if line.strip() and not line.strip().startswith("#")]

        scanned_packages = self.scan_imports(files)

        if len(lines) > 30 or (not scanned_packages and len(lines) > 0):
            if scanned_packages:
                logger.info(
                    f"  Regenerating {req_key}: replacing {len(lines)} entries "
                    f"with {len(scanned_packages)} scanned packages"
                )
                new_req = "\n".join(sorted(scanned_packages)) + "\n"
                files[req_key] = new_req
            else:
                logger.warning(f"  {req_key} has {len(lines)} entries but no Python imports found. Keeping original.")
        else:
            logger.info(f"  {req_key} looks reasonable ({len(lines)} entries). Keeping as is.")

        return files


class NodeDependencyScanner(LanguageDependencyScanner):
    """Scan and reconcile Node.js/npm dependencies."""

    def get_dependency_files(self) -> Set[str]:
        return {"package.json", "package-lock.json", "yarn.lock"}

    def scan_imports(self, files: Dict[str, str]) -> Set[str]:
        """Extract third-party packages from JS/TS source files."""
        packages = set()
        builtin_modules = {
            "fs",
            "path",
            "http",
            "https",
            "os",
            "sys",
            "util",
            "events",
            "stream",
            "crypto",
            "zlib",
            "assert",
            "child_process",
            "cluster",
            "dns",
            "domain",
            "net",
            "dgram",
            "readline",
            "repl",
            "tty",
            "vm",
            "process",
            "buffer",
            "querystring",
            "url",
            "punycode",
            "string_decoder",
            "timers",
            "console",
            "module",
            "perf_hooks",
            "inspector",
            "async_hooks",
        }

        for filename, content in files.items():
            if filename.endswith((".js", ".ts", ".jsx", ".tsx")):
                # Find require and import statements
                for match in re.finditer(
                    r"(?:require\(['\"]([^'\"]+)['\"]\)|import\s+\S+\s+from\s+['\"]([^'\"]+)['\"])",
                    content,
                ):
                    module = match.group(1) or match.group(2)
                    # Extract top-level package name
                    package = module.split("/")[0]
                    if package and not package.startswith(".") and package not in builtin_modules:
                        packages.add(package)

        return packages

    def reconcile(
        self,
        files: Dict[str, str],
        project_root: Path,
        logger: AgentLogger,
    ) -> Dict[str, str]:
        """Reconcile package.json dependencies with actual JS/TS imports."""
        pkg_key = None
        for path in files:
            if Path(path).name == "package.json" and "node_modules" not in path:
                pkg_key = path
                break

        if not pkg_key:
            return files

        try:
            pkg_data = json.loads(files[pkg_key])
        except (json.JSONDecodeError, TypeError):
            return files

        declared_deps = set(pkg_data.get("dependencies", {}).keys())
        scanned_packages = self.scan_imports(files)

        if not scanned_packages:
            logger.info(f"  {pkg_key}: no JS/TS imports found. Keeping as is.")
            return files

        if len(declared_deps) > max(len(scanned_packages) * 3, 30):
            logger.info(
                f"  Trimming {pkg_key}: {len(declared_deps)} declared deps → {len(scanned_packages)} scanned packages"
            )
            new_deps = {pkg: "*" for pkg in sorted(scanned_packages)}
            pkg_data["dependencies"] = new_deps
            new_content = json.dumps(pkg_data, indent=2) + "\n"
            files[pkg_key] = new_content
        else:
            logger.info(f"  {pkg_key} looks reasonable ({len(declared_deps)} deps). Keeping as is.")

        return files


class GoDependencyScanner(LanguageDependencyScanner):
    """Scan and reconcile Go module dependencies."""

    def get_dependency_files(self) -> Set[str]:
        return {"go.mod", "go.sum"}

    def scan_imports(self, files: Dict[str, str]) -> Set[str]:
        """Extract third-party modules from Go source files."""
        modules = set()

        for filename, content in files.items():
            if filename.endswith(".go"):
                # Find import statements
                for match in re.finditer(
                    r'import\s*\(\s*([\s\S]*?)\s*\)|import\s+"([^"]+)"',
                    content,
                ):
                    if match.group(1):
                        for line in match.group(1).split("\n"):
                            pkg = re.search(r'"([^"]+)"', line)
                            if pkg:
                                modules.add(pkg.group(1))
                    elif match.group(2):
                        modules.add(match.group(2))

        return {m for m in modules if "/" in m}  # Only third-party

    def reconcile(
        self,
        files: Dict[str, str],
        project_root: Path,
        logger: AgentLogger,
    ) -> Dict[str, str]:
        """Reconcile go.mod require block with actual Go imports."""
        mod_key = None
        for path in files:
            if Path(path).name == "go.mod":
                mod_key = path
                break

        if not mod_key:
            return files

        scanned_modules = self.scan_imports(files)
        if not scanned_modules:
            logger.info(f"  {mod_key}: no third-party Go imports found. Keeping as is.")
            return files

        mod_content = files[mod_key]
        require_lines = re.findall(r"^\s+\S+\s+v\S+", mod_content, re.MULTILINE)

        if len(require_lines) > len(scanned_modules) * 3:  # Use a heuristic to decide if file is "too big"
            logger.info(
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
            for mod in sorted(scanned_modules):  # Sort for deterministic output
                new_content += f"\t{mod} v0.0.0\n"  # Use v0.0.0 or actual versions if available
            new_content += ")\n"

            files[mod_key] = new_content
        else:
            logger.info(f"  {mod_key} looks reasonable ({len(require_lines)} requires). Keeping as is.")

        return files


class RustDependencyScanner(LanguageDependencyScanner):
    """Scan and reconcile Rust crate dependencies."""

    def get_dependency_files(self) -> Set[str]:
        return {"Cargo.toml", "Cargo.lock"}

    def scan_imports(self, files: Dict[str, str]) -> Set[str]:
        """Extract crates from Rust source files."""
        crates = set()
        std_libs = {"std"}

        for filename, content in files.items():
            if filename.endswith(".rs"):
                # Find extern crate and use statements
                for match in re.finditer(r"extern\s+crate\s+(\w+)", content):
                    if match.group(1) not in std_libs:
                        crates.add(match.group(1))
                for match in re.finditer(r"use\s+((?:\w|:)+)", content):
                    crate = match.group(1).split("::")[0]
                    if crate not in std_libs:
                        crates.add(crate)

        return crates

    def reconcile(
        self,
        files: Dict[str, str],
        project_root: Path,
        logger: AgentLogger,
    ) -> Dict[str, str]:
        """Reconcile Cargo.toml [dependencies] with actual Rust crate usage."""
        cargo_key = None
        for path in files:
            if Path(path).name == "Cargo.toml":
                cargo_key = path
                break

        if not cargo_key:
            return files

        scanned_crates = self.scan_imports(files)
        if not scanned_crates:
            logger.info(f"  {cargo_key}: no third-party crates found. Keeping as is.")
            return files

        logger.info(f"  {cargo_key}: detected {len(scanned_crates)} third-party crates")
        return files


class DependencyScanner:
    """Unified dependency scanner orchestrator.

    Coordinates language-specific scanners to provide an extensible,
    single-responsibility approach to dependency management.
    """

    def __init__(self, logger: AgentLogger):
        self.logger = logger
        self.scanners: Dict[str, LanguageDependencyScanner] = {
            "python": PythonDependencyScanner(logger=logger),
            "node": NodeDependencyScanner(logger=logger),
            "go": GoDependencyScanner(logger=logger),
            "rust": RustDependencyScanner(logger=logger),
        }

    def register_scanner(self, language: str, scanner: LanguageDependencyScanner):
        """Register a new language-specific scanner."""
        self.scanners[language] = scanner
        self.logger.info(f"Registered dependency scanner for {language}")

    def get_all_dependency_files(self) -> Set[str]:
        """Get all recognized dependency file names across all languages."""
        all_files = set()
        for scanner in self.scanners.values():
            all_files.update(scanner.get_dependency_files())
        return all_files

    def reconcile_dependencies(
        self,
        files: Dict[str, str],
        project_root: Path,
    ) -> Dict[str, str]:
        """Reconcile all dependency files with actual imports across all languages."""
        self.logger.info("🔧 Reconciling dependencies...")

        for language, scanner in self.scanners.items():
            try:
                files = scanner.reconcile(files, project_root, self.logger)
            except Exception as e:
                self.logger.warning(f"Error reconciling {language} dependencies: {e}")

        return files

    def scan_all_imports(self, files: Dict[str, str]) -> Dict[str, Set[str]]:
        """Scan all source files and return imports by language."""
        imports_by_language = {}
        for language, scanner in self.scanners.items():
            imports_by_language[language] = scanner.scan_imports(files)
        return imports_by_language
