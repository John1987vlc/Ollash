from collections import defaultdict  # NEW
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Interfaces
from backend.interfaces.imodel_provider import IModelProvider
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.code_quarantine import CodeQuarantine
from backend.utils.core.dependency_graph import DependencyGraph
from backend.utils.core.documentation_manager import DocumentationManager
from backend.utils.core.error_knowledge_base import ErrorKnowledgeBase
from backend.utils.core.event_publisher import EventPublisher
from backend.utils.core.file_manager import FileManager
from backend.utils.core.file_validator import FileValidator
from backend.utils.core.fragment_cache import FragmentCache
from backend.utils.core.llm_response_parser import LLMResponseParser
from backend.utils.core.parallel_generator import ParallelFileGenerator  # NEW
from backend.utils.core.permission_profiles import PolicyEnforcer
from backend.utils.core.scanners.rag_context_selector import RAGContextSelector  # NEW
from backend.utils.domains.auto_generation.contingency_planner import ContingencyPlanner
from backend.utils.domains.auto_generation.file_completeness_checker import FileCompletenessChecker
from backend.utils.domains.auto_generation.file_content_generator import FileContentGenerator
from backend.utils.domains.auto_generation.file_refiner import FileRefiner
from backend.utils.domains.auto_generation.improvement_planner import ImprovementPlanner
from backend.utils.domains.auto_generation.improvement_suggester import ImprovementSuggester
from backend.utils.domains.auto_generation.multi_language_test_generator import MultiLanguageTestGenerator

# Specialized AutoAgent services
from backend.utils.domains.auto_generation.project_planner import ProjectPlanner
from backend.utils.domains.auto_generation.project_reviewer import ProjectReviewer
from backend.utils.domains.auto_generation.senior_reviewer import SeniorReviewer
from backend.utils.domains.auto_generation.structure_generator import StructureGenerator
from backend.utils.domains.auto_generation.structure_pre_reviewer import StructurePreReviewer


class PhaseContext:
    """
    A container for all services and managers required by the AutoAgent phases.
    This simplifies dependency injection into individual phase classes.
    """

    # File categories for intelligent context selection (Moved from CoreAgent)
    _FRONTEND_EXTENSIONS = {
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".vue",
        ".svelte",
        ".html",
        ".css",
        ".scss",
        ".less",
    }
    _BACKEND_ROUTE_PATTERNS = {"routes", "views", "api", "endpoints", "controllers"}
    _DEPENDENCY_FILES = {
        "requirements.txt",
        "package.json",
        "Cargo.toml",
        "go.mod",
        "Gemfile",
        "pyproject.toml",
        "build.gradle",
        "pom.xml",
        "Dockerfile",
    }

    def __init__(
        self,
        config: Dict[str, Any],
        logger: AgentLogger,
        ollash_root_dir: Path,
        llm_manager: IModelProvider,
        response_parser: LLMResponseParser,
        file_manager: FileManager,
        file_validator: FileValidator,
        documentation_manager: DocumentationManager,
        event_publisher: EventPublisher,
        code_quarantine: CodeQuarantine,
        fragment_cache: FragmentCache,
        dependency_graph: DependencyGraph,
        parallel_generator: ParallelFileGenerator,
        error_knowledge_base: ErrorKnowledgeBase,
        policy_enforcer: PolicyEnforcer,
        rag_context_selector: RAGContextSelector,  # NEW
        # Specialized AutoAgent services
        project_planner: ProjectPlanner,
        structure_generator: StructureGenerator,
        file_content_generator: FileContentGenerator,
        file_refiner: FileRefiner,
        file_completeness_checker: FileCompletenessChecker,
        project_reviewer: ProjectReviewer,
        improvement_suggester: ImprovementSuggester,
        improvement_planner: ImprovementPlanner,
        senior_reviewer: SeniorReviewer,
        test_generator: MultiLanguageTestGenerator,
        contingency_planner: ContingencyPlanner,
        structure_pre_reviewer: StructurePreReviewer,
        generated_projects_dir: Path,
        auto_agent: Any = None,  # Temporary for now, to allow calling _reconcile_requirements from AutoAgent
    ):
        self.config = config
        self.logger = logger
        self.ollash_root_dir = ollash_root_dir
        self.llm_manager = llm_manager
        self.response_parser = response_parser
        self.file_manager = file_manager
        self.file_validator = file_validator
        self.documentation_manager = documentation_manager
        self.event_publisher = event_publisher
        self.code_quarantine = code_quarantine
        self.fragment_cache = fragment_cache
        self.dependency_graph = dependency_graph
        self.parallel_generator = parallel_generator
        self.error_knowledge_base = error_knowledge_base
        self.policy_enforcer = policy_enforcer
        self.rag_context_selector = rag_context_selector  # NEW
        self.auto_agent = auto_agent

        self.project_planner = project_planner
        self.structure_generator = structure_generator
        self.file_content_generator = file_content_generator
        self.file_refiner = file_refiner
        self.file_completeness_checker = file_completeness_checker
        self.project_reviewer = project_reviewer
        self.improvement_suggester = improvement_suggester
        self.improvement_planner = improvement_planner
        self.senior_reviewer = senior_reviewer
        self.test_generator = test_generator
        self.contingency_planner = contingency_planner
        self.structure_pre_reviewer = structure_pre_reviewer
        self.generated_projects_dir = generated_projects_dir

        self.current_generated_files: Dict[str, str] = {}
        self.current_project_structure: Dict[str, Any] = {}
        self.current_file_paths: List[str] = []
        self.current_readme_content: str = ""
        self.logic_plan: Dict[str, Dict[str, Any]] = {}  # NEW: Store implementation plans

    def update_generated_data(
        self,
        generated_files: Dict[str, str],
        project_structure: Dict[str, Any],
        file_paths: List[str],
        readme_content: str,
    ):
        """Updates the current state of generated data within the context."""
        self.current_generated_files.update(generated_files)
        self.current_project_structure = project_structure
        self.current_file_paths = file_paths
        self.current_readme_content = readme_content

    def select_related_files(
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
                self.logger.info(f"🔍 Selected {len(context_files)} contextual files using RAG semantic search")
                return context_files
        except Exception as e:
            self.logger.info(f"RAG selection unavailable, using heuristic scoring: {e}")

        # Fallback: Heuristic scoring (original behavior from CoreAgent)
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

    # ========== NEW HELPER METHODS MOVED FROM AutoAgent ==========

    def infer_language(self, file_path: str) -> str:
        """Infer programming language from file path."""
        ext = Path(file_path).suffix.lower()
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
        }
        return language_map.get(ext, "unknown")

    def group_files_by_language(self, files: Dict[str, str]) -> Dict[str, List[Tuple[str, str]]]:
        """Group files by programming language."""
        grouped = defaultdict(list)

        for rel_path, content in files.items():
            language = self.infer_language(rel_path)
            if language != "unknown":
                grouped[language].append((rel_path, content))

        return dict(grouped)

    def get_test_file_path(self, source_file: str, language: str) -> str:
        """Get test file path based on language conventions."""
        source_path = Path(source_file)

        # Language-specific test path patterns
        patterns = {
            "python": lambda p: str(Path("tests") / f"test_{p}.py"),
            "javascript": lambda p: str(Path("tests") / f"{p}.test.js"),
            "typescript": lambda p: str(Path("tests") / f"{p}.test.ts"),
            "go": lambda p: str(Path(p).parent / f"{p}_test.go"),
            "rust": lambda p: str(Path("tests") / f"{p}.rs"),
            "java": lambda p: str(Path("src/test/java") / f"{p}Test.java"),
        }

        stem = source_path.stem
        pattern_fn = patterns.get(language, lambda p: str(Path("tests") / f"test_{p}"))
        return pattern_fn(stem)

    def implement_plan(
        self,
        plan: Dict,
        project_root: Path,
        readme: str,
        structure: Dict,
        files: Dict[str, str],
        file_paths: List[str],
    ) -> Tuple[Dict[str, str], Dict, List[str]]:
        """Implement contingency plan from planner."""
        actions = plan.get("actions", [])
        self.logger.info(f"Implementing {len(actions)} contingency actions...")

        for action in actions[:10]:  # Limit to 10 actions
            action_type = action.get("type")

            if action_type == "create_file":
                target_path = action.get("path")
                content = action.get("content", "")
                if target_path:
                    files[target_path] = content
                    self.file_manager.write_file(project_root / target_path, content)
                    if target_path not in file_paths:
                        file_paths.append(target_path)

            elif action_type == "modify_file":
                target_path = action.get("path")
                changes = action.get("changes", {})
                if target_path and target_path in files:
                    content = files[target_path]
                    # Simple text replacement for changes
                    for old_text, new_text in changes.items():
                        content = content.replace(old_text, new_text)
                    files[target_path] = content
                    self.file_manager.write_file(project_root / target_path, content)

            elif action_type == "refine_file":
                target_path = action.get("path")
                issues = action.get("issues", [])
                if target_path and target_path in files:
                    try:
                        refined = self.file_refiner.refine_file(target_path, files[target_path], readme[:2000], issues)
                        if refined:
                            files[target_path] = refined
                            self.file_manager.write_file(project_root / target_path, refined)
                    except Exception as e:
                        self.logger.error(f"Error refining {target_path}: {e}")

        return files, structure, file_paths

    def ingest_existing_project(self, project_path: Path) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        """
        Loads an existing project into the agent's state.

        This method:
        1. Reads all source files from the project
        2. Reconstructs the project structure
        3. Extracts README if exists
        4. Updates internal state with loaded data

        Args:
            project_path: Root path of the existing project

        Returns:
            Tuple of (generated_files, initial_structure, file_paths)
        """
        self.logger.info(f"🔍 Ingesting existing project from {project_path}")

        loaded_files: Dict[str, str] = {}
        file_paths: List[str] = []
        readme_content: str = ""
        structure: Dict[str, Any] = {}

        # Define extensions and directories to load (exclude build, cache, etc)
        source_extensions = {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".go",
            ".rs",
            ".java",
            ".cpp",
            ".c",
            ".cs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".json",
            ".yaml",
            ".yml",
            ".xml",
            ".md",
            ".txt",
            ".html",
            ".css",
            ".scss",
            ".less",
        }

        exclude_dirs = {
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            ".cache",
            "dist",
            "build",
            ".pytest_cache",
            ".mypy_cache",
            ".egg-info",
            ".idea",
            ".vscode",
            "target",
        }

        try:
            project_path = Path(project_path)
            if not project_path.exists():
                self.logger.error(f"Project path does not exist: {project_path}")
                return {}, {}, []

            # Walk through project directory
            for root, dirs, files_in_dir in __import__("os").walk(project_path):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if d not in exclude_dirs]

                for file in files_in_dir:
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(project_path)

                    # Check if file should be loaded
                    if file_path.suffix.lower() not in source_extensions:
                        continue

                    # Handle special files
                    if file.lower() == "readme.md":
                        try:
                            readme_content = self.file_manager.read_file(str(file_path))
                        except Exception as e:
                            self.logger.warning(f"Could not read README: {e}")
                        continue

                    # Load file content
                    try:
                        content = self.file_manager.read_file(str(file_path))
                        rel_path_str = str(rel_path).replace("\\", "/")
                        loaded_files[rel_path_str] = content
                        file_paths.append(rel_path_str)

                        self.logger.debug(f"  Loaded: {rel_path_str} ({len(content)} bytes)")
                    except Exception as e:
                        self.logger.warning(f"Could not load {rel_path}: {e}")

            # Build structure from loaded files
            structure = self._build_structure_from_files(loaded_files)

            # Update context state
            self.update_generated_data(loaded_files, structure, file_paths, readme_content)
            self.logger.info(f"✅ Ingested {len(loaded_files)} files from existing project")

            return loaded_files, structure, file_paths

        except Exception as e:
            self.logger.error(f"Error ingesting project: {e}")
            return {}, {}, []

    def _build_structure_from_files(self, files: Dict[str, str]) -> Dict[str, Any]:
        """
        Reconstructs project structure from loaded files.
        Groups files by directory and type.
        """
        structure: Dict[str, Any] = {}

        for file_path in files.keys():
            parts = Path(file_path).parts
            current = structure

            # Navigate/create directory structure
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Mark file in structure
            filename = parts[-1] if parts else file_path
            current[filename] = {
                "type": "file",
                "extension": Path(filename).suffix,
                "language": self.infer_language(filename),
            }

        return structure
