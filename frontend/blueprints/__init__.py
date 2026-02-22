"""Overwritten frontend/blueprints/__init__.py with all needed blueprints."""

from pathlib import Path
from flask import Flask
from backend.utils.core.system.alert_manager import AlertManager
from backend.utils.core.system.automation_manager import AutomationManager
from backend.utils.core.system.event_publisher import EventPublisher
from frontend.services.chat_event_bridge import ChatEventBridge

from .alerts_bp import alerts_bp, init_app as init_alerts
from .analysis_bp import analysis_bp, init_app as init_analysis
from .audit_bp import audit_bp
from .artifacts_bp import artifacts_bp, init_app as init_artifacts
from .auto_agent_bp import auto_agent_bp, init_app as init_auto_agent
from .automations_bp import automations_bp, init_app as init_automations
from .automations_bp_api import automations_api_bp, init_app as init_automations_api
from .benchmark_bp import benchmark_bp, init_app as init_benchmark
from .chat_bp import chat_bp, init_app as init_chat
from .common_bp import common_bp, init_app as init_common
from .learning_bp import init_app as init_learning, learning_bp
from .metrics_bp import init_app as init_metrics, metrics_bp
from .monitors_bp import init_app as init_monitors, monitors_bp
from .multimodal_bp import init_app as init_multimodal, multimodal_bp
from .plugins_bp import init_app as init_plugins, plugins_bp
from .refinement_bp import init_refinement, refinement_bp
from .sandbox_bp import init_app as init_sandbox, sandbox_bp
from .triggers_bp import init_app as init_triggers, triggers_bp
from .webhooks_bp import init_app as init_webhooks, webhooks_bp
from .cicd_bp import cicd_bp, init_app as init_cicd
from .cost_bp import cost_bp, init_app as init_cost
from .export_bp import export_bp, init_app as init_export
from .knowledge_graph_bp import knowledge_graph_bp, init_app as init_knowledge_graph
from .pair_programming_bp import pair_programming_bp, init_app as init_pair_programming
from .project_graph_bp import project_graph_bp, init_app as init_project_graph
from .prompt_studio_bp import prompt_studio_bp
from .knowledge_bp import knowledge_bp
from .decisions_bp import decisions_bp
from .tuning_bp import tuning_bp
from .hil_bp import hil_bp
from .translator_bp import translator_bp
from .policies_bp import policies_bp
from .checkpoints_bp import checkpoints_bp
from .fragments_bp import fragments_bp
from .router_bp import router_bp
from .refactor_bp import refactor_bp, init_app as init_refactor
from .system_health_bp import system_health_bp, init_app as init_system_health
from .cybersecurity_bp import cybersecurity_bp, init_app as init_cybersecurity
from .swarm_bp import swarm_bp, init_app as init_swarm


def register_blueprints(
    app: Flask,
    ollash_root_dir: Path,
    event_publisher: EventPublisher,
    chat_event_bridge: ChatEventBridge,
    alert_manager: AlertManager,
):
    app.config["ollash_root_dir"] = ollash_root_dir
    blueprints = [
        (common_bp, lambda: init_common(app)),
        (auto_agent_bp, lambda: init_auto_agent(app, event_publisher, chat_event_bridge)),
        (chat_bp, lambda: init_chat(app, event_publisher)),
        (benchmark_bp, lambda: init_benchmark(app)),
        (automations_bp, lambda: init_automations(app, event_publisher)),
        (metrics_bp, lambda: init_metrics(app)),
        (monitors_bp, lambda: init_monitors(app, event_publisher)),
        (triggers_bp, lambda: init_triggers()),
        (alerts_bp, lambda: init_alerts(app, event_publisher, alert_manager)),
        (automations_api_bp, lambda: init_automations_api(app, event_publisher)),
        (analysis_bp, lambda: init_analysis(app)),
        (artifacts_bp, lambda: init_artifacts(app)),
        (learning_bp, lambda: init_learning(app)),
        (refinement_bp, lambda: init_refinement(app)),
        (multimodal_bp, lambda: init_multimodal(app, ollash_root_dir)),
        (plugins_bp, lambda: init_plugins(app)),
        (webhooks_bp, lambda: init_webhooks(app)),
        (sandbox_bp, lambda: init_sandbox(app)),
        (cicd_bp, lambda: init_cicd(app)),
        (cost_bp, lambda: init_cost(app)),
        (export_bp, lambda: init_export(app)),
        (knowledge_graph_bp, lambda: init_knowledge_graph(app)),
        (pair_programming_bp, lambda: init_pair_programming(app, event_publisher)),
        (system_health_bp, lambda: init_system_health(app)),
        (cybersecurity_bp, lambda: init_cybersecurity(app)),
        (swarm_bp, lambda: init_swarm(app)),
        (prompt_studio_bp, lambda: None),
        (audit_bp, lambda: None),
        (knowledge_bp, lambda: None),
        (decisions_bp, lambda: None),
        (tuning_bp, lambda: None),
        (hil_bp, lambda: None),
        (translator_bp, lambda: None),
        (policies_bp, lambda: None),
        (checkpoints_bp, lambda: None),
        (fragments_bp, lambda: None),
        (router_bp, lambda: None),
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
            logger.error(f"Failed to register '{bp.name}': {e}", exc_info=True)
