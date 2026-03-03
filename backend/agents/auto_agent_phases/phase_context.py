from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

# Lightweight runtime imports (no heavy transitive deps)
from backend.core.language_standards import BACKEND_ROUTE_PATTERNS, DEPENDENCY_FILES, FRONTEND_EXTENSIONS
from backend.utils.core.language_utils import LanguageUtils
def _extract_signatures(content: str, file_path: str) -> str:
    """Lazy wrapper — defers the import of the full domains package to first use.

    Importing backend.utils.domains.* at module level triggers the domains
    __init__.py which eagerly registers all @ollash_tool decorators (~600 modules).
    Moving the import inside this shim keeps phase_context.py lightweight.
    """
    from backend.utils.domains.auto_generation.utilities.signature_extractor import (  # noqa: PLC0415
        extract_signatures,
    )
    return extract_signatures(content, file_path)

if TYPE_CHECKING:
    # All service imports are type-hint-only: moving them here prevents the full
    # dependency graph (chromadb, SQLAlchemy async, OllamaClient…) from loading
    # during pytest collection.  At runtime the objects are received as constructor
    # parameters, so the classes never need to be resolved.
    from backend.interfaces.imodel_provider import IModelProvider
    from backend.utils.core.system.agent_logger import AgentLogger
    from backend.utils.core.system.cicd_healer import CICDHealer
    from backend.utils.core.analysis.code_quarantine import CodeQuarantine
    from backend.utils.core.analysis.scanners.dependency_scanner import DependencyScanner
    from backend.utils.core.command_executor import CommandExecutor
    from backend.utils.core.analysis.dependency_graph import DependencyGraph
    from backend.utils.core.io.documentation_manager import DocumentationManager
    from backend.utils.core.memory.error_knowledge_base import ErrorKnowledgeBase
    from backend.utils.core.system.event_publisher import EventPublisher
    from backend.utils.core.io.export_manager import ExportManager
    from backend.utils.core.io.file_manager import FileManager
    from backend.utils.core.analysis.file_validator import FileValidator
    from backend.utils.core.memory.fragment_cache import FragmentCache
    from backend.utils.core.llm.llm_response_parser import LLMResponseParser
    from backend.utils.core.llm.parallel_generator import ParallelFileGenerator
    from backend.utils.core.system.permission_profiles import PolicyEnforcer
    from backend.utils.core.analysis.scanners.rag_context_selector import RAGContextSelector
    from backend.utils.core.analysis.vulnerability_scanner import VulnerabilityScanner
    from backend.utils.domains.auto_generation.contingency_planner import ContingencyPlanner
    from backend.utils.domains.auto_generation.file_completeness_checker import FileCompletenessChecker
    from backend.utils.domains.auto_generation.file_content_generator import FileContentGenerator
    from backend.utils.domains.auto_generation.file_refiner import FileRefiner
    from backend.utils.domains.auto_generation.improvement_planner import ImprovementPlanner
    from backend.utils.domains.auto_generation.improvement_suggester import ImprovementSuggester
    from backend.utils.domains.auto_generation.infra_generator import InfraGenerator
    from backend.utils.domains.auto_generation.multi_language_test_generator import MultiLanguageTestGenerator
    from backend.utils.core.llm.token_tracker import TokenTracker
    from backend.utils.domains.auto_generation.project_planner import ProjectPlanner
    from backend.utils.domains.auto_generation.project_reviewer import ProjectReviewer
    from backend.utils.domains.auto_generation.senior_reviewer import SeniorReviewer
    from backend.utils.domains.auto_generation.structure_generator import StructureGenerator
    from backend.utils.domains.auto_generation.structure_pre_reviewer import StructurePreReviewer
    # Instantiated inside __init__ — also listed here for type-checker visibility
    from backend.utils.core.memory.decision_blackboard import DecisionBlackboard


class LLMSubContext:
    """Sub-context for LLM-related services."""

    def __init__(
        self,
        llm_manager: "IModelProvider",
        response_parser: "LLMResponseParser",
        token_tracker: Optional[TokenTracker] = None,
    ):
        self.manager = llm_manager
        self.response_parser = response_parser
        self.token_tracker = token_tracker


class FileSubContext:
    """Sub-context for file operation services."""

    def __init__(
        self,
        file_manager: "FileManager",
        file_validator: "FileValidator",
        file_content_generator: "FileContentGenerator",
        file_refiner: "FileRefiner",
        file_completeness_checker: "FileCompletenessChecker",
    ):
        self.manager = file_manager
        self.validator = file_validator
        self.content_generator = file_content_generator
        self.refiner = file_refiner
        self.completeness_checker = file_completeness_checker


class ReviewSubContext:
    """Sub-context for review services."""

    def __init__(
        self,
        project_reviewer: "ProjectReviewer",
        senior_reviewer: "SeniorReviewer",
        improvement_suggester: "ImprovementSuggester",
        improvement_planner: "ImprovementPlanner",
    ):
        self.project_reviewer = project_reviewer
        self.senior_reviewer = senior_reviewer
        self.improvement_suggester = improvement_suggester
        self.improvement_planner = improvement_planner


class InfraSubContext:
    """Sub-context for infrastructure services."""

    def __init__(
        self,
        cicd_healer: Optional["CICDHealer"] = None,
        vulnerability_scanner: Optional["VulnerabilityScanner"] = None,
        infra_generator: Optional["InfraGenerator"] = None,
        export_manager: Optional["ExportManager"] = None,
    ):
        self.cicd_healer = cicd_healer
        self.vulnerability_scanner = vulnerability_scanner
        self.infra_generator = infra_generator
        self.export_manager = export_manager


class PhaseContext:
    """
    A container for all services and managers required by the AutoAgent phases.
    This simplifies dependency injection into individual phase classes.

    Sub-contexts provide grouped access:
    - context.llm → LLM manager and response parser
    - context.files → File manager, validator, generator, refiner
    - context.review → Project reviewer, senior reviewer, improvement tools
    - context.infra → CI/CD healer, vulnerability scanner, infra generator

    Backward-compatible: context.file_manager etc. still work via properties.
    """

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
        dependency_scanner: DependencyScanner,
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
        # New services for CI/CD healing, security scanning, infrastructure, and documentation
        cicd_healer: Optional[CICDHealer] = None,
        vulnerability_scanner: Optional[VulnerabilityScanner] = None,
        export_manager: Optional[ExportManager] = None,
        infra_generator: Optional[InfraGenerator] = None,
        command_executor: Optional[CommandExecutor] = None,
        decision_blackboard: Optional[DecisionBlackboard] = None,
        token_tracker: Optional[TokenTracker] = None,
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
        self.dependency_scanner = dependency_scanner
        self.parallel_generator = parallel_generator
        self.error_knowledge_base = error_knowledge_base
        self.policy_enforcer = policy_enforcer
        self.rag_context_selector = rag_context_selector  # NEW
        self.auto_agent = auto_agent
        self.token_tracker = token_tracker

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

        # New services
        self.cicd_healer = cicd_healer
        self.vulnerability_scanner = vulnerability_scanner
        self.export_manager = export_manager
        self.infra_generator = infra_generator
        self.command_executor = command_executor

        # Mejora 6a: Decision Blackboard — persists design decisions across phases
        if decision_blackboard is not None:
            self.decision_blackboard: DecisionBlackboard = decision_blackboard
        else:
            from backend.utils.core.memory.decision_blackboard import DecisionBlackboard  # noqa: PLC0415
            _db_path = ollash_root_dir / ".ollash" / "decisions.db"
            self.decision_blackboard = DecisionBlackboard(_db_path)

        self.current_generated_files: Dict[str, str] = {}
        self.current_project_structure: Dict[str, Any] = {}
        self.current_file_paths: List[str] = []
        self.current_readme_content: str = ""
        self.logic_plan: Dict[str, Dict[str, Any]] = {}  # Store implementation plans
        self.backlog: List[Dict[str, Any]] = []
        self.ollama_context = None  # F40: KV Cache context
        self.last_model = None  # F40: Track model transitions

        # F1: Clarification — Q&A pairs collected before planning
        self.clarification_answers: Dict[str, str] = {}
        self.clarified_description: str = ""

        # F2: API Contract — OpenAPI YAML written by ApiContractPhase
        self.api_contract: Optional[str] = None
        self.api_endpoints: List[Dict[str, Any]] = []

        # F3: TDD — test skeletons keyed by source file path
        self.test_skeletons: Dict[str, str] = {}

        # F4: Plan Validation — report from Architect vs Critic debate
        self.plan_validation_report: Optional[Dict[str, Any]] = None

        # F7: Component Tree — frontend hierarchy (React/Vue/Angular/Svelte)
        self.component_tree: Optional[Dict[str, Any]] = None

        # F9: Viability — cost/token estimate written by ViabilityEstimatorPhase
        self.viability_report: Optional[Dict[str, Any]] = None

        # F10: Git checkpoints — commit hashes recorded after each successful phase
        self.checkpoint_commits: List[str] = []

        # Mejora 3: Step progress tracking for prompt injection
        self.step_progress: Dict[str, Any] = {
            "current_step_index": 0,
            "total_steps": 0,
            "completed_steps": [],
            "current_objective": "",
        }

        # F3: Pre-computed API map {file_path → signature summary} for token compression
        self.api_map: Dict[str, str] = {}

        # Feature 3: Pre-fetched context cache for predictive loading
        self.prefetched_context: Dict[str, str] = {}

        # Fix 1: Module system decision ("esm" or "cjs") — set by LogicPlanningPhase
        # Shared across all JS/TS generation and test phases so they always agree.
        self.module_system: str = ""

        # Fix 2: DOM contracts — {html_file_path: [element_id, ...]}
        # Set by InterfaceScaffoldingPhase; injected into JS/HTML generation prompts.
        self.dom_contracts: Dict[str, List[str]] = {}

        # E6: last execution history summary (set by AutoAgent from AutomationManager)
        self.last_execution_summary: Optional[Any] = None
        # E2: detected tech stack information (set by ProjectAnalysisPhase)
        self.tech_stack_info: Optional[Any] = None
        # E9: lazy-initialised sandbox validator (avoids import cycles)
        self._sandbox_validator: Optional[Any] = None
        # ProjectTypeDetector result — set by ReadmeGenerationPhase (no LLM call)
        # Carries detected project type and allowed file extensions for downstream enforcement
        self.project_type_info: Optional[Any] = None

        # Sub-contexts for grouped access
        self.llm = LLMSubContext(llm_manager, response_parser, token_tracker)
        self.files_ctx = FileSubContext(
            file_manager, file_validator, file_content_generator, file_refiner, file_completeness_checker
        )
        self.review_ctx = ReviewSubContext(
            project_reviewer, senior_reviewer, improvement_suggester, improvement_planner
        )
        self.infra_ctx = InfraSubContext(cicd_healer, vulnerability_scanner, infra_generator, export_manager)

        # Utility services (extracted)
        from backend.utils.core.io.project_ingestion_service import ProjectIngestionService  # noqa: PLC0415
        self._ingestion_service = ProjectIngestionService(
            file_reader=file_manager.read_file,
            logger=logger,
        )

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

    def update_step_progress(
        self,
        current_index: int,
        total: int,
        completed: List[str],
        current_objective: str,
    ) -> None:
        """Update the step progress tracker used for prompt injection (Mejora 3).

        Args:
            current_index: 1-based index of the step just completed.
            total: Total number of steps in this phase.
            completed: List of completed step labels/IDs.
            current_objective: Short description of what is being done next.
        """
        self.step_progress["current_step_index"] = current_index
        self.step_progress["total_steps"] = total
        self.step_progress["completed_steps"] = list(completed)
        self.step_progress["current_objective"] = current_objective

    def build_api_map(self, generated_files: Dict[str, str]) -> None:
        """Pre-compute signature-only summaries for all generated source files.

        Stores results in ``self.api_map`` keyed by file path.
        Call this ONCE at the start of FileContentGenerationPhase.
        Non-source files (.md, .json, .yaml, etc.) are skipped.

        Args:
            generated_files: The current dict of all generated file contents.
        """
        _SOURCE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"}
        self.api_map.clear()
        for path, content in generated_files.items():
            if not content:
                continue
            if Path(path).suffix.lower() not in _SOURCE_EXTS:
                continue
            self.api_map[path] = _extract_signatures(content, path)
        self.logger.info(f"[PhaseContext] API map built: {len(self.api_map)} entries")

    def prefetch_context_for_phase(
        self,
        next_phase_class: type,
        generated_files: Dict[str, str],
    ) -> None:
        """Pre-compute API map signatures for files the next phase will likely need.

        Called by AutoAgent after each phase completes.  Only populates the cache
        when *next_phase_class* is ``FileContentGenerationPhase`` and the
        ``logic_plan`` is already available.  All errors are silently ignored —
        pre-fetch must never abort the pipeline.

        Results are stored in ``self.prefetched_context`` keyed by file path.
        """
        try:
            from backend.agents.auto_agent_phases.file_content_generation_phase import (
                FileContentGenerationPhase,
            )

            if next_phase_class is not FileContentGenerationPhase:
                return

            upcoming_paths = list(self.logic_plan.keys())
            added = 0
            for path in upcoming_paths:
                if path in self.prefetched_context:
                    continue  # Already cached
                content = generated_files.get(path, "")
                if content:
                    self.prefetched_context[path] = _extract_signatures(content, path)
                    added += 1
            if added:
                self.logger.info(f"[PredictiveCtx] Pre-fetched {added} entries for FileContentGenerationPhase")
        except Exception as exc:
            self.logger.debug(f"[PredictiveCtx] Pre-fetch failed (non-fatal): {exc}")

    def _is_small_model(self, role: str = "coder") -> bool:
        """Return True if the LLM for *role* has ≤8B parameters (nano tier).

        Inspects the model name string for size suffixes like '3b', '4b', '7b', '8b'.
        Falls back to False (treat as large model) on any error.

        Args:
            role: Agent role whose client to inspect (default: "coder").

        Returns:
            True if model parameter count is ≤8B, False otherwise.
        """
        import re as _re_model

        try:
            client = self.llm_manager.get_client(role)
            model_name = getattr(client, "model", "") or ""
            match = _re_model.search(r"(\d+(?:\.\d+)?)b", model_name.lower())
            if match:
                return float(match.group(1)) <= 8.0
        except Exception:
            pass
        return False

    def select_related_files(
        self,
        target_path: str,
        generated_files: Dict[str, str],
        max_files: int = 8,
        signatures_only: bool = False,
    ) -> Dict[str, str]:
        """Select contextually relevant files using semantic search (RAG).

        First attempts semantic selection via RAGContextSelector (ChromaDB embeddings),
        then falls back to heuristic scoring if semantic selection unavailable.

        Args:
            target_path: Path to file needing context.
            generated_files: All available generated files.
            max_files: Maximum context files to select.
            signatures_only: If True, returns only function/class signatures instead of
                full file content (Mejora 2). Reduces token usage for small models.

        Returns:
            Dictionary of selected contextual files, values are either full content
            or signature-only strings depending on *signatures_only*.
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
                if signatures_only:
                    return {p: _extract_signatures(c, p) for p, c in context_files.items()}
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
        selected = {p: generated_files[p] for p in ranked[:max_files]}
        if signatures_only:
            return {p: _extract_signatures(c, p) for p, c in selected.items()}
        return selected

    # ========== NEW HELPER METHODS MOVED FROM AutoAgent ==========

    def infer_language(self, file_path: str) -> str:
        """Infer programming language from file path."""
        return LanguageUtils.infer_language(file_path)

    def group_files_by_language(self, files: Dict[str, str]) -> Dict[str, List[Tuple[str, str]]]:
        """Group files by programming language."""
        return LanguageUtils.group_files_by_language(files)

    def get_test_file_path(self, source_file: str, language: str) -> str:
        """Get test file path based on language conventions."""
        return LanguageUtils.get_test_file_path(source_file, language)

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

            elif action_type == "modify_file" or action_type == "refine_file":
                target_path = action.get("path")
                issues = action.get("issues", [])
                # If issues not provided but it's a modify_file, convert 'changes' to a list of issues
                if not issues and "changes" in action:
                    changes = action.get("changes", {})
                    if isinstance(changes, dict):
                        issues = [{"description": f"Change {k} to {v}"} for k, v in changes.items()]
                    elif isinstance(changes, list):
                        issues = [{"description": str(c)} for c in changes]

                if target_path and target_path in files:
                    try:
                        self.logger.info(f"    Refining {target_path} as part of contingency plan...")
                        refined = self.file_refiner.refine_file(target_path, files[target_path], readme[:2000], issues)
                        if refined:
                            files[target_path] = refined
                            self.file_manager.write_file(project_root / target_path, refined)
                    except Exception as e:
                        self.logger.error(f"Error refining {target_path}: {e}")

        return files, structure, file_paths

    def _opt_enabled(self, opt_name: str) -> bool:
        """Return True only if the current coder model is ≤8B AND the feature flag is on.

        All 6 small-model optimizations are gated through this method so they
        never activate when a large model (>8B) is in use.

        Args:
            opt_name: Key from ``agent_features.json`` ``small_model_optimizations`` dict,
                e.g. ``"opt1_prompt_state_machine"``.

        Returns:
            True if small model detected AND flag is enabled (defaults to True if missing).
        """
        if not self._is_small_model():
            return False
        opts = self.config.get("small_model_optimizations", {})
        return bool(opts.get(opt_name, True))

    def _is_mid_model(self, role: str = "coder") -> bool:
        """Return True if the LLM for *role* has 9–29B parameters (slim tier).

        Uses the same regex as _is_small_model(). Falls back to False on any error.

        Args:
            role: Agent role whose client to inspect (default: "coder").

        Returns:
            True if model parameter count is 9–29B inclusive, False otherwise.
        """
        import re as _re_model

        try:
            client = self.llm_manager.get_client(role)
            model_name = getattr(client, "model", "") or ""
            match = _re_model.search(r"(\d+(?:\.\d+)?)b", model_name.lower())
            if match:
                size = float(match.group(1))
                return 9.0 <= size <= 29.0
        except Exception:
            pass
        return False

    def _opt_mid_enabled(self, opt_name: str) -> bool:
        """Return True only if the current model is 9–29B AND the feature flag is on.

        Mirrors _opt_enabled() but reads from the ``mid_model_optimizations`` config
        key so that slim-tier tweaks never activate for nano (≤8B) or full (≥30B).

        Args:
            opt_name: Key from agent_features.json mid_model_optimizations dict,
                e.g. "mid1_skip_docs_phases".

        Returns:
            True if mid model detected AND flag is enabled (defaults to True if missing).
        """
        if not self._is_mid_model():
            return False
        opts = self.config.get("mid_model_optimizations", {})
        return bool(opts.get(opt_name, True))

    def _truncate_snapshot(self, snapshot: Dict[str, str], max_tokens: int) -> Dict[str, str]:
        """Proportionally trim snapshot values so the total fits within *max_tokens*.

        Uses a rough 4-chars-per-token estimate. When the total exceeds the
        budget, each value is shortened proportionally.

        Args:
            snapshot: Dict of file paths to content strings.
            max_tokens: Soft cap on total output length (in tokens).

        Returns:
            Snapshot with values truncated as needed.
        """
        if not snapshot:
            return snapshot
        chars_budget = max_tokens * 4
        total_chars = sum(len(v) for v in snapshot.values())
        if total_chars <= chars_budget:
            return snapshot
        ratio = chars_budget / total_chars
        return {k: v[: max(50, int(len(v) * ratio))] for k, v in snapshot.items()}

    def build_micro_context_snapshot(
        self,
        target_file: str,
        max_tokens: int = 1000,
    ) -> Dict[str, str]:
        """Return a minimal context snapshot for small-model generation (Opt 2).

        Fetches the ≤2 direct dependencies of *target_file* from the
        DependencyGraph, extracts only their signatures, then enforces a
        hard token cap. Falls back to ``select_related_files()`` when the
        graph returns nothing useful.

        Args:
            target_file: File currently being generated.
            max_tokens: Hard cap on total context size (default 1000 tokens ≈ 4000 chars).

        Returns:
            Dict of {file_path: signature_string} for the ≤2 closest deps.
        """
        try:
            dep_files = self.dependency_graph.get_context_for_file(target_file, max_depth=1)[:2]
        except Exception:
            dep_files = []

        snapshot: Dict[str, str] = {}
        for dep in dep_files:
            content = self.current_generated_files.get(dep, "")
            if content:
                snapshot[dep] = _extract_signatures(content, dep)

        if not snapshot:
            # Fallback: signature-only RAG selection with max 2 files
            snapshot = self.select_related_files(
                target_file,
                self.current_generated_files,
                max_files=2,
                signatures_only=True,
            )

        result = self._truncate_snapshot(snapshot, max_tokens)
        self.logger.info(
            f"[Opt2] Micro-context snapshot for '{target_file}': "
            f"{len(result)} files, ~{sum(len(v) for v in result.values()) // 4} tokens"
        )
        return result

    def ingest_existing_project(self, project_path: Path) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        """Load an existing project into the agent's state.

        Delegates to :class:`ProjectIngestionService` and updates internal
        context state with the loaded data.

        Returns:
            Tuple of (generated_files, initial_structure, file_paths)
        """
        loaded_files, structure, file_paths, readme_content = self._ingestion_service.ingest(project_path)
        if loaded_files:
            self.update_generated_data(loaded_files, structure, file_paths, readme_content)
        return loaded_files, structure, file_paths
