"""Centralized blueprint registration for the Flask app."""

from pathlib import Path

from flask import Flask

from backend.utils.core.alert_manager import AlertManager
from backend.utils.core.automation_manager import AutomationManager
from backend.utils.core.event_publisher import EventPublisher
from frontend.services.chat_event_bridge import ChatEventBridge

from .alerts_bp import alerts_bp
from .alerts_bp import init_app as init_alerts
from .analysis_bp import analysis_bp
from .analysis_bp import init_app as init_analysis
from .artifacts_bp import artifacts_bp
from .artifacts_bp import init_app as init_artifacts
from .auto_agent_bp import auto_agent_bp
from .auto_agent_bp import init_app as init_auto_agent
from .automations_bp import automations_bp
from .automations_bp import init_app as init_automations
from .automations_bp_api import automations_api_bp
from .automations_bp_api import init_app as init_automations_api
from .benchmark_bp import benchmark_bp
from .benchmark_bp import init_app as init_benchmark
from .chat_bp import chat_bp
from .chat_bp import init_app as init_chat

# Import all blueprints and their init functions
from .common_bp import common_bp
from .common_bp import init_app as init_common
from .learning_bp import init_app as init_learning
from .learning_bp import learning_bp
from .metrics_bp import init_app as init_metrics
from .metrics_bp import metrics_bp
from .monitors_bp import init_app as init_monitors
from .monitors_bp import monitors_bp
from .multimodal_bp import init_app as init_multimodal
from .multimodal_bp import multimodal_bp
from .refinement_bp import init_refinement, refinement_bp
from .triggers_bp import init_app as init_triggers
from .triggers_bp import triggers_bp

# New blueprints (F7, F8, F11, F12, F15)
from .cicd_bp import cicd_bp
from .cicd_bp import init_app as init_cicd
from .cost_bp import cost_bp
from .cost_bp import init_app as init_cost
from .export_bp import export_bp
from .export_bp import init_app as init_export
from .knowledge_graph_bp import knowledge_graph_bp
from .knowledge_graph_bp import init_app as init_knowledge_graph
from .pair_programming_bp import pair_programming_bp
from .pair_programming_bp import init_app as init_pair_programming
from .project_graph_bp import project_graph_bp
from .project_graph_bp import init_app as init_project_graph
from .refactor_bp import refactor_bp
from .refactor_bp import init_app as init_refactor
from .system_health_bp import system_health_bp
from .system_health_bp import init_app as init_system_health


def register_blueprints(
    app: Flask,
    ollash_root_dir: Path,
    event_publisher: EventPublisher,
    chat_event_bridge: ChatEventBridge,
    alert_manager: AlertManager,
):
    """
    Initializes and registers all blueprints for the application.

    This function centralizes the setup for all modular parts of the UI,
    ensuring that each blueprint has its required services and is properly
    registered with the Flask app instance.
    """
    # List of blueprints and their initializers
    # Each tuple contains: (blueprint_object, init_function, init_args)
    # Use a lambda to defer argument binding until the loop.
    blueprints = [
        (common_bp, lambda: init_common(app)),
        (
            auto_agent_bp,
            lambda: init_auto_agent(app, event_publisher, chat_event_bridge),
        ),
        (chat_bp, lambda: init_chat(app, event_publisher)),
        (benchmark_bp, lambda: init_benchmark(app)),
        (automations_bp, lambda: init_automations(app, event_publisher)),
        (metrics_bp, lambda: init_metrics(app)),
        (monitors_bp, lambda: init_monitors(app, event_publisher)),
        (triggers_bp, lambda: init_triggers()),
        (
            alerts_bp,
            lambda: init_alerts(app, event_publisher, alert_manager),
        ),
        (
            automations_api_bp,
            lambda: init_automations_api(app, event_publisher),
        ),
        (analysis_bp, lambda: init_analysis(app)),
        (artifacts_bp, lambda: init_artifacts(app)),
        (learning_bp, lambda: init_learning(app)),
        (refinement_bp, lambda: init_refinement(app)),
        (multimodal_bp, lambda: init_multimodal(app, ollash_root_dir)),
        # New blueprints (F7, F8, F11, F12, F15)
        (cicd_bp, lambda: init_cicd(app)),
        (cost_bp, lambda: init_cost(app)),
        (export_bp, lambda: init_export(app)),
        (knowledge_graph_bp, lambda: init_knowledge_graph(app)),
        (pair_programming_bp, lambda: init_pair_programming(app, event_publisher)),
        # UX improvement blueprints
        (system_health_bp, lambda: init_system_health(app)),
        (refactor_bp, lambda: init_refactor(app)),
        (project_graph_bp, lambda: init_project_graph(app)),
    ]

    logger = app.config["logger"]

    for bp, init_func in blueprints:
        try:
            init_func()
            app.register_blueprint(bp)
            logger.info(f"✓ Blueprint '{bp.name}' registered successfully.")
        except Exception as e:
            logger.error(
                f"Failed to initialize or register blueprint '{bp.name}': {e}",
                exc_info=True,
            )
            # Depending on severity, you might want to re-raise or handle this
            # For now, we log and continue to allow the app to start if possible
