from abc import ABC, abstractmethod
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.token_tracker import TokenTracker
from src.utils.core.llm_response_parser import LLMResponseParser
from src.utils.core.command_executor import CommandExecutor
from src.utils.core.file_validator import FileValidator
from src.utils.core.documentation_manager import DocumentationManager
from src.utils.core.event_publisher import EventPublisher


class CoreAgent(ABC):
    """
    Abstract base class for agents, providing common functionalities like
    LLM client management, logging, command execution, and file handling.
    """

    # Common LLM roles and their default models/timeouts
    LLM_ROLES = [
        ("prototyper", "prototyter_model", "gpt-oss:20b", 600),
        ("coder", "coder_model", "qwen3-coder:30b", 480),
        ("planner", "planner_model", "ministral-3:14b", 900),
        ("generalist", "generalist_model", "ministral-3:8b", 300),
        ("suggester", "suggester_model", "ministral-3:8b", 300),
        ("improvement_planner", "improvement_planner_model", "ministral-3:14b", 900),
        ("test_generator", "test_generator_model", "qwen3-coder:30b", 480),
        ("senior_reviewer", "senior_reviewer_model", "ministral-3:14b", 900),
        ("orchestration", "orchestration_model", "ministral-3:8b", 300), # Added orchestration role
        ("default", "default_model", "qwen3-coder-next:14b", 600), # For DefaultAgent, generic tasks
    ]

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

    def __init__(self, config_path: str = "config/settings.json", ollash_root_dir: Optional[Path] = None, logger_name: str = "CoreAgent"):
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.ollash_root_dir = ollash_root_dir if ollash_root_dir else Path(os.getcwd())
        log_file_path = self.ollash_root_dir / "logs" / f"{logger_name.lower()}.log"

        self.url = os.environ.get(
            "OLLASH_OLLAMA_URL",
            self.config.get("ollama_url", "http://localhost:11434"),
        )
        self.logger = AgentLogger(log_file=str(log_file_path), logger_name=logger_name)
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
            config=self.config
        )
        self.event_publisher = EventPublisher()

        self.llm_clients: Dict[str, OllamaClient] = {}
        self._initialize_llm_clients()

        self.logger.info(f"{logger_name} initialized.")

    def _initialize_llm_clients(self):
        """Create OllamaClient instances for each specialized LLM role."""
        llm_config = self.config.get("auto_agent_llms", {}) # Assuming auto_agent_llms is common config
        timeout_config = self.config.get("auto_agent_timeouts", {})

        for role, model_key, default_model, default_timeout in self.LLM_ROLES:
            self.llm_clients[role] = OllamaClient(
                url=self.url,
                model=llm_config.get(model_key, default_model),
                timeout=timeout_config.get(role, default_timeout),
                logger=self.logger,
                config=self.config,
            )
        self.logger.info("CoreAgent LLM clients initialized.")

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
        """Scan Python files for import statements and return a list of pip-installable packages."""
        import_pattern = re.compile(
            r'^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.MULTILINE
        )
        top_level_modules = set()

        for path, content in files.items():
            if not path.endswith(".py") or not content:
                continue
            for match in import_pattern.finditer(content):
                module = match.group(1)
                top_level_modules.add(module)

        # Filter out stdlib and local project imports
        third_party = set()
        for mod in top_level_modules:
            if mod in self._PYTHON_STDLIB:
                continue
            pkg = self._IMPORT_TO_PACKAGE.get(mod, mod)
            third_party.add(pkg)

        return sorted(third_party)

    def _scan_node_imports(self, files: Dict[str, str]) -> List[str]:
        """Scan JS/TS files for require/import statements and return npm package names."""
        require_pattern = re.compile(r"""require\s*\(\s*['"]([^'"./][^'"]*)['"]\s*\)""")
        import_pattern = re.compile(r"""(?:import\s+.*?\s+from|import)\s+['"]([^'"./][^'"]*)['"]\s*;?""")

        packages = set()
        js_extensions = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")

        for path, content in files.items():
            if not any(path.endswith(ext) for ext in js_extensions) or not content:
                continue
            for match in require_pattern.finditer(content):
                pkg = match.group(1)
                if pkg.startswith("@"):
                    parts = pkg.split("/")
                    pkg = "/".join(parts[:2]) if len(parts) >= 2 else pkg
                else:
                    pkg = pkg.split("/")[0]
                packages.add(pkg)
            for match in import_pattern.finditer(content):
                pkg = match.group(1)
                if pkg.startswith("@"):
                    parts = pkg.split("/")
                    pkg = "/".join(parts[:2]) if len(parts) >= 2 else pkg
                else:
                    pkg = pkg.split("/")[0]
                packages.add(pkg)

        third_party = {p for p in packages if p not in self._NODE_BUILTINS
                       and not p.startswith("node:")}
        return sorted(third_party)

    def _scan_go_imports(self, files: Dict[str, str]) -> List[str]:
        """Scan Go files for import statements and return third-party module paths."""
        single_pattern = re.compile(r'^\s*import\s+"([^"]+)"', re.MULTILINE)
        block_pattern = re.compile(r'import\s*\((.*?)\)', re.DOTALL)
        quoted_pattern = re.compile(r'"([^"]+)"')

        modules = set()

        for path, content in files.items():
            if not path.endswith(".go") or not content:
                continue
            for match in single_pattern.finditer(content):
                modules.add(match.group(1))
            for block in block_pattern.finditer(content):
                for quoted in quoted_pattern.finditer(block.group(1)):
                    modules.add(quoted.group(1))

        third_party = set()
        for mod in modules:
            top = mod.split("/")[0]
            if top in self._GO_STDLIB:
                continue
            if "." in top:
                third_party.add(mod)

        return sorted(third_party)

    def _scan_rust_imports(self, files: Dict[str, str]) -> List[str]:
        """Scan Rust files for extern crate statements and return crate names."""
        crate_pattern = re.compile(r'^\s*extern\s+crate\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.MULTILINE)
        use_pattern = re.compile(r'^\s*use\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:::|;)', re.MULTILINE)

        rust_stdlib = {"std", "core", "alloc", "proc_macro", "test"}
        crates = set()

        for path, content in files.items():
            if not path.endswith(".rs") or not content:
                continue
            for match in crate_pattern.finditer(content):
                crate = match.group(1)
                if crate not in rust_stdlib:
                    crates.add(crate)
            for match in use_pattern.finditer(content):
                crate = match.group(1)
                if crate not in rust_stdlib:
                    crates.add(crate)

        return sorted(crates)

    def _reconcile_requirements(
        self, files: Dict[str, str], project_root: Path
    ) -> Dict[str, str]:
        """Reconcile dependency files with actual imports.

        Supports multiple languages:
        - Python: requirements.txt from actual imports in .py files
        - Node.js: package.json dependencies from require/import in .js/.ts files
        - Go: go.mod require block from import statements in .go files
        - Rust: Cargo.toml [dependencies] from extern crate/use in .rs files
        """
        files = self._reconcile_python_requirements(files, project_root)
        files = self._reconcile_package_json(files, project_root)
        files = self._reconcile_go_mod(files, project_root)
        files = self._reconcile_cargo_toml(files, project_root)
        return files

    def _reconcile_python_requirements(
        self, files: Dict[str, str], project_root: Path
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
                new_req = "\n".join(scanned_packages) + "\n"
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
        """Select contextually relevant files for generation rather than just the last N.

        Prioritizes:
        - Files in the same directory
        - For frontend files: backend route/API files
        - For dependency files: source files (to infer actual dependencies)
        - Falls back to the most recently generated files
        """
        if not generated_files:
            return {}

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
