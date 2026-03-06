"""
analysis_router - migrated from analysis_bp.py.
Handles advanced analysis: Cross-Reference, Knowledge Graphs, and Decision Context.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.memory.cross_reference_analyzer import CrossReferenceAnalyzer
from backend.utils.core.memory.decision_context_manager import DecisionContextManager
from backend.utils.core.memory.knowledge_graph_builder import KnowledgeGraphBuilder
from backend.utils.core.tools.all_tool_definitions import ALL_TOOLS_DEFINITIONS

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class CompareRequest(BaseModel):
    doc1_path: str
    doc2_path: str


class FindReferencesRequest(BaseModel):
    term: str
    source_dirs: Optional[List[str]] = ["docs"]
    context_window: Optional[int] = 100


class InconsistenciesRequest(BaseModel):
    doc_paths: List[str]


class GapsRequest(BaseModel):
    theory_doc: str
    config_file: Optional[str] = "backend/config/llm_models.json"


class BuildGraphRequest(BaseModel):
    doc_paths: Optional[List[str]] = None
    rebuild: Optional[bool] = False


class KnowledgePathsRequest(BaseModel):
    start_term: str
    end_term: str


class RecordDecisionRequest(BaseModel):
    decision: str
    reasoning: str
    category: str
    context: Dict[str, Any]
    project: Optional[str] = None
    tags: Optional[List[str]] = None


class SimilarDecisionsRequest(BaseModel):
    problem: str
    category: Optional[str] = None
    project: Optional[str] = None
    max_results: Optional[int] = 5


class SuggestDecisionRequest(BaseModel):
    question: str
    category: Optional[str] = None


class DecisionOutcomeRequest(BaseModel):
    success: bool
    lesson: str
    metrics: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_analysis_managers(request: Request):
    """Return analysis managers from app state or initialize them."""
    if not hasattr(request.app.state, "analysis_managers"):
        # We assume AgentKernel or similar has initialized these, or we do it here
        from backend.core.containers import main_container
        
        logger = main_container.core.logging.logger()
        ollash_root_dir = request.app.state.ollash_root_dir
        config = main_container.core.config_loader().get_full_config()

        request.app.state.analysis_managers = {
            "cross_ref": CrossReferenceAnalyzer(ollash_root_dir, logger, config),
            "knowledge_graph": KnowledgeGraphBuilder(ollash_root_dir, logger, config),
            "decision_context": DecisionContextManager(ollash_root_dir, logger, config),
        }
    return request.app.state.analysis_managers


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/tools/definitions")
async def get_tool_definitions():
    """Returns categorized tool definitions for the UI."""
    try:
        categorized = {}
        total_count = len(ALL_TOOLS_DEFINITIONS)

        for tool in ALL_TOOLS_DEFINITIONS:
            name = tool["function"]["name"]
            category = "general"
            if any(word in name for word in ["ping", "traceroute", "port", "network", "subnet", "nmap", "scapy"]):
                category = "network"
            elif any(word in name for word in ["system", "process", "log", "disk", "resource", "startup", "package"]):
                category = "system"
            elif any(word in name for word in ["file", "read", "write", "patch", "refine", "structure"]):
                category = "code"
            elif any(word in name for word in ["git", "commit", "push", "pull", "repo"]):
                category = "git"
            elif any(word in name for word in ["security", "audit", "vuln", "hardening", "policy"]):
                category = "security"
            elif any(word in name for word in ["plan", "project", "logic", "strategy"]):
                category = "planning"

            if category not in categorized:
                categorized[category] = []

            categorized[category].append({"name": name, "description": tool["function"]["description"]})

        return {"total_tools": total_count, "categories": categorized}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cross-reference/compare")
async def compare_documents(payload: CompareRequest, request: Request):
    try:
        managers = get_analysis_managers(request)
        project_root = request.app.state.ollash_root_dir
        doc1 = project_root / payload.doc1_path
        doc2 = project_root / payload.doc2_path
        result = managers["cross_ref"].compare_documents(doc1, doc2)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cross-reference/find-references")
async def find_cross_references(payload: FindReferencesRequest, request: Request):
    try:
        managers = get_analysis_managers(request)
        project_root = request.app.state.ollash_root_dir
        source_paths = [project_root / d for d in payload.source_dirs]
        references = managers["cross_ref"].find_cross_references(payload.term, source_paths, payload.context_window)
        return {
            "term": payload.term,
            "count": len(references),
            "references": [r.to_dict() if hasattr(r, "to_dict") else r for r in references],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cross-reference/inconsistencies")
async def find_inconsistencies(payload: InconsistenciesRequest, request: Request):
    try:
        managers = get_analysis_managers(request)
        project_root = request.app.state.ollash_root_dir
        doc_paths = [project_root / p for p in payload.doc_paths]
        inconsistencies = managers["cross_ref"].extract_inconsistencies(doc_paths)
        return {
            "count": len(inconsistencies),
            "inconsistencies": [i.to_dict() if hasattr(i, "to_dict") else i for i in inconsistencies],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cross-reference/gaps")
async def find_gaps(payload: GapsRequest, request: Request):
    try:
        managers = get_analysis_managers(request)
        project_root = request.app.state.ollash_root_dir
        theory_doc = project_root / payload.theory_doc
        config_file = project_root / payload.config_file
        gaps = managers["cross_ref"].find_gaps_theory_vs_practice(theory_doc, config_file)
        return gaps
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge-graph/build")
async def build_knowledge_graph(payload: BuildGraphRequest, request: Request):
    try:
        managers = get_analysis_managers(request)
        doc_paths = None
        if payload.doc_paths:
            project_root = request.app.state.ollash_root_dir
            doc_paths = [project_root / p for p in payload.doc_paths]
        stats = managers["knowledge_graph"].build_from_documentation(doc_paths)
        return {"status": "success", "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge-graph/connections/{term}")
async def get_concept_connections(term: str, request: Request, max_depth: int = 2):
    try:
        managers = get_analysis_managers(request)
        connections = managers["knowledge_graph"].get_concept_connections(term, max_depth)
        return connections
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge-graph/paths")
async def find_knowledge_paths(payload: KnowledgePathsRequest, request: Request):
    try:
        managers = get_analysis_managers(request)
        paths = managers["knowledge_graph"].find_knowledge_paths(payload.start_term, payload.end_term)
        return {
            "start_term": payload.start_term,
            "end_term": payload.end_term,
            "path_count": len(paths),
            "paths": paths,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge-graph/index")
async def get_thematic_index(request: Request):
    try:
        managers = get_analysis_managers(request)
        index = managers["knowledge_graph"].generate_thematic_index()
        return index
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge-graph/export/mermaid")
async def export_mermaid_diagram(request: Request):
    try:
        managers = get_analysis_managers(request)
        mermaid_code = managers["knowledge_graph"].export_graph_mermaid()
        return {"format": "mermaid", "diagram": mermaid_code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decisions/record")
async def record_decision(payload: RecordDecisionRequest, request: Request):
    try:
        managers = get_analysis_managers(request)
        decision_id = managers["decision_context"].record_decision(
            decision=payload.decision,
            reasoning=payload.reasoning,
            category=payload.category,
            context=payload.context,
            project=payload.project,
            tags=payload.tags,
        )
        return {"status": "success", "decision_id": decision_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decisions/similar")
async def find_similar_decisions(payload: SimilarDecisionsRequest, request: Request):
    try:
        managers = get_analysis_managers(request)
        similar = managers["decision_context"].find_similar_decisions(
            problem=payload.problem,
            category=payload.category,
            project=payload.project,
            max_results=payload.max_results,
        )
        return {
            "problem": payload.problem,
            "similar_decisions": [d.to_dict() if hasattr(d, "to_dict") else d for d in similar],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/decisions/suggestions")
async def get_suggestions(payload: SuggestDecisionRequest, request: Request):
    try:
        managers = get_analysis_managers(request)
        suggestions = managers["decision_context"].suggest_based_on_history(
            question=payload.question, category=payload.category
        )
        return {"question": payload.question, "suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/decisions/outcome/{decision_id}")
async def update_decision_outcome(decision_id: str, payload: DecisionOutcomeRequest, request: Request):
    try:
        managers = get_analysis_managers(request)
        success = managers["decision_context"].update_outcome(decision_id, payload.model_dump())
        if not success:
            raise HTTPException(status_code=404, detail="Decision not found")
        return {"status": "success", "decision_id": decision_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decisions/project/{project_name}")
async def get_project_context(project_name: str, request: Request):
    try:
        managers = get_analysis_managers(request)
        context = managers["decision_context"].get_project_context(project_name)
        return context
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decisions/statistics")
async def get_decision_statistics(request: Request):
    try:
        managers = get_analysis_managers(request)
        stats = managers["decision_context"].get_statistics()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decisions/all")
async def list_all_decisions(request: Request, project: Optional[str] = None):
    try:
        managers = get_analysis_managers(request)
        decisions = managers["decision_context"].get_all_decisions(project)
        return {
            "count": len(decisions),
            "project": project,
            "decisions": [d.to_dict() if hasattr(d, "to_dict") else d for d in decisions],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def analysis_index():
    return {"status": "ok", "router": "analysis"}
