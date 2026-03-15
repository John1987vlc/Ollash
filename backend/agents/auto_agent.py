"""AutoAgent — 8-phase project generation pipeline optimized for 4B models.

Design decisions:
- No CoreAgent inheritance: standalone orchestrator with 5 simple constructor args
- Phases are lazily imported inside run() — avoids loading ~1567 modules at startup
- Error handling: PipelinePhaseError is caught per-phase; pipeline continues best-effort
- Small models (<=8B) skip TestRunPhase automatically
- generate_structure_only() supports the wizard step-1 preview flow
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional, Type

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.utils.core.exceptions import PipelinePhaseError


def _load_phases() -> dict[str, Type[BasePhase]]:
    """Import all 8 phase classes. Called once per run() invocation."""
    from backend.agents.auto_agent_phases.project_scan_phase import ProjectScanPhase
    from backend.agents.auto_agent_phases.blueprint_phase import BlueprintPhase
    from backend.agents.auto_agent_phases.scaffold_phase import ScaffoldPhase
    from backend.agents.auto_agent_phases.code_fill_phase import CodeFillPhase
    from backend.agents.auto_agent_phases.patch_phase import PatchPhase
    from backend.agents.auto_agent_phases.infra_phase import InfraPhase
    from backend.agents.auto_agent_phases.test_run_phase import TestRunPhase
    from backend.agents.auto_agent_phases.finish_phase import FinishPhase

    return {
        "ProjectScanPhase": ProjectScanPhase,
        "BlueprintPhase": BlueprintPhase,
        "ScaffoldPhase": ScaffoldPhase,
        "CodeFillPhase": CodeFillPhase,
        "PatchPhase": PatchPhase,
        "InfraPhase": InfraPhase,
        "TestRunPhase": TestRunPhase,
        "FinishPhase": FinishPhase,
    }


class AutoAgent:
    """8-phase project generation pipeline optimized for 4B parameter models.

    Phase sequence (full tier, >=9B):
      1. ProjectScanPhase  — zero-LLM: detect type/stack, ingest existing files
      2. BlueprintPhase    — 1 LLM call: full JSON blueprint (max 20 files)
      3. ScaffoldPhase     — zero-LLM: create dirs + write stub files
      4. CodeFillPhase     — core: generate each file in priority order
      5. PatchPhase        — static analysis (ruff/tsc) + targeted fixes
      6. InfraPhase        — templates: requirements.txt, Dockerfile, .gitignore
      7. TestRunPhase      — run tests, patch failures (max 3 iterations)
      8. FinishPhase       — write OLLASH.md, log metrics, fire project_complete

    Small model tier (<=8B, e.g. qwen3.5:4b): skips TestRunPhase.
    """

    FULL_PHASE_ORDER: List[str] = [
        "ProjectScanPhase",
        "BlueprintPhase",
        "ScaffoldPhase",
        "CodeFillPhase",
        "PatchPhase",
        "InfraPhase",
        "TestRunPhase",
        "FinishPhase",
    ]

    SMALL_PHASE_ORDER: List[str] = [
        "ProjectScanPhase",
        "BlueprintPhase",
        "ScaffoldPhase",
        "CodeFillPhase",
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
    ) -> Path:
        """Run the full pipeline. Returns project_root Path on completion."""
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
        )

        # Determine tier before importing phases (ctx.is_small() is fast)
        is_small = ctx.is_small()
        phase_order = self.SMALL_PHASE_ORDER if is_small else self.FULL_PHASE_ORDER
        if skip_phases:
            phase_order = [p for p in phase_order if p not in skip_phases]

        tier = "small (<=8B)" if is_small else "full (>8B)"
        self.logger.info(f"[AutoAgent] Starting '{project_name}' | {tier} | {len(phase_order)} phases")

        phase_classes = _load_phases()
        phases: List[BasePhase] = [phase_classes[name]() for name in phase_order]

        start = time.monotonic()
        for phase in phases:
            try:
                phase.execute(ctx)
            except PipelinePhaseError as e:
                self.logger.error(f"[AutoAgent] Phase {e.phase_name} failed: {e}")
                ctx.errors.append(f"Phase {e.phase_name}: {str(e)}")
                # Continue with remaining phases — best-effort delivery

        elapsed = time.monotonic() - start
        self.logger.info(
            f"[AutoAgent] '{project_name}' done in {elapsed:.1f}s | "
            f"{len(ctx.generated_files)} files | {ctx.total_tokens():,} tokens"
        )
        return project_root

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
