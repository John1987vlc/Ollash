"""Metrics router — LLM token usage and agent phase stats."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

# --------------------------------------------------------------------------
# In-memory phase metrics store
# --------------------------------------------------------------------------
_phase_store: list[dict[str, Any]] = []
_phase_lock = Lock()


def record_phase(phase_name: str, duration_s: float, success: bool, tier: str = "") -> None:
    """Called by phases to record execution stats."""
    with _phase_lock:
        _phase_store.append(
            {
                "ts": time.time(),
                "phase": phase_name,
                "duration_s": round(duration_s, 2),
                "success": success,
                "tier": tier,
            }
        )
        if len(_phase_store) > 1000:
            del _phase_store[:200]


@router.get("/")
async def metrics_index():
    return {"status": "ok", "endpoints": ["/llm", "/agent"]}


@router.get("/llm")
async def get_llm_metrics():
    """Aggregated LLM call stats from the in-memory call log."""
    from backend.utils.core.llm.call_log import llm_call_log

    entries = llm_call_log.get_recent(limit=500)
    stats = llm_call_log.stats()

    by_model: dict[str, dict] = defaultdict(
        lambda: {
            "calls": 0,
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "errors": 0,
            "latency_ms_sum": 0.0,
        }
    )
    for e in entries:
        m = e["model"]
        by_model[m]["calls"] += 1
        by_model[m]["total_tokens"] += e["total_tokens"]
        by_model[m]["prompt_tokens"] += e["prompt_tokens"]
        by_model[m]["completion_tokens"] += e["completion_tokens"]
        by_model[m]["latency_ms_sum"] += e["latency_ms"]
        if not e["success"]:
            by_model[m]["errors"] += 1

    models = []
    for model_name, data in by_model.items():
        avg_lat = data["latency_ms_sum"] / data["calls"] if data["calls"] else 0
        models.append(
            {
                "model": model_name,
                "calls": data["calls"],
                "total_tokens": data["total_tokens"],
                "prompt_tokens": data["prompt_tokens"],
                "completion_tokens": data["completion_tokens"],
                "avg_latency_ms": round(avg_lat, 1),
                "error_count": data["errors"],
            }
        )

    return {"summary": stats, "by_model": models, "recent": entries[-20:]}


@router.get("/agent")
async def get_agent_metrics():
    """Phase execution stats."""
    with _phase_lock:
        entries = list(_phase_store)

    if not entries:
        return {"total_phases": 0, "phases": []}

    by_phase: dict[str, dict] = defaultdict(lambda: {"runs": 0, "successes": 0, "total_duration_s": 0.0})
    for e in entries:
        p = e["phase"]
        by_phase[p]["runs"] += 1
        if e["success"]:
            by_phase[p]["successes"] += 1
        by_phase[p]["total_duration_s"] += e["duration_s"]

    phases = []
    for phase_name, data in by_phase.items():
        avg_dur = data["total_duration_s"] / data["runs"] if data["runs"] else 0
        phases.append(
            {
                "phase": phase_name,
                "runs": data["runs"],
                "success_rate": round(data["successes"] / data["runs"], 2),
                "avg_duration_s": round(avg_dur, 2),
            }
        )
    phases.sort(key=lambda x: x["runs"], reverse=True)

    return {"total_phases": len(entries), "unique_phases": len(by_phase), "phases": phases, "recent": entries[-10:]}


@router.delete("/llm")
async def clear_llm_metrics():
    from backend.utils.core.llm.call_log import llm_call_log

    llm_call_log.clear()
    return {"status": "cleared"}
