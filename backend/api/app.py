"""
FastAPI application factory.

Replaces frontend/app.py (Flask factory). Supports:
- Lifespan events for startup/shutdown (replaces @app.before_first_request)
- StaticFiles for /static assets
- Jinja2Templates for server-side rendering (same templates, updated url_for syntax)
- CORS middleware
- dependency-injector wiring via Depends()
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


# ---------------------------------------------------------------------------
# Template instance (global, shared across all routers)
# ---------------------------------------------------------------------------

templates: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    """Return the shared Jinja2Templates instance."""
    if templates is None:
        raise RuntimeError("Templates not initialized — call create_app() first.")
    return templates


# ---------------------------------------------------------------------------
# Lifespan (startup + shutdown)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Application lifespan: initialize services on startup, cleanup on shutdown."""
    # --- Startup ---
    _init_app_state(app)
    _wire_di_container(app)
    automation_manager = getattr(app.state, "automation_manager", None)
    if automation_manager and hasattr(automation_manager, "start") and callable(automation_manager.start):
        import asyncio

        if asyncio.iscoroutinefunction(automation_manager.start):
            await automation_manager.start()
        else:
            automation_manager.start()
    yield
    # --- Shutdown ---
    automation_manager = getattr(app.state, "automation_manager", None)
    if automation_manager and hasattr(automation_manager, "stop"):
        automation_manager.stop()


def _init_app_state(app: FastAPI) -> None:
    """Initialize all services and attach to app.state (replaces app.config).

    Skips initialization for any service already pre-configured on app.state
    so that tests can inject mocks before the lifespan starts.
    """
    if getattr(app.state, "_services_initialized", False):
        return

    from backend.utils.core.system.event_publisher import EventPublisher
    from backend.utils.core.system.automation_manager import get_automation_manager
    from backend.utils.core.system.notification_manager import get_notification_manager
    from backend.utils.core.system.alert_manager import get_alert_manager
    from backend.services.chat_event_bridge import ChatEventBridge

    import os

    ollash_root_dir = Path(os.environ.get("OLLASH_ROOT_DIR", ".ollash"))

    if not getattr(app.state, "event_publisher", None):
        app.state.event_publisher = EventPublisher()
    if not getattr(app.state, "chat_event_bridge", None):
        app.state.chat_event_bridge = ChatEventBridge(app.state.event_publisher)
    if not getattr(app.state, "notification_manager", None):
        app.state.notification_manager = get_notification_manager()
    if not getattr(app.state, "alert_manager", None):
        app.state.alert_manager = get_alert_manager(app.state.notification_manager, app.state.event_publisher)
    if not getattr(app.state, "automation_manager", None):
        app.state.automation_manager = get_automation_manager(ollash_root_dir, app.state.event_publisher)
    if not getattr(app.state, "ollash_root_dir", None):
        app.state.ollash_root_dir = ollash_root_dir

    app.state._services_initialized = True

    # Load local plugins (best-effort — failures are logged, never fatal)
    try:
        from backend.api.routers.plugins_router import load_all_plugins

        loaded = load_all_plugins()
        if loaded:
            import logging as _logging

            _logging.getLogger(__name__).info("Plugins loaded: %s", loaded)
    except Exception as _plug_exc:
        import logging as _logging

        _logging.getLogger(__name__).warning("Plugin load error: %s", _plug_exc)


def _wire_di_container(app: FastAPI) -> None:
    """Wire dependency-injector container to all router modules."""
    from backend.core.containers import main_container
    from backend.api.routers import ALL_ROUTER_MODULES

    main_container.wire(modules=ALL_ROUTER_MODULES)
    app.state.container = main_container


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(ollash_root_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    global templates

    app = FastAPI(
        title="Ollash — Local AI Agent Platform",
        version="1.3.0",
        lifespan=_lifespan,
    )

    # Rate limiter (per-IP; override key_func for per-user in individual routes)
    limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS — restrict to localhost in production; wildcard kept for dev convenience.
    # Override OLLASH_CORS_ORIGINS env var (comma-separated) to lock down further.
    _cors_origins_env = os.environ.get("OLLASH_CORS_ORIGINS", "")
    _cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()] if _cors_origins_env else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files: /static → frontend/static/
    app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

    # Jinja2 templates: same directory, updated url_for calls in templates
    templates = Jinja2Templates(directory="frontend/templates")

    # Register Vite asset URL helper as template global
    from backend.api.vite import asset_url

    templates.env.globals["asset_url"] = asset_url
    templates.env.globals["use_vite"] = os.getenv("USE_VITE_ASSETS", "false").lower() == "true"

    # Register all routers
    _register_routers(app)

    return app


def _register_routers(app: FastAPI) -> None:
    """Import and include all API routers."""
    from backend.api.routers.health_router import router as health_router
    from backend.api.routers.chat_router import router as chat_router
    from backend.api.routers.alerts_router import router as alerts_router
    from backend.api.routers.auto_agent_router import router as auto_agent_router
    from backend.api.routers.analysis_router import router as analysis_router
    from backend.api.routers.benchmark_router import router as benchmark_router
    from backend.api.routers.audit_router import router as audit_router
    from backend.api.routers.checkpoints_router import router as checkpoints_router
    from backend.api.routers.cicd_router import router as cicd_router
    from backend.api.routers.knowledge_graph_router import router as knowledge_graph_router
    from backend.api.routers.learning_router import router as learning_router
    from backend.api.routers.metrics_router import router as metrics_router
    from backend.api.routers.artifacts_router import router as artifacts_router
    from backend.api.routers.swarm_router import router as swarm_router
    from backend.api.routers.terminal_router import router as terminal_router
    from backend.api.routers.export_router import router as export_router
    from backend.api.routers.cost_router import router as cost_router
    from backend.api.routers.plugins_router import router as plugins_router
    from backend.api.routers.refinement_router import router as refinement_router
    from backend.api.routers.phase6_router import router as phase6_router
    from backend.api.routers.multimodal_router import router as multimodal_router
    from backend.api.routers.triggers_router import router as triggers_router
    from backend.api.routers.monitors_router import router as monitors_router
    from backend.api.routers.automations_router import router as automations_router
    from backend.api.routers.hil_router import router as hil_router
    from backend.api.routers.project_graph_router import router as project_graph_router
    from backend.api.routers.analytics_router import router as analytics_router
    from backend.api.routers.common_router import router as common_router
    from backend.api.routers.cybersecurity_router import router as cybersecurity_router
    from backend.api.routers.prompt_studio_router import router as prompt_studio_router
    from backend.api.routers.pair_programming_router import router as pair_programming_router
    from backend.api.routers.knowledge_router import router as knowledge_router
    from backend.api.routers.operations_router import router as operations_router
    from backend.api.routers.webhooks_router import router as webhooks_router
    from backend.api.routers.git_router import router as git_router
    from backend.api.routers.tuning_router import router as tuning_router
    from backend.api.routers.resilience_router import router as resilience_router
    from backend.api.routers.refactor_router import router as refactor_router
    from backend.api.routers.sandbox_router import router as sandbox_router
    from backend.api.routers.fragments_router import router as fragments_router
    from backend.api.routers.decisions_router import router as decisions_router
    from backend.api.routers.policies_router import router as policies_router
    from backend.api.routers.insights_router import router as insights_router
    from backend.api.routers.translator_router import router as translator_router
    from backend.api.routers.pages_router import router as pages_router
    from backend.api.routers.models_router import router as models_router
    from backend.api.routers.auth_router import router as auth_router
    from backend.api.routers.pipeline_router import router as pipeline_router
    from backend.api.routers.privacy_router import router as privacy_router
    from backend.api.routers.mcp_router import router as mcp_router

    routers = [
        auth_router,
        privacy_router,
        pipeline_router,
        mcp_router,
        health_router,
        chat_router,
        alerts_router,
        auto_agent_router,
        analysis_router,
        benchmark_router,
        audit_router,
        checkpoints_router,
        cicd_router,
        knowledge_graph_router,
        learning_router,
        metrics_router,
        artifacts_router,
        swarm_router,
        terminal_router,
        export_router,
        cost_router,
        plugins_router,
        refinement_router,
        phase6_router,
        multimodal_router,
        triggers_router,
        monitors_router,
        automations_router,
        hil_router,
        project_graph_router,
        analytics_router,
        common_router,
        cybersecurity_router,
        prompt_studio_router,
        pair_programming_router,
        knowledge_router,
        operations_router,
        webhooks_router,
        git_router,
        tuning_router,
        resilience_router,
        refactor_router,
        sandbox_router,
        fragments_router,
        decisions_router,
        policies_router,
        insights_router,
        translator_router,
        pages_router,
        models_router,
    ]

    for router in routers:
        app.include_router(router)
