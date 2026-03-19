"""AutoAgent — 10-phase project generation pipeline optimized for 4B models.

Design decisions:
- No CoreAgent inheritance: standalone orchestrator with 5 simple constructor args
- Phases are lazily imported inside run() — avoids loading ~1567 modules at startup
- Error handling: PipelinePhaseError is caught per-phase; pipeline continues best-effort
- Small models (<=8B) skip TestRunPhase and SeniorReviewPhase automatically
- generate_structure_only() supports the wizard step-1 preview flow
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.utils.core.exceptions import PipelinePhaseError


def _load_phases() -> dict[str, Type[BasePhase]]:
    """Import all phase classes. Called once per run() invocation."""
    from backend.agents.auto_agent_phases.project_scan_phase import ProjectScanPhase
    from backend.agents.auto_agent_phases.blueprint_phase import BlueprintPhase
    from backend.agents.auto_agent_phases.scaffold_phase import ScaffoldPhase
    from backend.agents.auto_agent_phases.code_fill_phase import CodeFillPhase
    from backend.agents.auto_agent_phases.cross_file_validation_phase import CrossFileValidationPhase
    from backend.agents.auto_agent_phases.patch_phase import PatchPhase
    from backend.agents.auto_agent_phases.senior_review_phase import SeniorReviewPhase
    from backend.agents.auto_agent_phases.infra_phase import InfraPhase
    from backend.agents.auto_agent_phases.test_run_phase import TestRunPhase
    from backend.agents.auto_agent_phases.finish_phase import FinishPhase

    return {
        "ProjectScanPhase": ProjectScanPhase,
        "BlueprintPhase": BlueprintPhase,
        "ScaffoldPhase": ScaffoldPhase,
        "CodeFillPhase": CodeFillPhase,
        "CrossFileValidationPhase": CrossFileValidationPhase,
        "PatchPhase": PatchPhase,
        "SeniorReviewPhase": SeniorReviewPhase,
        "InfraPhase": InfraPhase,
        "TestRunPhase": TestRunPhase,
        "FinishPhase": FinishPhase,
    }


class AutoAgent:
    """10-phase project generation pipeline optimized for 4B parameter models.

    Phase sequence (full tier, >8B):
      1.  ProjectScanPhase          — zero-LLM: detect type/stack, ingest existing files
      2.  BlueprintPhase            — 1 LLM call: full JSON blueprint (max 20 files)
      3.  ScaffoldPhase             — zero-LLM: create dirs + write stub files
      4.  CodeFillPhase             — core: generate each file in priority order
      4b. CrossFileValidationPhase  — zero-LLM: HTML↔JS id contract, CSS class check
      5.  PatchPhase                — static analysis + multi-round improvement (3 rounds)
      6b. SeniorReviewPhase         — comprehensive LLM review + auto-repair loop
      6.  InfraPhase                — templates: requirements.txt, Dockerfile, .gitignore
      7.  TestRunPhase              — run tests, patch failures (max 3 iterations)
      8.  FinishPhase               — write OLLASH.md, log metrics, fire project_complete

    Small model tier (<=8B, e.g. qwen3.5:4b): skips SeniorReviewPhase and TestRunPhase
    at the orchestrator level. CrossFileValidationPhase runs on all tiers (zero-LLM).
    """

    FULL_PHASE_ORDER: List[str] = [
        "ProjectScanPhase",
        "BlueprintPhase",
        "ScaffoldPhase",
        "CodeFillPhase",
        "CrossFileValidationPhase",
        "PatchPhase",
        "SeniorReviewPhase",
        "InfraPhase",
        "TestRunPhase",
        "FinishPhase",
    ]

    # Small models (<=8B) skip the LLM-heavy review and test-run phases.
    # Per-phase ctx.is_small() guards remain as belt-and-suspenders.
    SMALL_PHASE_ORDER: List[str] = [
        "ProjectScanPhase",
        "BlueprintPhase",
        "ScaffoldPhase",
        "CodeFillPhase",
        "CrossFileValidationPhase",
        "PatchPhase",
        "InfraPhase",
        "FinishPhase",
    ]

    def __init__(
        self,
        llm_manager,  # IModelProvider
        file_manager,  # FileManager
        event_publisher,  # EventPublisher
        logger,  # AgentLogger
        generated_projects_dir: Path,
    ) -> None:
        self.llm_manager = llm_manager
        self.file_manager = file_manager
        self.event_publisher = event_publisher
        self.logger = logger
        self.generated_projects_dir = Path(generated_projects_dir)
        self.generated_projects_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def run(
        self,
        description: str,
        project_name: str,
        project_root: Optional[Path] = None,
        skip_phases: Optional[List[str]] = None,
        resume: bool = False,
        on_blueprint_ready: Optional[Callable[[Dict[str, Any]], bool]] = None,
        num_refine_loops: int = 3,
    ) -> Path:
        """Run the full pipeline. Returns project_root Path on completion.

        Args:
            resume: If True, load checkpoint from .ollash/checkpoint.json and
                    skip already-completed phases.
            on_blueprint_ready: Optional callback invoked after BlueprintPhase.
                    Receives the blueprint dict; return False to abort the pipeline.
                    The callback may mutate the dict to adjust the plan.
            num_refine_loops: Max improvement rounds in PatchPhase (1–10).
        """
        if project_root is None:
            project_root = self.generated_projects_dir / project_name

        ctx = PhaseContext(
            project_name=project_name,
            project_description=description,
            project_root=project_root,
            llm_manager=self.llm_manager,
            file_manager=self.file_manager,
            event_publisher=self.event_publisher,
            logger=self.logger,
            on_blueprint_ready=on_blueprint_ready,
            num_refine_loops=max(1, num_refine_loops),
        )

        # Determine tier before importing phases (ctx.is_small() is fast)
        is_small = ctx.is_small()
        phase_order = self.SMALL_PHASE_ORDER if is_small else self.FULL_PHASE_ORDER
        if skip_phases:
            phase_order = [p for p in phase_order if p not in skip_phases]

        tier = "small (<=8B)" if is_small else "full (>8B)"
        self.logger.info(f"[AutoAgent] Starting '{project_name}' | {tier} | {len(phase_order)} phases")

        # #15 — Warn when description complexity exceeds small model capacity
        complexity = ctx.description_complexity()
        if is_small and complexity >= 5:
            self.logger.warning(
                f"[AutoAgent] Complex project (score {complexity}/10) with a <=8B model — "
                "consider using a larger model for better results"
            )
        ctx.metrics["description_complexity"] = complexity

        # Attach run logger to ctx for all phases to use
        from backend.utils.core.run_log.pipeline_run_logger import PipelineRunLogger

        ctx.run_logger = PipelineRunLogger(project_root, project_name, description)
        try:
            model_name = getattr(ctx.llm_manager.get_client("coder"), "model", "unknown")
        except Exception:
            model_name = "unknown"
        ctx.run_logger.log_pipeline_start(
            phase_order=phase_order,
            model_name=model_name,
            tier=tier,
            complexity=complexity,
            num_refine_loops=max(1, num_refine_loops),
        )

        # #1 — Checkpoint/resume: restore state and determine which phases to skip
        completed_phases: List[str] = []
        if resume:
            checkpoint = PhaseContext.load_checkpoint(project_root)
            if checkpoint:
                ctx.apply_checkpoint_dict(checkpoint)
                completed_phases = checkpoint.get("completed_phases", [])
                self.logger.info(f"[AutoAgent] Resumed from checkpoint — skipping phases: {completed_phases}")
            else:
                self.logger.warning("[AutoAgent] --resume requested but no checkpoint found; starting fresh")

        phase_classes = _load_phases()
        phases: List[BasePhase] = [phase_classes[name]() for name in phase_order]

        start = time.monotonic()
        try:
            for phase in phases:
                # Skip already-completed phases when resuming (#1)
                # Only active when resume=True was passed — not for fresh runs.
                if resume and getattr(phase, "phase_id", None) in completed_phases:
                    phase_id_skip = getattr(phase, "phase_id", "?")
                    self.logger.info(f"[AutoAgent] Phase {phase_id_skip} skipped (checkpoint)")
                    if ctx.run_logger:
                        ctx.run_logger.log_phase_skipped(
                            phase_id_skip,
                            getattr(phase, "phase_label", phase_id_skip),
                            "resumed from checkpoint",
                        )
                    continue

                try:
                    phase.execute(ctx)
                except PipelinePhaseError as e:
                    self.logger.error(f"[AutoAgent] Phase {e.phase_name} failed: {e}")
                    ctx.errors.append(f"Phase {e.phase_name}: {str(e)}")
                    # Continue with remaining phases — best-effort delivery
                    continue

                # Save checkpoint after each successful phase (#1)
                phase_id = getattr(phase, "phase_id", None)
                if phase_id:
                    completed_phases.append(phase_id)
                    ctx.save_checkpoint(completed_phases)

                # #9 — Interactive pause: invoke callback after BlueprintPhase
                if phase_id == "2" and on_blueprint_ready is not None:
                    blueprint_dict = self._blueprint_to_dict(ctx)
                    should_continue = on_blueprint_ready(blueprint_dict)
                    if not should_continue:
                        self.logger.info("[AutoAgent] Pipeline aborted by on_blueprint_ready callback")
                        return project_root
        finally:
            elapsed = time.monotonic() - start
            if ctx.run_logger:
                ctx.run_logger.log_pipeline_end(
                    elapsed_seconds=elapsed,
                    files_generated=len(ctx.generated_files),
                    total_tokens=ctx.total_tokens(),
                    errors=ctx.errors,
                )
                ctx.run_logger.close()

        self.logger.info(
            f"[AutoAgent] '{project_name}' done in {elapsed:.1f}s | "
            f"{len(ctx.generated_files)} files | {ctx.total_tokens():,} tokens"
        )
        return project_root

    @staticmethod
    def _blueprint_to_dict(ctx: PhaseContext) -> Dict[str, Any]:
        """Serialize current blueprint for the on_blueprint_ready callback."""
        return {
            "project_name": ctx.project_name,
            "project_type": ctx.project_type,
            "tech_stack": ctx.tech_stack,
            "files": [
                {
                    "path": fp.path,
                    "purpose": fp.purpose,
                    "priority": fp.priority,
                    "exports": fp.exports,
                    "imports": fp.imports,
                    "key_logic": fp.key_logic,
                }
                for fp in ctx.blueprint
            ],
        }

    def generate_structure_only(
        self,
        description: str,
        project_name: str,
    ) -> dict:
        """Run only Phase 1 (scan) + Phase 2 (blueprint).

        Returns the blueprint as a dict. Used by the wizard step-1 preview.
        """
        project_root = self.generated_projects_dir / project_name
        ctx = PhaseContext(
            project_name=project_name,
            project_description=description,
            project_root=project_root,
            llm_manager=self.llm_manager,
            file_manager=self.file_manager,
            event_publisher=self.event_publisher,
            logger=self.logger,
        )

        phase_classes = _load_phases()
        for name in ("ProjectScanPhase", "BlueprintPhase"):
            phase_classes[name]().execute(ctx)

        return {
            "project_name": ctx.project_name,
            "project_type": ctx.project_type,
            "tech_stack": ctx.tech_stack,
            "files": [
                {
                    "path": fp.path,
                    "purpose": fp.purpose,
                    "priority": fp.priority,
                    "exports": fp.exports,
                    "imports": fp.imports,
                }
                for fp in ctx.blueprint
            ],
        }
