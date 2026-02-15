from abc import ABC, abstractmethod
import json
import re
from pathlib import Path
from typing import Dict, List

from backend.utils.core.token_tracker import TokenTracker
from backend.utils.core.llm_recorder import LLMRecorder
from backend.utils.core.llm_response_parser import LLMResponseParser
from backend.utils.core.command_executor import CommandExecutor
from backend.utils.core.file_validator import FileValidator
from backend.utils.core.documentation_manager import DocumentationManager
from backend.utils.core.event_publisher import EventPublisher
from backend.utils.core.scanners.dependency_scanner import DependencyScanner
from backend.utils.core.scanners.rag_context_selector import RAGContextSelector
from backend.utils.core.concurrent_rate_limiter import (
    ConcurrentGPUAwareRateLimiter,
    SessionResourceManager,
)
from backend.utils.core.benchmark_model_selector import (
    AutoModelSelector,
)
from backend.utils.core.permission_profiles import PermissionProfileManager, PolicyEnforcer
from backend.utils.core.automatic_learning import AutomaticLearningSystem
from backend.utils.core.model_health_monitor import ModelHealthMonitor
from backend.utils.core.cross_reference_analyzer import CrossReferenceAnalyzer # NEW
from backend.services.llm_client_manager import LLMClientManager
from backend.core.kernel import AgentKernel


class CoreAgent(ABC):
    """
    Abstract base class for agents, providing common functionalities like
    LLM client management, logging, command execution, and file handling.
    """



    # File categories for intelligent context selection
    _FRONTEND_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html", ".css", ".scss", ".less"}
    _BACKEND_ROUTE_PATTERNS = {"routes", "views", "api", "endpoints", "controllers"}
    _DEPENDENCY_FILES = {"requirements.txt", "package.json", "Cargo.toml", "go.mod", "Gemfile", "pyproject.toml", "build.gradle", "pom.xml", "Dockerfile"}

    # -- Standard library modules (not installable via pip) --
    _PYTHON_STDLIB = {
        "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
        "asyncore", "atexit", "audioop", "base64", "bdb", "binascii",
        "binhex", "bisect", "builtins", "bz2", "calendar", "cgi", "cgitb",
        "chunk", "cmath", "cmd", "code", "codecs", "codeop", "collections",
        "colorsys", "compileall", "concurrent", "configparser", "contextlib",
        "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv",
        "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal",
        "difflib", "dis", "distutils", "doctest", "email", "encodings",
        "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput",
        "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt",
        "getpass", "gettext", "glob", "grp", "gzip", "hashlib", "heapq",
        "hmac", "html", "http", "idlelib", "imaplib", "imghdr", "imp",
        "importlib", "inspect", "io", "ipaddress", "itertools", "json",
        "keyword", "lib2to3", "linecache", "locale", "logging", "lzma",
        "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
        "modulefinder", "multiprocessing", "netrc", "nis", "nntplib",
        "numbers", "operator", "optparse", "os", "ossaudiodev", "pathlib",
        "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform",
        "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
        "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc",
        "queue", "quopri", "random", "re", "readline", "reprlib",
        "resource", "rlcompleter", "runpy", "sched", "secrets", "select",
        "selectors", "shelve", "shlex", "shutil", "signal", "site",
        "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "sqlite3",
        "ssl", "stat", "statistics", "string", "stringprep", "struct",
        "subprocess", "sunau", "symtable", "sys", "sysconfig", "syslog",
        "tabnanny", "tarfile", "telnetlib", "tempfile", "termios", "test",
        "textwrap", "threading", "time", "timeit", "tkinter", "token",
        "tokenize", "tomllib", "trace", "traceback", "tracemalloc",
        "tty", "turtle", "turtledemo", "types", "typing", "unicodedata",
        "unittest", "urllib", "uu", "uuid", "venv", "warnings", "wave",
        "weakref", "webbrowser", "winreg", "winsound", "wsgiref",
        "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport",
        "zlib", "_thread",
    }

    # Common import-name → PyPI-package-name mappings
    _IMPORT_TO_PACKAGE = {
        "flask": "Flask",
        "flask_sqlalchemy": "Flask-SQLAlchemy",
        "flask_cors": "Flask-CORS",
        "flask_migrate": "Flask-Migrate",
        "flask_login": "Flask-Login",
        "flask_wtf": "Flask-WTF",
        "flask_restful": "Flask-RESTful",
        "sqlalchemy": "SQLAlchemy",
        "dotenv": "python-dotenv",
        "PIL": "Pillow",
        "cv2": "opencv-python",
        "sklearn": "scikit-learn",
        "yaml": "PyYAML",
        "bs4": "beautifulsoup4",
        "dateutil": "python-dateutil",
        "attr": "attrs",
        "jwt": "PyJWT",
        "gi": "PyGObject",
        "wx": "wxPython",
        "serial": "pyserial",
        "usb": "pyusb",
        "Crypto": "pycryptodome",
    }

    # -- Node.js built-in modules (not installable via npm) --
    _NODE_BUILTINS = {
        "assert", "buffer", "child_process", "cluster", "console", "constants",
        "crypto", "dgram", "dns", "domain", "events", "fs", "http", "http2",
        "https", "module", "net", "os", "path", "perf_hooks", "process",
        "punycode", "querystring", "readline", "repl", "stream", "string_decoder",
        "sys", "timers", "tls", "tty", "url", "util", "v8", "vm", "worker_threads",
        "zlib",
    }

    # -- Go standard library top-level packages --
    _GO_STDLIB = {
        "archive", "bufio", "builtin", "bytes", "cmp", "compress", "container",
        "context", "crypto", "database", "debug", "embed", "encoding", "errors",
        "expvar", "flag", "fmt", "go", "hash", "html", "image", "index", "io",
        "iter", "log", "maps", "math", "mime", "net", "os", "path", "plugin",
        "reflect", "regexp", "runtime", "slices", "sort", "strconv", "strings",
        "structs", "sync", "syscall", "testing", "text", "time", "unicode",
        "unique", "unsafe", "weak",
    }

    def __init__(self, kernel: AgentKernel, logger_name: str = "CoreAgent", llm_manager: LLMClientManager = None, llm_recorder: LLMRecorder = None):
        self.kernel = kernel
        self.ollash_root_dir = self.kernel.ollash_root_dir
        self.config = self.kernel.get_full_config() # Use kernel's config
        self.logger = self.kernel.get_logger() # Use kernel's logger
        self.llm_recorder = llm_recorder if llm_recorder else LLMRecorder(logger=self.logger) # Initialize if not provided

        self.token_tracker = TokenTracker()
        self.response_parser = LLMResponseParser()
        
        self.command_executor = CommandExecutor(
            working_dir=str(self.ollash_root_dir),
            logger=self.logger,
            use_docker_sandbox=self.config.get("use_docker_sandbox", False)
        )
        
        self.file_validator = FileValidator(logger=self.logger, command_executor=self.command_executor)
        self.documentation_manager = DocumentationManager(
            project_root=self.ollash_root_dir,
            logger=self.logger,
            llm_recorder=self.llm_recorder, # Pass llm_recorder
            config=self.config
        )
        self.event_publisher = EventPublisher()
        self.cross_reference_analyzer = CrossReferenceAnalyzer(
            project_root=self.ollash_root_dir,
            logger=self.logger,
            config=self.config,
            llm_recorder=self.llm_recorder,
        )
        self.cross_reference_analyzer = CrossReferenceAnalyzer(
            project_root=self.ollash_root_dir,
            logger=self.logger,
            config=self.config,
            llm_recorder=self.llm_recorder,
        )

        # Initialize new architectural modules (6 improvements)
        self.dependency_scanner = DependencyScanner(logger=self.logger)
        chroma_db_path = str(self.ollash_root_dir / ".ollash" / "chroma_db")
        self.rag_context_selector = RAGContextSelector(
            self.config,
            chroma_db_path,
            None
        )
        self.rate_limiter = ConcurrentGPUAwareRateLimiter(
            logger=self.logger,
        )
        self.session_resource_manager = SessionResourceManager()
        self.benchmark_selector = AutoModelSelector(
            logger=self.logger,
            benchmark_dir=self.ollash_root_dir / ".ollash" / "benchmarks",
        )
        self.permission_manager = PermissionProfileManager(
            logger=self.logger,
            project_root=self.ollash_root_dir,
        )
        self.policy_enforcer = PolicyEnforcer(
            profile_manager=self.permission_manager,
            logger=self.logger,
            tool_settings_config=self.kernel.get_tool_settings_config(), # NEW
        )
        self.policy_enforcer.set_active_profile("developer") # Set active profile after initialization
        self.learning_system = AutomaticLearningSystem(
            logger=self.logger,
            project_root=self.ollash_root_dir,
            settings_manager=self.config
        )
        if llm_manager:
            self.llm_manager = llm_manager
        else:
            self.llm_manager = LLMClientManager(
                config=self.kernel.get_llm_models_config(),
                tool_settings=self.kernel.get_tool_settings_config(),
                logger=self.logger,
                recorder=self.llm_recorder
            )

        self.logger.info(f"{logger_name} initialized with 6 architectural improvements and external LLM management.")
        self.logger.info(
            "  ✓ DependencyScanner (multi-language desoupling)"
        )
        self.logger.info(
            "  ✓ RAGContextSelector (semantic context via ChromaDB)"
        )
        self.logger.info(
            "  ✓ ConcurrentGPUAwareRateLimiter (GPU resource management)"
        )
        self.logger.info(
            "  ✓ BenchmarkModelSelector (auto model optimization)"
        )
        self.logger.info(
            "  ✓ PermissionProfiles (fine-grained access control)"
        )
        self.logger.info(
            "  ✓ AutomaticLearningSystem (post-mortem pattern capture)"
        )



    @staticmethod
    def _save_file(file_path: Path, content: str):
        """Save content to a file, creating parent directories as needed."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content.strip())

    @abstractmethod
    def run(self, *args, **kwargs):
        """Abstract method to be implemented by concrete agents."""
        pass

    def _scan_python_imports(self, files: Dict[str, str]) -> List[str]:
        """Scan Python files for import statements and return a list of pip-installable packages.
        
        Delegates to DependencyScanner for multi-language consistency.
        """
        return self.dependency_scanner.scan_all_imports(files).get("python", [])

    def _scan_node_imports(self, files: Dict[str, str]) -> List[str]:
        """Scan JS/TS files for require/import statements and return npm package names.
        
        Delegates to DependencyScanner for multi-language consistency.
        """
        return self.dependency_scanner.scan_all_imports(files).get("javascript", [])

    def _scan_go_imports(self, files: Dict[str, str]) -> List[str]:
        """Scan Go files for import statements and return third-party module paths.
        
        Delegates to DependencyScanner for multi-language consistency.
        """
        return self.dependency_scanner.scan_all_imports(files).get("go", [])

    def _scan_rust_imports(self, files: Dict[str, str]) -> List[str]:
        """Scan Rust files for extern crate statements and return crate names.
        
        Delegates to DependencyScanner for multi-language consistency.
        """
        return self.dependency_scanner.scan_all_imports(files).get("rust", [])

    def _reconcile_requirements(
        self, files: Dict[str, str], project_root: Path, python_version: str
    ) -> Dict[str, str]:
        """Reconcile dependency files with actual imports using DependencyScanner.

        Supports multiple languages:
        - Python: requirements.txt from actual imports in .py files
        - Node.js: package.json dependencies from require/import in .js/.ts files
        - Go: go.mod require block from import statements in .go files
        - Rust: Cargo.toml [dependencies] from extern crate/use in .rs files
        
        Uses DependencyScanner for consistent, extensible multi-language support.
        """
        try:
            # Use DependencyScanner for all reconciliation
            files = self.dependency_scanner.reconcile_dependencies(files, project_root)
            self.logger.info("✓ Dependency reconciliation completed via DependencyScanner")
            return files
        except Exception as e:
            self.logger.warning(f"DependencyScanner error, falling back to basic reconciliation: {e}")
            # Fallback to individual language scans if scanner fails
            files = self._reconcile_python_requirements(files, project_root, python_version)
            files = self._reconcile_package_json(files, project_root)
            files = self._reconcile_go_mod(files, project_root)
            files = self._reconcile_cargo_toml(files, project_root)
            return files

    def _reconcile_python_requirements(
        self, files: Dict[str, str], project_root: Path, python_version: str
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
        lines = [line.strip() for line in req_content.splitlines()
                 if line.strip() and not line.strip().startswith("#")]

        scanned_packages = self._scan_python_imports(files)

        if len(lines) > 30 or not scanned_packages:
            if scanned_packages:
                self.logger.info(
                    f"  Regenerating {req_key}: replacing {len(lines)} entries "
                    f"with {len(scanned_packages)} scanned packages"
                )
                new_req = f"# Python {python_version} requirements\n" + "\n".join(scanned_packages) + "\n"
                files[req_key] = new_req
                self._save_file(project_root / req_key, new_req)
            else:
                self.logger.warning(
                    f"  {req_key} has {len(lines)} entries but no Python imports found. "
                    f"Keeping original."
                )
        else:
            self.logger.info(
                f"  {req_key} looks reasonable ({len(lines)} entries). Keeping as is."
            )

        return files

    def _reconcile_package_json(
        self, files: Dict[str, str], project_root: Path
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
        scanned_packages = set(self._scan_node_imports(files))

        if not scanned_packages:
            self.logger.info(f"  {pkg_key}: no JS/TS imports found. Keeping as is.")
            return files

        if len(declared_deps) > max(len(scanned_packages) * 3, 30):
            self.logger.info(
                f"  Trimming {pkg_key}: {len(declared_deps)} declared deps → "
                f"{len(scanned_packages)} scanned packages"
            )
            new_deps = {pkg: "*" for pkg in sorted(scanned_packages)}
            pkg_data["dependencies"] = new_deps
            new_content = json.dumps(pkg_data, indent=2) + "\n"
            files[pkg_key] = new_content
            self._save_file(project_root / pkg_key, new_content)
        else:
            self.logger.info(
                f"  {pkg_key} looks reasonable ({len(declared_deps)} deps). Keeping as is."
            )

        return files

    def _reconcile_go_mod(
        self, files: Dict[str, str], project_root: Path
    ) -> Dict[str, str]:
        """Reconcile go.mod require block with actual Go imports."""
        mod_key = None
        for path in files:
            if Path(path).name == "go.mod":
                mod_key = path
                break

        if not mod_key:
            return files

        scanned_modules = self._scan_go_imports(files)
        if not scanned_modules:
            self.logger.info(f"  {mod_key}: no third-party Go imports found. Keeping as is.")
            return files

        mod_content = files[mod_key]
        require_lines = re.findall(r'^\s+\S+\s+v\S+', mod_content, re.MULTILINE)

        if len(require_lines) > max(len(scanned_modules) * 3, 30):
            self.logger.info(
                f"  Regenerating {mod_key} require block: {len(require_lines)} → "
                f"{len(scanned_modules)} modules"
            )
            module_line = re.search(r'^module\s+\S+', mod_content, re.MULTILINE)
            go_version = re.search(r'^go\s+\S+', mod_content, re.MULTILINE)

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
            self.logger.info(
                f"  {mod_key} looks reasonable ({len(require_lines)} requires). Keeping as is."
            )

        return files

    def _reconcile_cargo_toml(
        self, files: Dict[str, str], project_root: Path
    ) -> Dict[str, str]:
        """Reconcile Cargo.toml [dependencies] with actual Rust crate usage."""
        cargo_key = None
        for path in files:
            if Path(path).name == "Cargo.toml":
                cargo_key = path
                break

        if not cargo_key:
            return files

        scanned_crates = self._scan_rust_imports(files)
        if not scanned_crates:
            self.logger.info(f"  {cargo_key}: no external crate usage found. Keeping as is.")
            return files

        cargo_content = files[cargo_key]
        dep_section = re.search(
            r'\[dependencies\](.*?)(?=\n\[|\Z)', cargo_content, re.DOTALL
        )
        if dep_section:
            dep_lines = [l.strip() for l in dep_section.group(1).splitlines()
                         if l.strip() and "=" in l]
        else:
            dep_lines = []

        if len(dep_lines) > max(len(scanned_crates) * 3, 20):
            self.logger.info(
                f"  Trimming {cargo_key} [dependencies]: {len(dep_lines)} → "
                f"{len(scanned_crates)} crates"
            )
            new_deps = "\n".join(f'{crate} = "*"' for crate in scanned_crates)
            if dep_section:
                new_content = (
                    cargo_content[:dep_section.start(1)]
                    + "\n" + new_deps + "\n"
                    + cargo_content[dep_section.end(1):]
                )
            else:
                new_content = cargo_content + f"\n[dependencies]\n{new_deps}\n"
            files[cargo_key] = new_content
            self._save_file(project_root / cargo_key, new_content)
        else:
            self.logger.info(
                f"  {cargo_key} looks reasonable ({len(dep_lines)} deps). Keeping as is."
            )

        return files

    def _select_related_files(
        self, target_path: str, generated_files: Dict[str, str], max_files: int = 8
    ) -> Dict[str, str]:
        """Select contextually relevant files using semantic search (RAG).

        First attempts semantic selection via RAGContextSelector (ChromaDB embeddings),
        then falls back to heuristic scoring if semantic selection unavailable.
        
        Args:
            target_path: Path to file needing context
            generated_files: All available generated files
            max_files: Maximum context files to select
            
        Returns:
            Dictionary of selected contextual files
        """
        if not generated_files:
            return {}

        try:
            # Try semantic selection first
            target = Path(target_path)
            context_files = self.rag_context_selector.select_relevant_files(
                query=target.stem,
                available_files=generated_files,
                max_files=max_files,
            )
            
            if context_files:
                self.logger.info(
                    f"🔍 Selected {len(context_files)} contextual files using RAG semantic search"
                )
                return context_files
        except Exception as e:
            self.logger.info(f"RAG selection unavailable, using heuristic scoring: {e}")

        # Fallback: Heuristic scoring (original behavior)
        target = Path(target_path)
        target_ext = target.suffix.lower()
        target_name = target.name
        target_dir = str(target.parent)

        scored: Dict[str, int] = {}
        for path, content in generated_files.items():
            if not content:
                continue
            p = Path(path)
            score = 0

            if str(p.parent) == target_dir:
                score += 3

            if target_ext in self._FRONTEND_EXTENSIONS:
                name_lower = p.stem.lower()
                if any(pat in name_lower for pat in self._BACKEND_ROUTE_PATTERNS):
                    score += 5
                if "model" in name_lower:
                    score += 3

            if target_name in self._DEPENDENCY_FILES:
                if p.suffix in (".py", ".js", ".ts", ".go", ".rs", ".rb"):
                    score += 4

            if any(pat in target.stem.lower() for pat in self._BACKEND_ROUTE_PATTERNS):
                if "model" in p.stem.lower():
                    score += 4

            if p.name in ("__init__.py", "config.py", "settings.py", "app.py"):
                score += 2

            scored[path] = score

        ranked = sorted(scored.keys(), key=lambda p: scored[p], reverse=True)
        selected = {p: generated_files[p] for p in ranked[:max_files]}
        return selected
