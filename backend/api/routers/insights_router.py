"""
insights_router - migrated from insights_bp.py.
Handles activity reports and system insights.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/reports", tags=["insights"])


@router.get("/weekly")
async def get_weekly_report():
    """Returns a weekly summary report with system activity metrics."""
    return {
        "metrics": [
            {"name": "Lines Of Code Generated", "value": "12450"},
            {"name": "Auto Corrected Errors", "value": "84"},
            {"name": "Time Saved Hours", "value": "15.5"},
            {"name": "Agents Deployed", "value": "12"},
            {"name": "Success Rate", "value": "94.2"},
        ]
    }


@router.get("/")
async def reports_index():
    return {"status": "ok", "router": "reports"}
