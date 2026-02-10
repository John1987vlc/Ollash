import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.token_tracker import TokenTracker
from src.utils.core.llm_response_parser import LLMResponseParser
from src.utils.core.file_validator import FileValidator
from src.utils.domains.auto_generation.project_planner import ProjectPlanner
from src.utils.domains.auto_generation.structure_generator import StructureGenerator
from src.utils.domains.auto_generation.file_content_generator import FileContentGenerator
from src.utils.domains.auto_generation.file_refiner import FileRefiner
from src.utils.domains.auto_generation.file_completeness_checker import FileCompletenessChecker
from src.utils.domains.auto_generation.project_reviewer import ProjectReviewer
from src.utils.domains.auto_generation.improvement_suggester import ImprovementSuggester
from src.utils.domains.auto_generation.improvement_planner import ImprovementPlanner
from src.utils.domains.auto_generation.senior_reviewer import SeniorReviewer


class AutoAgent:
    """Orchestrates the multi-phase project creation pipeline.

    Phases:
        1. README generation (planner LLM)
        2. JSON structure generation (prototyper LLM)
        3. Empty file scaffolding
        4. File content generation (prototyper LLM)
        5. File refinement (coder LLM)
        5.5. Verification loop - validate & fix (coder LLM)
        6. Final review (generalist LLM)
        7. Iterative Improvement (suggester, improvement_planner, coder)
        8. Senior Review (senior_reviewer)
    """

    LLM_ROLES = [
        ("prototyper", "prototyper_model", "gpt-oss:20b", 600),
        ("coder", "coder_model", "qwen3-coder:30b", 480),
        ("planner", "planner_model", "ministral-3:14b", 900),
        ("generalist", "generalist_model", "ministral-3:8b", 300),
        ("suggester", "suggester_model", "ministral-3:8b", 300), # Using generalist model for suggestions
        ("improvement_planner", "improvement_planner_model", "ministral-3:14b", 900), # Using planner model for planning
        ("senior_reviewer", "senior_reviewer_model", "ministral-3:14b", 900), # Needs strong reasoning for complex analysis
    ]

    def __init__(self, config_path: str = "config/settings.json", ollash_root_dir: Optional[Path] = None):
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.ollash_root_dir = ollash_root_dir if ollash_root_dir else Path(os.getcwd())
        log_file_path = self.ollash_root_dir / "logs" / "auto_agent.log"

        self.url = os.environ.get(
            "OLLASH_OLLAMA_URL",
            os.environ.get("MOLTBOT_OLLAMA_URL",
            self.config.get("ollama_url", "http://localhost:11434")),
        )
        self.logger = AgentLogger(log_file=str(log_file_path))
        self.token_tracker = TokenTracker()
        self.response_parser = LLMResponseParser()
        self.file_validator = FileValidator(logger=self.logger)

        self.llm_clients: Dict[str, OllamaClient] = {}
        self._initialize_llm_clients()

        # Phase services (dependency injection)
        self.planner = ProjectPlanner(self.llm_clients["planner"], self.logger)
        self.structure_gen = StructureGenerator(
            self.llm_clients["prototyper"], self.logger, self.response_parser
        )
        self.content_gen = FileContentGenerator(
            self.llm_clients["prototyper"], self.logger, self.response_parser
        )
        self.refiner = FileRefiner(
            self.llm_clients["coder"], self.logger, self.response_parser
        )
        self.completeness_checker = FileCompletenessChecker(
            self.llm_clients["coder"],
            self.logger,
            self.response_parser,
            self.file_validator,
            max_retries_per_file=2,
        )
        self.reviewer = ProjectReviewer(self.llm_clients["generalist"], self.logger)
        self.suggester = ImprovementSuggester(
            self.llm_clients["suggester"], self.logger, self.response_parser
        )
        self.improvement_planner = ImprovementPlanner(
            self.llm_clients["improvement_planner"], self.logger, self.response_parser
        )
        self.senior_reviewer = SeniorReviewer( # New Service
            self.llm_clients["senior_reviewer"], self.logger, self.response_parser
        )

        self.generated_projects_dir = self.ollash_root_dir / "generated_projects" / "auto_agent_projects"
        self.generated_projects_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("AutoAgent initialized.")

    def _initialize_llm_clients(self):
        """Create OllamaClient instances for each specialized LLM role."""
        llm_config = self.config.get("auto_agent_llms", {})
        timeout_config = self.config.get("auto_agent_timeouts", {})

        for role, model_key, default_model, default_timeout in self.LLM_ROLES:
            self.llm_clients[role] = OllamaClient(
                url=self.url,
                model=llm_config.get(model_key, default_model),
                timeout=timeout_config.get(role, default_timeout),
                logger=self.logger,
                config=self.config,
            )
        self.logger.info("AutoAgent LLM clients initialized.")

    def create_project(self, project_description: str, project_name: str = "new_project", num_refine_loops: int = 0) -> Path:
        """Orchestrate the full project creation pipeline.

        Returns the path to the generated project root.
        """
        project_root = self.generated_projects_dir / project_name
        project_root.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"[PROJECT_NAME:{project_name}] Starting project '{project_name}' at {project_root}")

        # Phase 1: README
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 1: Generating README.md...")
        readme = self.planner.generate_readme(project_description)
        self._save_file(project_root / "README.md", readme)
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 1 complete.")

        # Phase 2: JSON structure
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2: Generating project structure...")
        structure = self.structure_gen.generate(readme, max_retries=3)
        if not structure or (not structure.get("files") and not structure.get("folders")):
            self.logger.error(f"[PROJECT_NAME:{project_name}] Could not generate valid structure. Using fallback.")
            structure = StructureGenerator.create_fallback_structure(readme)
        self._save_file(project_root / "project_structure.json", json.dumps(structure, indent=2))
        file_paths = StructureGenerator.extract_file_paths(structure)
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2 complete: {len(file_paths)} files planned.")

        # Phase 3: Empty files
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 3: Creating empty placeholders...")
        StructureGenerator.create_empty_files(project_root, structure)
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 3 complete.")

        # Phase 4: Content generation
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 4: Generating file contents...")
        files: Dict[str, str] = {}
        for idx, rel_path in enumerate(file_paths, 1):
            self.logger.info(f"  [{idx}/{len(file_paths)}] {rel_path}")
            try:
                related = self._select_related_files(rel_path, files)
                content = self.content_gen.generate_file(
                    rel_path, readme, structure, related
                )
                files[rel_path] = content or ""
                if content:
                    self._save_file(project_root / rel_path, content)
            except Exception as e:
                self.logger.error(f"  Error generating {rel_path}: {e}")
                files[rel_path] = ""
        self.logger.info("PHASE 4 complete.")

        # Phase 5: Refinement
        self.logger.info("PHASE 5: Refining files...")
        for idx, (rel_path, content) in enumerate(list(files.items()), 1):
            if not content or len(content) < 10:
                continue
            self.logger.info(f"  [{idx}/{len(file_paths)}] Refining {rel_path}")
            try:
                # The refiner's generate_file method expects readme_excerpt, not the whole thing
                refined = self.refiner.refine_file(rel_path, content, readme[:1000])
                if refined:
                    files[rel_path] = refined
                    self._save_file(project_root / rel_path, refined)
            except Exception as e:
                self.logger.error(f"  Error refining {rel_path}: {e}")
        self.logger.info("PHASE 5 complete.")

        # Phase 5.5: Verification loop
        self.logger.info("PHASE 5.5: Verification loop...")
        files = self.completeness_checker.verify_and_fix(files, readme[:1000])
        for rel_path, content in files.items():
            if content:
                self._save_file(project_root / rel_path, content)
        self.logger.info("PHASE 5.5 complete.")

        # Phase 5.6: Dependency reconciliation (requirements.txt from actual imports)
        self.logger.info("PHASE 5.6: Reconciling dependency files with actual imports...")
        files = self._reconcile_requirements(files, project_root)
        self.logger.info("PHASE 5.6 complete.")

        # Phase 6: Final review
        self.logger.info("PHASE 6: Final review...")
        validation_summary = self.completeness_checker.get_validation_summary(files)
        try:
            review = self.reviewer.review(project_name, readme[:500], file_paths, validation_summary)
            self._save_file(project_root / "PROJECT_REVIEW.md", review)
        except Exception as e:
            self.logger.error(f"Error during review: {e}")

        # New Iterative Improvement Phase (Phase 7)
        if num_refine_loops > 0:
            self.logger.info(f"PHASE 7: Starting Iterative Improvement Loops ({num_refine_loops} loops)...")
            for loop_num in range(num_refine_loops):
                self.logger.info(f"PHASE 7: Iteration {loop_num + 1}/{num_refine_loops}")

                # 1. Suggest improvements
                suggestions = self.suggester.suggest_improvements(
                    project_description, readme, structure, files, loop_num
                )
                self.logger.info(f"  Suggested Improvements ({len(suggestions)}): {', '.join(suggestions[:3])}...")
                if not suggestions:
                    self.logger.info("  No further improvements suggested. Ending refinement loops.")
                    break

                # 2. Plan improvements
                plan = self.improvement_planner.generate_plan(
                    suggestions, project_description, readme, structure, files
                )
                if not plan or not plan.get("actions"):
                    self.logger.warning("  Improvement plan could not be generated or was empty. Skipping this iteration.")
                    continue
                self.logger.info(f"  Improvement Plan generated with {len(plan.get('actions', []))} actions.")

                # 3. Implement improvements
                self.logger.info("  Implementing plan...")
                files, structure, file_paths = self._implement_plan(
                    plan, project_root, readme, structure, files, file_paths
                )

                # Re-run refinement and verification after each loop to ensure quality
                self.logger.info(f"  Re-running Phase 5: Refinement after improvement loop {loop_num + 1}...")
                for idx, (rel_path, content) in enumerate(list(files.items()), 1):
                    if not content or len(content) < 10:
                        continue
                    self.logger.info(f"    Refining {rel_path}")
                    try:
                        # The refiner's generate_file method expects readme_excerpt, not the whole thing
                        refined = self.refiner.refine_file(rel_path, content, readme[:1000])
                        if refined:
                            files[rel_path] = refined
                            self._save_file(project_root / rel_path, refined)
                    except Exception as e:
                        self.logger.error(f"    Error refining {rel_path}: {e}")

                self.logger.info(f"  Re-running Phase 5.5: Verification after improvement loop {loop_num + 1}...")
                files = self.completeness_checker.verify_and_fix(files, readme[:1000])
                for rel_path, content in files.items():
                    if content:
                        self._save_file(project_root / rel_path, content)

            self.logger.info("PHASE 7: Iterative Improvement complete.")
        
        # Phase 7.5: Content completeness check
        self.logger.info("PHASE 7.5: Checking content completeness (placeholder detection)...")
        incomplete_files = []
        for rel_path, content in files.items():
            if not content:
                continue
            warning = self.file_validator.check_content_completeness(rel_path, content)
            if warning:
                self.logger.warning(f"  INCOMPLETE: {rel_path} — {warning}")
                incomplete_files.append(rel_path)

        if incomplete_files:
            self.logger.info(f"  Found {len(incomplete_files)} incomplete files, attempting to complete them...")
            for rel_path in incomplete_files:
                content = files[rel_path]
                try:
                    issues = [{"description": "File contains placeholder/stub content that needs real implementation",
                               "severity": "major",
                               "recommendation": "Replace all TODO, placeholder, and stub content with real implementations"}]
                    refined = self.refiner.refine_file(rel_path, content, readme[:2000], issues)
                    if refined:
                        files[rel_path] = refined
                        self._save_file(project_root / rel_path, refined)
                        self.logger.info(f"    Completed: {rel_path}")
                except Exception as e:
                    self.logger.error(f"    Error completing {rel_path}: {e}")

            # Re-verify after completing
            files = self.completeness_checker.verify_and_fix(files, readme[:2000])
            for rel_path, content in files.items():
                if content:
                    self._save_file(project_root / rel_path, content)
        self.logger.info("PHASE 7.5 complete.")

        # Senior Review Phase (Phase 8)
        self.logger.info("PHASE 8: Starting Senior Review...")
        review_passed = False
        review_attempt = 0
        max_review_attempts = 3
        while not review_passed and review_attempt < max_review_attempts:
            review_attempt += 1
            self.logger.info(f"PHASE 8: Senior Review Attempt {review_attempt}/{max_review_attempts}...")

            review_results = self.senior_reviewer.perform_review(
                project_description, project_name, readme, structure, files, review_attempt
            )

            if review_results.get("status") == "passed":
                review_passed = True
                self.logger.info("PHASE 8: Senior Review Passed!")
                self._save_file(project_root / "SENIOR_REVIEW_SUMMARY.md", review_results.get("summary", "Senior review passed."))
            else:
                issues = review_results.get("issues", [])
                self.logger.warning(f"PHASE 8: Senior Review Failed. Issues found: {len(issues)}")

                # Save detailed issue log
                issue_log = f"# Senior Review Issues — Attempt {review_attempt}\n\n"
                issue_log += f"**Summary:** {review_results.get('summary', 'N/A')}\n\n"
                for i, issue in enumerate(issues, 1):
                    issue_log += (
                        f"## Issue {i}: [{issue.get('severity', 'unknown').upper()}]\n"
                        f"**File:** {issue.get('file', 'N/A')}\n"
                        f"**Description:** {issue.get('description', 'N/A')}\n"
                        f"**Recommendation:** {issue.get('recommendation', 'N/A')}\n\n"
                    )
                self._save_file(project_root / f"SENIOR_REVIEW_ISSUES_ATTEMPT_{review_attempt}.md", issue_log)

                if issues:
                    self.logger.info("  Attempting targeted fixes based on senior review issues...")

                    # Group issues by file for targeted refinement
                    files_with_issues = set()
                    general_issues = []
                    for issue in issues:
                        file_value = issue.get("file")
                        if file_value:
                            if isinstance(file_value, list):
                                # If LLM hallucinates a list for file, convert to a string
                                file_value = str(file_value)
                                self.logger.warning(f"  Senior Review: 'file' field was a list, converted to string: {file_value}")
                            files_with_issues.add(file_value)
                        else:
                            general_issues.append(issue)

                    # Fix files that have specific issues
                    for rel_path in files_with_issues:
                        if rel_path not in files or not files[rel_path] or len(files[rel_path]) < 10:
                            continue
                        self.logger.info(f"    Fixing {rel_path} (targeted)...")
                        try:
                            file_issues = [iss for iss in issues if iss.get("file") == rel_path]
                            refined = self.refiner.refine_file(
                                rel_path, files[rel_path], readme[:2000], file_issues
                            )
                            if refined:
                                files[rel_path] = refined
                                self._save_file(project_root / rel_path, refined)
                        except Exception as e:
                            self.logger.error(f"    Error fixing {rel_path}: {e}")

                    # For general issues without a specific file, refine all non-trivial files
                    if general_issues:
                        self.logger.info(f"  Applying {len(general_issues)} general fixes across all files...")
                        for rel_path, content in list(files.items()):
                            if not content or len(content) < 10 or rel_path in files_with_issues:
                                continue
                            try:
                                refined = self.refiner.refine_file(
                                    rel_path, content, readme[:2000], general_issues
                                )
                                if refined:
                                    files[rel_path] = refined
                                    self._save_file(project_root / rel_path, refined)
                            except Exception as e:
                                self.logger.error(f"    Error refining {rel_path}: {e}")

                    self.logger.info("  Re-running verification after senior review fixes...")
                    files = self.completeness_checker.verify_and_fix(files, readme[:2000])
                    for rel_path, content in files.items():
                        if content:
                            self._save_file(project_root / rel_path, content)
                else:
                    self.logger.warning("  No specific issues provided by senior reviewer to fix.")

        if not review_passed:
            self.logger.error("PHASE 8: Senior Review failed after multiple attempts. Manual intervention may be required.")
            self._save_file(project_root / "SENIOR_REVIEW_FAILED.md", "Senior review failed after multiple attempts.")
        
        self.logger.info(f"Project '{project_name}' completed at {project_root}")
        self.logger.info(f"  Generated {len(file_paths)} files")
        return project_root

    def _implement_plan(
        self,
        plan: Dict,
        project_root: Path,
        readme_content: str,
        json_structure: Dict,
        current_files: Dict[str, str],
        current_file_paths: List[str]
    ) -> Tuple[Dict[str, str], Dict, List[str]]:
        """Implements the given plan, updating files and structure."""
        actions = plan.get("actions", [])
        updated_files = current_files.copy()
        updated_structure = json_structure.copy()
        updated_file_paths = current_file_paths.copy()

        for action in actions:
            action_type = action.get("type")
            path = action.get("path")
            content = action.get("content") # For 'create' or 'modify'
            target_folder = action.get("target_folder") # For 'create_folder'

            if not path and action_type != "create_folder":
                self.logger.warning(f"  Skipping action due to missing path: {action}")
                continue

            abs_path = project_root / Path(path) if path else None

            try:
                if action_type == "create_file":
                    self.logger.info(f"    Creating new file: {path}")
                    # Use content_gen to generate new file content, or use provided content
                    generated_content = content
                    if not generated_content:
                        generated_content = self.content_gen.generate_file(
                            path, readme_content, updated_structure, updated_files
                        )
                    if generated_content:
                        self._save_file(abs_path, generated_content)
                        updated_files[path] = generated_content
                        # Update structure and file_paths (simplified, might need more robust update)
                        if path not in updated_file_paths:
                            updated_file_paths.append(path)
                        # More complex logic needed to insert into json_structure dict based on path

                elif action_type == "modify_file":
                    self.logger.info(f"    Modifying file: {path}")
                    if abs_path and abs_path.exists():
                        current_file_content = abs_path.read_text(encoding="utf-8")
                        # Use refiner to apply changes, or apply provided content directly
                        modified_content = content
                        if not modified_content:
                            modified_content = self.refiner.refine_file(
                                path, current_file_content, readme_content[:1000]
                            )
                        if modified_content:
                            self._save_file(abs_path, modified_content)
                            updated_files[path] = modified_content
                    else:
                        self.logger.warning(f"    File not found for modification: {path}")

                elif action_type == "create_folder":
                    self.logger.info(f"    Creating new folder: {target_folder}")
                    folder_path = project_root / Path(target_folder)
                    folder_path.mkdir(parents=True, exist_ok=True)
                    # More complex logic needed to insert into json_structure dict based on path

                elif action_type == "delete_file":
                    self.logger.info(f"    Deleting file: {path}")
                    if abs_path and abs_path.exists():
                        abs_path.unlink()
                        if path in updated_files:
                            del updated_files[path]
                        if path in updated_file_paths:
                            updated_file_paths.remove(path)
                    # More complex logic needed to remove from json_structure dict

                else:
                    self.logger.warning(f"    Unknown action type: {action_type}")

            except Exception as e:
                self.logger.error(f"  Error during plan implementation for {path}: {e}")

        # After all actions, re-extract file paths from the (potentially updated) structure
        # This is a robust way to ensure file_paths is consistent
        # For now, a simplified update to json_structure is used, more robust update is needed.
        # updated_file_paths = StructureGenerator.extract_file_paths(updated_structure)

        return updated_files, updated_structure, updated_file_paths
    
    # File categories for intelligent context selection
    _FRONTEND_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}
    _BACKEND_ROUTE_PATTERNS = {"routes", "views", "api", "endpoints", "controllers"}
    _DEPENDENCY_FILES = {"requirements.txt", "package.json", "Cargo.toml", "go.mod", "Gemfile"}

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

            # Same directory gets a boost
            if str(p.parent) == target_dir:
                score += 3

            # Frontend file generating → prioritize backend route files
            if target_ext in self._FRONTEND_EXTENSIONS:
                name_lower = p.stem.lower()
                if any(pat in name_lower for pat in self._BACKEND_ROUTE_PATTERNS):
                    score += 5
                # Also boost model files for frontend
                if "model" in name_lower:
                    score += 3

            # Dependency file generating → prioritize source files
            if target_name in self._DEPENDENCY_FILES:
                if p.suffix in (".py", ".js", ".ts", ".go", ".rs", ".rb"):
                    score += 4

            # Backend route file → prioritize model files
            if any(pat in target.stem.lower() for pat in self._BACKEND_ROUTE_PATTERNS):
                if "model" in p.stem.lower():
                    score += 4

            # Config/init files are generally useful
            if p.name in ("__init__.py", "config.py", "settings.py", "app.py"):
                score += 2

            scored[path] = score

        # Sort by score (desc), then take top max_files
        ranked = sorted(scored.keys(), key=lambda p: scored[p], reverse=True)
        selected = {p: generated_files[p] for p in ranked[:max_files]}
        return selected

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
            # Map import name to package name
            pkg = self._IMPORT_TO_PACKAGE.get(mod, mod)
            third_party.add(pkg)

        return sorted(third_party)

    def _reconcile_requirements(
        self, files: Dict[str, str], project_root: Path
    ) -> Dict[str, str]:
        """Phase 5.6: Reconcile requirements.txt with actual imports.

        If requirements.txt exists and has excessive or hallucinated deps,
        regenerate it from actual imports found in Python source files.
        """
        req_key = None
        for path in files:
            if Path(path).name == "requirements.txt":
                req_key = path
                break

        if not req_key:
            return files

        # Check if requirements seems problematic
        req_content = files[req_key]
        lines = [line.strip() for line in req_content.splitlines()
                 if line.strip() and not line.strip().startswith("#")]

        scanned_packages = self._scan_python_imports(files)

        if len(lines) > 30 or not scanned_packages:
            # Requirements is bloated OR we found no imports — regenerate from scan
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

    @staticmethod
    def _save_file(file_path: Path, content: str):
        """Save content to a file, creating parent directories as needed."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content.strip())