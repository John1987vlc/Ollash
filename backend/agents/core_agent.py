from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List

from backend.core.kernel import AgentKernel
from backend.core.language_standards import (
    BACKEND_ROUTE_PATTERNS,
    DEPENDENCY_FILES,
    FRONTEND_EXTENSIONS,
)
from backend.services.llm_client_manager import LLMClientManager
from backend.utils.core.analysis.file_validator import FileValidator
from backend.utils.core.analysis.scanners.dependency_reconciler import DependencyReconciler
from backend.utils.core.analysis.scanners.dependency_scanner import DependencyScanner
from backend.utils.core.analysis.scanners.rag_context_selector import RAGContextSelector
from backend.utils.core.command_executor import CommandExecutor
from backend.utils.core.io.documentation_manager import DocumentationManager
from backend.utils.core.llm.benchmark_model_selector import AutoModelSelector
from backend.utils.core.llm.llm_recorder import LLMRecorder
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.llm.token_tracker import TokenTracker
from backend.utils.core.memory.automatic_learning import AutomaticLearningSystem
from backend.utils.core.memory.cross_reference_analyzer import CrossReferenceAnalyzer
from backend.utils.core.system.concurrent_rate_limiter import (
    ConcurrentGPUAwareRateLimiter,
    SessionResourceManager,
)
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.core.system.permission_profiles import PermissionProfileManager, PolicyEnforcer


class CoreAgent(ABC):
    """Abstract base class for agents.

    Provides shared infrastructure: LLM client management, logging, command
    execution, dependency scanning/reconciliation, and context-file selection.
    Language-standard constants live in ``backend.core.language_standards``.
    Reconciliation logic lives in ``DependencyReconciler``.
    """

    def __init__(
        self,
        kernel: AgentKernel,
        logger_name: str = "CoreAgent",
        llm_manager: LLMClientManager = None,
        llm_recorder: LLMRecorder = None,
        dependency_scanner: DependencyScanner = None,
    ):
        self.kernel = kernel
        self.ollash_root_dir = self.kernel.ollash_root_dir
        self.config = self.kernel.get_full_config()
        self.logger = self.kernel.get_logger()
        self.llm_recorder = llm_recorder if llm_recorder else LLMRecorder(logger=self.logger)

        self.token_tracker = TokenTracker()
        self.response_parser = LLMResponseParser()

        self.command_executor = CommandExecutor(
            working_dir=str(self.ollash_root_dir),
            logger=self.logger,
            use_docker_sandbox=self.config.get("use_docker_sandbox", False),
        )

        self.file_validator = FileValidator(logger=self.logger, command_executor=self.command_executor)
        self.documentation_manager = DocumentationManager(
            project_root=self.ollash_root_dir,
            logger=self.logger,
            llm_recorder=self.llm_recorder,
            config=self.config,
        )
        self.event_publisher = EventPublisher()
        self.cross_reference_analyzer = CrossReferenceAnalyzer(
            project_root=self.ollash_root_dir,
            logger=self.logger,
            config=self.config,
            llm_recorder=self.llm_recorder,
        )

        # Architectural modules
        self.dependency_scanner = (
            dependency_scanner if dependency_scanner else DependencyScanner(logger=self.logger)
        )
        self.dependency_reconciler = DependencyReconciler(
            dependency_scanner=self.dependency_scanner,
            logger=self.logger,
        )
        chroma_db_path = str(self.ollash_root_dir / ".ollash" / "chroma_db")
        self.rag_context_selector = RAGContextSelector(self.config, chroma_db_path, None)
        self.rate_limiter = ConcurrentGPUAwareRateLimiter(logger=self.logger)
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
            tool_settings_config=self.kernel.get_tool_settings_config(),
        )
        self.policy_enforcer.set_active_profile("developer")
        self.learning_system = AutomaticLearningSystem(
            logger=self.logger,
            project_root=self.ollash_root_dir,
            settings_manager=self.config,
        )
        if llm_manager:
            self.llm_manager = llm_manager
        else:
            self.llm_manager = LLMClientManager(
                config=self.kernel.get_llm_models_config(),
                tool_settings=self.kernel.get_tool_settings_config(),
                logger=self.logger,
                recorder=self.llm_recorder,
            )

        self.logger.info(f"{logger_name} initialized with 6 architectural improvements and external LLM management.")
        self.logger.info("  ✓ DependencyScanner (multi-language decoupling)")
        self.logger.info("  ✓ RAGContextSelector (semantic context via ChromaDB)")
        self.logger.info("  ✓ ConcurrentGPUAwareRateLimiter (GPU resource management)")
        self.logger.info("  ✓ BenchmarkModelSelector (auto model optimization)")
        self.logger.info("  ✓ PermissionProfiles (fine-grained access control)")
        self.logger.info("  ✓ AutomaticLearningSystem (post-mortem pattern capture)")

    @staticmethod
    def _save_file(file_path: Path, content: str) -> None:
        """Save content to a file, creating parent directories as needed."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as fh:
            fh.write(content.strip())

    @abstractmethod
    def run(self, *args, **kwargs):
        """Abstract method to be implemented by concrete agents."""

    # ------------------------------------------------------------------
    # Dependency scanning (thin wrappers over DependencyScanner)
    # ------------------------------------------------------------------

    def _scan_python_imports(self, files: Dict[str, str]) -> List[str]:
        """Return pip-installable packages found in Python source files."""
        return self.dependency_scanner.scan_all_imports(files).get("python", [])

    def _scan_node_imports(self, files: Dict[str, str]) -> List[str]:
        """Return npm package names found in JS/TS source files."""
        return self.dependency_scanner.scan_all_imports(files).get("javascript", [])

    def _scan_go_imports(self, files: Dict[str, str]) -> List[str]:
        """Return third-party module paths found in Go source files."""
        return self.dependency_scanner.scan_all_imports(files).get("go", [])

    def _scan_rust_imports(self, files: Dict[str, str]) -> List[str]:
        """Return crate names found in Rust source files."""
        return self.dependency_scanner.scan_all_imports(files).get("rust", [])

    # ------------------------------------------------------------------
    # Dependency reconciliation (delegates to DependencyReconciler)
    # ------------------------------------------------------------------

    def _reconcile_requirements(
        self, files: Dict[str, str], project_root: Path, python_version: str
    ) -> Dict[str, str]:
        """Reconcile dependency manifests with actual imports.

        Delegates to :class:`DependencyReconciler` which supports Python,
        Node.js, Go, and Rust.
        """
        return self.dependency_reconciler.reconcile(files, project_root, python_version)

    # ------------------------------------------------------------------
    # Context-file selection
    # ------------------------------------------------------------------

    def _select_related_files(
        self, target_path: str, generated_files: Dict[str, str], max_files: int = 8
    ) -> Dict[str, str]:
        """Select contextually relevant files using semantic search (RAG).

        First attempts semantic selection via RAGContextSelector (ChromaDB
        embeddings), then falls back to heuristic scoring.

        Args:
            target_path: Path to the file needing context.
            generated_files: All available generated files.
            max_files: Maximum number of context files to select.

        Returns:
            Mapping of selected contextual files.
        """
        if not generated_files:
            return {}

        try:
            target = Path(target_path)
            context_files = self.rag_context_selector.select_relevant_files(
                query=target.stem,
                available_files=generated_files,
                max_files=max_files,
            )
            if context_files:
                self.logger.info(f"🔍 Selected {len(context_files)} contextual files using RAG semantic search")
                return context_files
        except Exception as exc:
            self.logger.info(f"RAG selection unavailable, using heuristic scoring: {exc}")

        # Heuristic fallback
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

            if target_ext in FRONTEND_EXTENSIONS:
                name_lower = p.stem.lower()
                if any(pat in name_lower for pat in BACKEND_ROUTE_PATTERNS):
                    score += 5
                if "model" in name_lower:
                    score += 3

            if target_name in DEPENDENCY_FILES:
                if p.suffix in (".py", ".js", ".ts", ".go", ".rs", ".rb"):
                    score += 4

            if any(pat in target.stem.lower() for pat in BACKEND_ROUTE_PATTERNS):
                if "model" in p.stem.lower():
                    score += 4

            if p.name in ("__init__.py", "config.py", "settings.py", "app.py"):
                score += 2

            scored[path] = score

        ranked = sorted(scored.keys(), key=lambda p: scored[p], reverse=True)
        return {p: generated_files[p] for p in ranked[:max_files]}
