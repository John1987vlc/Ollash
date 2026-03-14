"""Pipeline Builder router — CRUD for custom pipelines + SSE execution.

Endpoints
---------
GET  /api/pipelines/phases          — metadata for all available phases
GET  /api/pipelines                 — list saved pipelines
POST /api/pipelines                 — create pipeline
GET  /api/pipelines/{id}            — get pipeline detail + recent runs
PUT  /api/pipelines/{id}            — update pipeline
DELETE /api/pipelines/{id}          — delete pipeline (builtin protected)
POST /api/pipelines/{id}/run        — execute pipeline, SSE stream of events
GET  /api/pipelines/{id}/runs       — list past runs
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Generator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.api.deps import get_current_user_dep

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])

_PIPELINE_DB = Path(os.environ.get("OLLASH_ROOT_DIR", ".ollash")) / "pipelines.db"


def _store():
    from backend.utils.core.system.db.pipeline_store import PipelineStore

    store = PipelineStore(_PIPELINE_DB)
    store.seed_builtins()
    return store


# ---------------------------------------------------------------------------
# Phase catalog — static metadata for all 39 phases
# ---------------------------------------------------------------------------

PHASES_CATALOG: list[dict[str, Any]] = [
    # Generation
    {
        "id": "ReadmeGenerationPhase",
        "label": "README Generation",
        "category": "generation",
        "description": "Generates project README and infers project type.",
    },
    {
        "id": "StructureGenerationPhase",
        "label": "Structure Generation",
        "category": "generation",
        "description": "Generates the directory and file structure scaffold.",
    },
    {
        "id": "LogicPlanningPhase",
        "label": "Logic Planning",
        "category": "generation",
        "description": "Creates a detailed implementation plan for every file.",
    },
    {
        "id": "EmptyFileScaffoldingPhase",
        "label": "Empty File Scaffolding",
        "category": "generation",
        "description": "Creates empty placeholder files on disk.",
    },
    {
        "id": "FileContentGenerationPhase",
        "label": "File Content Generation",
        "category": "generation",
        "description": "Generates full file content from plans (supports Chain-of-Draft for small models).",
    },
    {
        "id": "FileRefinementPhase",
        "label": "File Refinement",
        "category": "generation",
        "description": "Refines and polishes generated file content.",
    },
    {
        "id": "JavaScriptOptimizationPhase",
        "label": "JavaScript Optimization",
        "category": "generation",
        "description": "Optimizes and deduplicates JavaScript/TypeScript files.",
    },
    {
        "id": "InfrastructureGenerationPhase",
        "label": "Infrastructure Generation",
        "category": "generation",
        "description": "Generates Docker, CI/CD, and infrastructure files.",
    },
    {
        "id": "DocumentationDeployPhase",
        "label": "Documentation Deploy",
        "category": "generation",
        "description": "Generates deployment documentation and runbooks.",
    },
    {
        "id": "DynamicDocumentationPhase",
        "label": "Dynamic Documentation",
        "category": "generation",
        "description": "Generates dynamic docs (OpenAPI, changelog). Full tier only.",
    },
    {
        "id": "InterfaceScaffoldingPhase",
        "label": "Interface Scaffolding",
        "category": "generation",
        "description": "Generates abstract interfaces and base classes.",
    },
    # Planning
    {
        "id": "ClarificationPhase",
        "label": "Clarification",
        "category": "planning",
        "description": "Asks clarifying questions before generation. Nano tier skips.",
    },
    {
        "id": "PlanValidationPhase",
        "label": "Plan Validation",
        "category": "planning",
        "description": "Validates logic plan for completeness. Slim/Nano tiers skip.",
    },
    {
        "id": "ViabilityEstimatorPhase",
        "label": "Viability Estimator",
        "category": "planning",
        "description": "Estimates project complexity and generation viability.",
    },
    {
        "id": "ProjectAnalysisPhase",
        "label": "Project Analysis",
        "category": "planning",
        "description": "Deep analysis of existing project structure and tech stack.",
    },
    {
        "id": "ApiContractPhase",
        "label": "API Contract",
        "category": "planning",
        "description": "Generates OpenAPI contract from logic plan. Nano tier skips.",
    },
    {
        "id": "ComponentTreePhase",
        "label": "Component Tree",
        "category": "planning",
        "description": "Builds component dependency tree. Nano tier skips.",
    },
    {
        "id": "TestPlanningPhase",
        "label": "Test Planning",
        "category": "planning",
        "description": "Creates test plan mapping files to test suites. Nano tier skips.",
    },
    {
        "id": "DependencyPrecheckPhase",
        "label": "Dependency Pre-check",
        "category": "planning",
        "description": "Validates required dependencies before generation starts.",
    },
    # Review
    {
        "id": "StructurePreReviewPhase",
        "label": "Structure Pre-Review",
        "category": "review",
        "description": "Reviews generated structure before file creation.",
    },
    {
        "id": "VerificationPhase",
        "label": "Verification",
        "category": "review",
        "description": "Runs syntax checks and basic validation on generated files.",
    },
    {
        "id": "ExhaustiveReviewRepairPhase",
        "label": "Exhaustive Review & Repair",
        "category": "review",
        "description": "Deep review + auto-repair of all files. Nano tier skips.",
    },
    {
        "id": "FinalReviewPhase",
        "label": "Final Review",
        "category": "review",
        "description": "Final holistic quality review of the complete project.",
    },
    {
        "id": "SeniorReviewPhase",
        "label": "Senior Review",
        "category": "review",
        "description": "Senior architect review — critique, score, suggest improvements.",
    },
    {
        "id": "ContentCompletenessPhase",
        "label": "Content Completeness",
        "category": "review",
        "description": "Checks every file for stub patterns (pass, TODO, ...).",
    },
    {
        "id": "IterativeImprovementPhase",
        "label": "Iterative Improvement",
        "category": "review",
        "description": "Applies improvement suggestions from review phases.",
    },
    # Validation
    {
        "id": "SecurityScanPhase",
        "label": "Security Scan",
        "category": "validation",
        "description": "Scans for OWASP vulnerabilities, generates security report.",
    },
    {
        "id": "LicenseCompliancePhase",
        "label": "License Compliance",
        "category": "validation",
        "description": "Checks dependency licenses. Slim/Nano tiers skip.",
    },
    {
        "id": "DependencyReconciliationPhase",
        "label": "Dependency Reconciliation",
        "category": "validation",
        "description": "Reconciles requirements.txt / package.json with actual imports.",
    },
    {
        "id": "CodeQuarantinePhase",
        "label": "Code Quarantine",
        "category": "validation",
        "description": "Isolates files with critical security issues.",
    },
    {
        "id": "WebSmokeTestPhase",
        "label": "Web Smoke Test",
        "category": "validation",
        "description": "Runs Playwright smoke tests on generated web apps.",
    },
    {
        "id": "ChaosInjectionPhase",
        "label": "Chaos Injection",
        "category": "validation",
        "description": "Injects failure scenarios to test robustness.",
    },
    # Infrastructure
    {
        "id": "GenerationExecutionPhase",
        "label": "Test Execution",
        "category": "infrastructure",
        "description": "Runs generated test suite, reports pass/fail counts.",
    },
    {
        "id": "CICDHealingPhase",
        "label": "CI/CD Healing",
        "category": "infrastructure",
        "description": "Detects and fixes CI/CD pipeline failures. Slim/Nano skip.",
    },
]

_PHASE_ID_SET = {p["id"] for p in PHASES_CATALOG}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PipelineCreate(BaseModel):
    name: str
    phases: list[str]
    description: str = ""


class PipelineUpdate(BaseModel):
    name: str | None = None
    phases: list[str] | None = None
    description: str | None = None


class RunRequest(BaseModel):
    project_path: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/phases")
def list_phases() -> list[dict]:
    """Return metadata for all available pipeline phases."""
    return PHASES_CATALOG


@router.get("")
def list_pipelines(user: dict = Depends(get_current_user_dep)) -> list[dict]:
    return _store().list_pipelines()


@router.post("", status_code=201)
def create_pipeline(
    body: PipelineCreate,
    user: dict = Depends(get_current_user_dep),
) -> dict:
    unknown = [p for p in body.phases if p not in _PHASE_ID_SET]
    if unknown:
        raise HTTPException(400, detail=f"Unknown phases: {unknown}")
    if not body.name.strip():
        raise HTTPException(400, detail="Pipeline name is required")
    return _store().create_pipeline(body.name, body.phases, body.description)


@router.get("/{pipeline_id}")
def get_pipeline(
    pipeline_id: int,
    user: dict = Depends(get_current_user_dep),
) -> dict:
    pipeline = _store().get_pipeline(pipeline_id)
    if pipeline is None:
        raise HTTPException(404, detail="Pipeline not found")
    store = _store()
    pipeline["recent_runs"] = store.list_runs(pipeline_id, limit=5)
    return pipeline


@router.put("/{pipeline_id}")
def update_pipeline(
    pipeline_id: int,
    body: PipelineUpdate,
    user: dict = Depends(get_current_user_dep),
) -> dict:
    if body.phases is not None:
        unknown = [p for p in body.phases if p not in _PHASE_ID_SET]
        if unknown:
            raise HTTPException(400, detail=f"Unknown phases: {unknown}")
    updated = _store().update_pipeline(pipeline_id, body.name, body.phases, body.description)
    if updated is None:
        raise HTTPException(404, detail="Pipeline not found")
    return updated


@router.delete("/{pipeline_id}", status_code=204)
def delete_pipeline(
    pipeline_id: int,
    user: dict = Depends(get_current_user_dep),
) -> None:
    deleted = _store().delete_pipeline(pipeline_id)
    if not deleted:
        raise HTTPException(404, detail="Pipeline not found or is a built-in pipeline")


@router.get("/{pipeline_id}/runs")
def list_runs(
    pipeline_id: int,
    user: dict = Depends(get_current_user_dep),
) -> list[dict]:
    store = _store()
    if store.get_pipeline(pipeline_id) is None:
        raise HTTPException(404, detail="Pipeline not found")
    return store.list_runs(pipeline_id)


@router.post("/{pipeline_id}/run")
def run_pipeline(
    pipeline_id: int,
    body: RunRequest,
    request: Request,
    user: dict = Depends(get_current_user_dep),
) -> StreamingResponse:
    """Execute a pipeline with SSE streaming progress."""
    store = _store()
    pipeline = store.get_pipeline(pipeline_id)
    if pipeline is None:
        raise HTTPException(404, detail="Pipeline not found")

    run = store.create_run(pipeline_id, body.project_path)
    run_id = run["id"]

    def _sse(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    def _generate() -> Generator[str, None, None]:
        phases = pipeline["phases"]
        total = len(phases)

        yield _sse({"type": "run_started", "run_id": run_id, "total_phases": total, "pipeline": pipeline["name"]})
        store.append_log(run_id, {"type": "run_started", "ts": time.time()})

        for idx, phase_id in enumerate(phases):
            # Check for client disconnect
            if request.is_disconnected():
                break

            phase_meta = next(
                (p for p in PHASES_CATALOG if p["id"] == phase_id),
                {"id": phase_id, "label": phase_id, "category": "unknown"},
            )

            yield _sse(
                {
                    "type": "phase_started",
                    "phase": phase_id,
                    "label": phase_meta["label"],
                    "index": idx,
                    "total": total,
                }
            )

            # Execute the phase
            phase_result = _execute_phase(phase_id, body.project_path, user)

            event: dict[str, Any] = {
                "type": "phase_done" if phase_result["success"] else "phase_error",
                "phase": phase_id,
                "label": phase_meta["label"],
                "index": idx,
                "total": total,
                "duration": phase_result.get("duration", 0),
            }
            if not phase_result["success"]:
                event["error"] = phase_result.get("error", "Unknown error")

            yield _sse(event)
            store.append_log(run_id, {**event, "ts": time.time()})

            if not phase_result["success"]:
                store.finish_run(run_id, "failed")
                yield _sse({"type": "run_finished", "run_id": run_id, "status": "failed"})
                return

        store.finish_run(run_id, "completed")
        yield _sse({"type": "run_finished", "run_id": run_id, "status": "completed"})

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Phase execution helper
# ---------------------------------------------------------------------------


def _execute_phase(phase_id: str, project_path: str, user: dict) -> dict[str, Any]:
    """Run a single phase standalone.  Returns {success, duration, error?}."""
    start = time.time()

    # Map phase_id → module path
    _MODULE_MAP = {
        "SecurityScanPhase": "backend.agents.auto_agent_phases.security_scan_phase",
        "SeniorReviewPhase": "backend.agents.auto_agent_phases.senior_review_phase",
        "LogicPlanningPhase": "backend.agents.auto_agent_phases.logic_planning_phase",
        "FileRefinementPhase": "backend.agents.auto_agent_phases.file_refinement_phase",
        "ExhaustiveReviewRepairPhase": "backend.agents.auto_agent_phases.exhaustive_review_repair_phase",
        "TestPlanningPhase": "backend.agents.auto_agent_phases.test_planning_phase",
        "GenerationExecutionPhase": "backend.agents.auto_agent_phases.generation_execution_phase",
        "VerificationPhase": "backend.agents.auto_agent_phases.verification_phase",
        "ReadmeGenerationPhase": "backend.agents.auto_agent_phases.readme_generation_phase",
        "StructureGenerationPhase": "backend.agents.auto_agent_phases.structure_generation_phase",
        "StructurePreReviewPhase": "backend.agents.auto_agent_phases.structure_pre_review_phase",
        "EmptyFileScaffoldingPhase": "backend.agents.auto_agent_phases.empty_file_scaffolding_phase",
        "FileContentGenerationPhase": "backend.agents.auto_agent_phases.file_content_generation_phase",
        "JavaScriptOptimizationPhase": "backend.agents.auto_agent_phases.javascript_optimization_phase",
        "InfrastructureGenerationPhase": "backend.agents.auto_agent_phases.infrastructure_generation_phase",
        "DocumentationDeployPhase": "backend.agents.auto_agent_phases.documentation_deploy_phase",
        "DynamicDocumentationPhase": "backend.agents.auto_agent_phases.dynamic_documentation_phase",
        "CICDHealingPhase": "backend.agents.auto_agent_phases.cicd_healing_phase",
        "ContentCompletenessPhase": "backend.agents.auto_agent_phases.content_completeness_phase",
        "FinalReviewPhase": "backend.agents.auto_agent_phases.final_review_phase",
        "IterativeImprovementPhase": "backend.agents.auto_agent_phases.iterative_improvement_phase",
        "CodeQuarantinePhase": "backend.agents.auto_agent_phases.code_quarantine_phase",
        "LicenseCompliancePhase": "backend.agents.auto_agent_phases.license_compliance_phase",
        "DependencyReconciliationPhase": "backend.agents.auto_agent_phases.dependency_reconciliation_phase",
        "ClarificationPhase": "backend.agents.auto_agent_phases.clarification_phase",
        "PlanValidationPhase": "backend.agents.auto_agent_phases.plan_validation_phase",
        "ApiContractPhase": "backend.agents.auto_agent_phases.api_contract_phase",
        "ComponentTreePhase": "backend.agents.auto_agent_phases.component_tree_phase",
        "DependencyPrecheckPhase": "backend.agents.auto_agent_phases.dependency_precheck_phase",
        "ViabilityEstimatorPhase": "backend.agents.auto_agent_phases.viability_estimator_phase",
        "ProjectAnalysisPhase": "backend.agents.auto_agent_phases.project_analysis_phase",
        "WebSmokeTestPhase": "backend.agents.auto_agent_phases.web_smoke_test_phase",
        "ChaosInjectionPhase": "backend.agents.auto_agent_phases.chaos_injection_phase",
        "InterfaceScaffoldingPhase": "backend.agents.auto_agent_phases.interface_scaffolding_phase",
    }

    module_path = _MODULE_MAP.get(phase_id)
    if module_path is None:
        return {"success": False, "duration": 0, "error": f"No module mapped for phase: {phase_id}"}

    try:
        import importlib

        from backend.agents.auto_agent_phases.phase_context import PhaseContext
        from backend.core.containers import ApplicationContainer

        # Build a minimal PhaseContext pointing to the project directory
        container = ApplicationContainer()
        container.wire(modules=[])

        root = Path(project_path) if project_path else Path.cwd()
        ctx = PhaseContext.from_container(container, project_root=root)

        mod = importlib.import_module(module_path)
        phase_cls = getattr(mod, phase_id)
        phase = phase_cls(ctx)

        # Run the phase
        if hasattr(phase, "run"):
            phase.run(
                project_description="",
                project_name=root.name,
                project_root=root,
                readme_content="",
                initial_structure={},
                generated_files={},
                file_paths=[],
            )
        else:
            phase.execute(
                project_description="",
                project_name=root.name,
                project_root=root,
                readme_content="",
                initial_structure={},
                generated_files={},
                file_paths=[],
            )

        return {"success": True, "duration": round(time.time() - start, 2)}
    except Exception as exc:
        return {"success": False, "duration": round(time.time() - start, 2), "error": str(exc)}
