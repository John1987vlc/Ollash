"""
cost_router - migrated from cost_bp.py.
Handles model cost analysis, reports, and streaming.
"""

import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from backend.core.containers import main_container

router = APIRouter(prefix="/api/costs", tags=["cost"])


def get_cost_analyzer():
    """Returns the cost analyzer singleton."""
    try:
        from backend.utils.core.analysis.cost_analyzer import CostAnalyzer
        
        # We can't easily use DI here without more context, so we'll instantiate if needed
        # Or better, pull from main_container if wired
        app_logger = main_container.core.logging.logger()
        llm_config = main_container.auto_agent_module.llm_models_config()
        
        return CostAnalyzer(
            logger=app_logger,
            llm_config=llm_config,
        )
    except Exception:
        return None


@router.get("/report")
async def get_cost_report():
    """Get cost report."""
    analyzer = get_cost_analyzer()
    if not analyzer:
        raise HTTPException(status_code=503, detail="Cost analyzer not available")

    try:
        report = analyzer.get_report()
        return {"report": report.to_dict() if hasattr(report, "to_dict") else report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions")
async def get_suggestions():
    """Get model downgrade suggestions."""
    analyzer = get_cost_analyzer()
    if not analyzer:
        return {"suggestions": []}

    try:
        suggestions = analyzer.suggest_downgrades()
        return {"suggestions": [s.to_dict() if hasattr(s, "to_dict") else s for s in suggestions]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-model")
async def get_costs_by_model():
    """Get token usage breakdown by model."""
    analyzer = get_cost_analyzer()
    if not analyzer:
        return {"by_model": {}}

    try:
        report = analyzer.get_report()
        report_dict = report.to_dict() if hasattr(report, "to_dict") else report
        return {"by_model": report_dict.get("by_model", {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-phase")
async def get_costs_by_phase():
    """Get token usage breakdown by phase."""
    analyzer = get_cost_analyzer()
    if not analyzer:
        return {"by_phase": {}}

    try:
        report = analyzer.get_report()
        report_dict = report.to_dict() if hasattr(report, "to_dict") else report
        return {"by_phase": report_dict.get("by_phase", {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_cost_history(limit: int = Query(50)):
    """Get historical token usage data."""
    analyzer = get_cost_analyzer()
    if not analyzer:
        return {"history": []}

    try:
        report = analyzer.get_report()
        report_dict = report.to_dict() if hasattr(report, "to_dict") else report
        history = report_dict.get("history", [])
        return {"history": history[:limit]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def cost_index():
    return {"status": "ok", "router": "cost"}
