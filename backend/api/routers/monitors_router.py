"""
monitors_router - migrated from monitors_bp.py.
Handles proactive monitoring agents for system, network, and security.
"""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.agents.monitor_agents import create_monitor_agents

router = APIRouter(prefix="/api/monitors", tags=["monitors"])

# In-memory cache for monitor agents
_monitor_agents = None


def get_monitor_agents(request: Request):
    """Lazy initialization of monitor agents."""
    global _monitor_agents
    if _monitor_agents is None:
        ollash_root_dir = request.app.state.ollash_root_dir
        event_publisher = request.app.state.event_publisher
        _monitor_agents = create_monitor_agents(ollash_root_dir, event_publisher)
    return _monitor_agents


class LogAnalysisRequest(BaseModel):
    patterns: Optional[List[str]] = None


class UptimeRequest(BaseModel):
    services: Optional[List[str]] = None


class PortIssuesRequest(BaseModel):
    ports: Optional[List[int]] = None


class IntegrityRequest(BaseModel):
    files: Optional[List[str]] = None


@router.get("/available")
async def get_available_monitors():
    """Get list of available monitoring agents."""
    return {
        "monitors": [
            {
                "id": "system",
                "name": "System Monitor",
                "description": "Health checks, cleanup, log analysis",
                "capabilities": ["health_check", "cleanup", "analyze_logs"],
            },
            {
                "id": "network",
                "name": "Network Monitor",
                "description": "Uptime checks, port monitoring",
                "capabilities": ["check_services_uptime", "detect_port_issues"],
            },
            {
                "id": "security",
                "name": "Security Monitor",
                "description": "Integrity scanning, vulnerability checks",
                "capabilities": [
                    "integrity_scan",
                    "security_log_analysis",
                    "vulnerability_scan",
                ],
            },
        ]
    }


@router.post("/system/health-check")
async def run_system_health_check(request: Request):
    """Run system health check."""
    agents = get_monitor_agents(request)
    try:
        result = await agents["system"].perform_health_check()
        return {"status": "completed", "check_type": "system_health", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/system/cleanup")
async def run_system_cleanup(request: Request):
    """Run system cleanup scan."""
    agents = get_monitor_agents(request)
    try:
        result = await agents["system"].cleanup_system()
        return {"status": "completed", "check_type": "system_cleanup", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/system/logs")
async def analyze_system_logs(payload: LogAnalysisRequest, request: Request):
    """Analyze system logs."""
    agents = get_monitor_agents(request)
    try:
        result = await agents["system"].analyze_logs(payload.patterns)
        return {"status": "completed", "check_type": "log_analysis", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/network/uptime")
async def check_network_uptime(payload: UptimeRequest, request: Request):
    """Check network services uptime."""
    agents = get_monitor_agents(request)
    try:
        result = await agents["network"].check_services_uptime(payload.services)
        return {"status": "completed", "check_type": "network_uptime", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/network/ports")
async def detect_port_issues(payload: PortIssuesRequest, request: Request):
    """Detect port issues."""
    agents = get_monitor_agents(request)
    try:
        result = await agents["network"].detect_port_issues(payload.ports)
        return {"status": "completed", "check_type": "port_detection", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/security/integrity")
async def run_integrity_scan(payload: IntegrityRequest, request: Request):
    """Run file integrity scan."""
    agents = get_monitor_agents(request)
    try:
        result = await agents["security"].integrity_scan(payload.files)
        return {"status": "completed", "check_type": "integrity_scan", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/security/logs")
async def analyze_security_logs(request: Request):
    """Analyze security logs."""
    agents = get_monitor_agents(request)
    try:
        result = await agents["security"].security_log_analysis()
        return {
            "status": "completed",
            "check_type": "security_log_analysis",
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/security/vulnerabilities")
async def scan_vulnerabilities(request: Request):
    """Scan for vulnerabilities."""
    agents = get_monitor_agents(request)
    try:
        result = await agents["security"].vulnerability_scan()
        return {
            "status": "completed",
            "check_type": "vulnerability_scan",
            "result": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def monitors_index():
    return {"status": "ok", "router": "monitors"}
