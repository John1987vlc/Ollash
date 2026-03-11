"""
analytics_router - Analytics dashboard endpoints.
Returns data from EpisodicMemory / ErrorKnowledgeBase when available,
falls back to empty structures so the frontend renders cleanly.
"""

import logging
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/")
async def analytics_index():
    return {"status": "ok", "router": "analytics"}


@router.get("/summary")
async def analytics_summary():
    """KPI summary: total projects, tokens, files generated, self-healing events."""
    try:
        from backend.core.containers import main_container  # noqa: PLC0415

        episodic = main_container.core.memory.episodic_memory()
        knowledge = main_container.core.memory.error_knowledge_base()

        total_projects = 0
        total_tokens = 0
        total_files = 0
        total_failed = 0
        agent_type_counts: dict = {}

        if hasattr(episodic, "get_all_episodes"):
            episodes = (
                await episodic.get_all_episodes()
                if hasattr(episodic.get_all_episodes, "__await__")
                else episodic.get_all_episodes()
            )
            total_projects = len({e.get("project_name") for e in episodes if e.get("project_name")})
            total_tokens = sum(e.get("tokens", 0) for e in episodes)
            total_files = sum(e.get("files_generated", 0) for e in episodes)
            for e in episodes:
                atype = e.get("agent_type", "UNKNOWN").upper()
                agent_type_counts[atype] = agent_type_counts.get(atype, 0) + 1

        if hasattr(knowledge, "get_error_count"):
            total_failed = knowledge.get_error_count()

    except Exception as exc:
        logger.debug("analytics/summary: using empty defaults (%s)", exc)
        total_projects = 0
        total_tokens = 0
        total_files = 0
        total_failed = 0
        agent_type_counts = {}

    return {
        "total_projects": total_projects,
        "total_tokens": total_tokens,
        "total_files": total_files,
        "total_failed": total_failed,
        "agent_type_counts": agent_type_counts,
    }


@router.get("/projects")
async def analytics_projects():
    """List of projects with token usage, for the bar chart."""
    try:
        from backend.core.containers import main_container  # noqa: PLC0415

        episodic = main_container.core.memory.episodic_memory()

        if not hasattr(episodic, "get_all_episodes"):
            return []

        raw = episodic.get_all_episodes()
        if hasattr(raw, "__await__"):
            raw = await raw

        # Aggregate by project name
        by_project: dict = {}
        for ep in raw:
            name = ep.get("project_name") or "unnamed"
            if name not in by_project:
                by_project[name] = {"project_name": name, "total_tokens": 0, "timestamp": ep.get("timestamp")}
            by_project[name]["total_tokens"] += ep.get("tokens", 0)

        return sorted(by_project.values(), key=lambda p: p.get("timestamp") or "", reverse=True)
    except Exception as exc:
        logger.debug("analytics/projects: using empty list (%s)", exc)
        return []


@router.get("/projects/{project_name}")
async def analytics_project_nodes(project_name: str):
    """Node breakdown for a specific project."""
    try:
        from backend.core.containers import main_container  # noqa: PLC0415

        episodic = main_container.core.memory.episodic_memory()

        if not hasattr(episodic, "get_episodes_by_project"):
            return []

        raw = episodic.get_episodes_by_project(project_name)
        if hasattr(raw, "__await__"):
            raw = await raw

        return [
            {
                "task_id": ep.get("task_id") or ep.get("phase") or "—",
                "agent_type": ep.get("agent_type") or "UNKNOWN",
                "duration_ms": ep.get("duration_ms"),
                "tokens": ep.get("tokens", 0),
                "retry_count": ep.get("retry_count", 0),
            }
            for ep in (raw or [])
        ]
    except Exception as exc:
        logger.debug("analytics/projects/%s: using empty list (%s)", project_name, exc)
        return []


@router.get("/lessons")
async def analytics_lessons():
    """Lessons learned from EpisodicMemory and ErrorKnowledgeBase."""
    try:
        from backend.core.containers import main_container  # noqa: PLC0415

        knowledge = main_container.core.memory.error_knowledge_base()

        if not hasattr(knowledge, "get_recent_patterns"):
            return []

        patterns = knowledge.get_recent_patterns()
        if hasattr(patterns, "__await__"):
            patterns = await patterns

        return [
            {
                "date": p.get("timestamp") or p.get("date"),
                "agent": p.get("agent_type") or "UNKNOWN",
                "error_pattern": p.get("pattern") or p.get("error_pattern") or "—",
                "fix_applied": p.get("fix") or p.get("fix_applied") or "—",
            }
            for p in (patterns or [])
        ]
    except Exception as exc:
        logger.debug("analytics/lessons: using empty list (%s)", exc)
        return []
