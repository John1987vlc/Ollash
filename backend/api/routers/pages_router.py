"""
Pages router — serves all Jinja2 HTML pages.

Replaces Flask's common_views.py and per-blueprint page routes.
Templates use `request.url_for('static', path='...')` instead of
Flask's `url_for('static', filename='...')`.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from backend.api.app import get_templates

router = APIRouter(tags=["pages"])


def _render(request: Request, template: str, ctx: dict | None = None):
    context = {"request": request, **(ctx or {})}
    return get_templates().TemplateResponse(template, context)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _render(request, "index.html")


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return _render(request, "pages/chat.html")


@router.get("/auto-agent", response_class=HTMLResponse)
async def auto_agent_page(request: Request):
    return _render(request, "pages/auto-agent.html")


@router.get("/swarm", response_class=HTMLResponse)
async def swarm_page(request: Request):
    return _render(request, "pages/swarm.html")


@router.get("/analysis", response_class=HTMLResponse)
async def analysis_page(request: Request):
    return _render(request, "pages/analysis.html")


@router.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request):
    return _render(request, "pages/audit.html")


@router.get("/benchmark", response_class=HTMLResponse)
async def benchmark_page(request: Request):
    return _render(request, "pages/benchmark.html")


@router.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request):
    return _render(request, "pages/metrics.html")


@router.get("/knowledge-graph", response_class=HTMLResponse)
async def knowledge_graph_page(request: Request):
    return _render(request, "pages/knowledge-graph.html")


@router.get("/learning", response_class=HTMLResponse)
async def learning_page(request: Request):
    return _render(request, "pages/learning.html")


@router.get("/terminal", response_class=HTMLResponse)
async def terminal_page(request: Request):
    return _render(request, "pages/terminal.html")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return _render(request, "pages/settings.html")
