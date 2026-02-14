"""Flask application factory for the Ollash Web UI."""
import os
import logging
from pathlib import Path
from flask import Flask

# Import the new centralized config
from backend.core.config import config as central_config

from backend.utils.core.event_publisher import EventPublisher
from frontend.services.chat_event_bridge import ChatEventBridge
from backend.utils.core.automation_manager import get_automation_manager
from backend.utils.core.alert_manager import get_alert_manager
from backend.utils.core.notification_manager import get_notification_manager

from frontend.blueprints.common_bp import common_bp, init_app as init_common
from frontend.blueprints.auto_agent_bp import auto_agent_bp, init_app as init_auto_agent
from frontend.blueprints.chat_bp import chat_bp, init_app as init_chat
from frontend.blueprints.benchmark_bp import benchmark_bp, init_app as init_benchmark
from frontend.blueprints.automations_bp import automations_bp, init_app as init_automations
from frontend.blueprints.metrics_bp import metrics_bp, init_app as init_metrics
from frontend.blueprints.monitors_bp import monitors_bp, init_app as init_monitors
from frontend.blueprints.triggers_bp import triggers_bp, init_app as init_triggers
from frontend.blueprints.alerts_bp import alerts_bp, init_app as init_alerts
from frontend.blueprints.automations_bp_api import automations_api_bp, init_app as init_automations_api
from frontend.blueprints.analysis_bp import analysis_bp, init_app as init_analysis
from frontend.blueprints.artifacts_bp import artifacts_bp, init_app as init_artifacts
from frontend.blueprints.learning_bp import learning_bp, init_app as init_learning
from frontend.blueprints.refinement_bp import refinement_bp, init_refinement
from frontend.blueprints.multimodal_bp import multimodal_bp, init_app as init_multimodal
from frontend.middleware import add_cors_headers

logger = logging.getLogger(__name__)

# Global instances for event handling
event_publisher = EventPublisher()
chat_event_bridge = ChatEventBridge(event_publisher) # ChatEventBridge subscribes to the publisher


def create_app(ollash_root_dir: Path = None) -> Flask:
    if ollash_root_dir is None:
        ollash_root_dir = Path(__file__).resolve().parent.parent.parent  # repo root

    app = Flask(
        __name__,
        static_folder=str(Path(__file__).parent / "static"),
        template_folder=str(Path(__file__).parent / "templates"),
    )

    # --- Centralized Configuration Injection ---
    # Merge all parts of the central config into a single dictionary for the app context
    combined_config = {
        **(central_config.TOOL_SETTINGS or {}),
        **(central_config.LLM_MODELS or {}),
        **(central_config.AGENT_FEATURES or {}),
        **(central_config.ALERTS or {}),
        **(central_config.AUTOMATION_TEMPLATES or {})
    }
    app.config['config'] = combined_config
    app.config['ollash_root_dir'] = ollash_root_dir
    app.config['logger'] = logger
    # --- End Configuration Injection ---

    # Secret key for session management
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32).hex())

    # CORS support
    app.after_request(add_cors_headers)

    # Initialize automation & alert systems FIRST
    try:
        automation_manager = get_automation_manager(ollash_root_dir, event_publisher)
        notification_manager = get_notification_manager()
        alert_manager = get_alert_manager(notification_manager, event_publisher)
        
        # Store in app config for blueprints to access
        app.config['automation_manager'] = automation_manager
        app.config['notification_manager'] = notification_manager
        app.config['alert_manager'] = alert_manager
        app.config['event_publisher'] = event_publisher
        
        # Start the automation manager
        automation_manager.start()
        logger.info("✅ Automation Manager started")
        
    except Exception as e:
        logger.error(f"Failed to initialize automation system: {e}")

    # Initialize blueprint-level singletons, passing the event publisher
    init_common(ollash_root_dir)
    init_auto_agent(ollash_root_dir, event_publisher, chat_event_bridge) # MODIFIED
    init_chat(ollash_root_dir, event_publisher)
    init_benchmark(ollash_root_dir)
    
    # Initialize automations blueprint with error handling
    try:
        init_automations(ollash_root_dir, event_publisher)
        logger.info("✓ Automations system initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize automations: {e}")
        # Continue without automations - non-critical feature

    # Initialize alerts blueprint
    try:
        init_alerts(ollash_root_dir, event_publisher, app.config.get('alert_manager'))
        logger.info("✓ Alerts system initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize alerts: {e}")

    # Initialize automations API blueprint
    try:
        init_automations_api(ollash_root_dir, event_publisher)
        logger.info("✓ Automations API initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize automations API: {e}")

    # Initialize metrics blueprint
    try:
        init_metrics(ollash_root_dir)
        logger.info("✓ Metrics dashboard initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize metrics: {e}")

    # Initialize monitors blueprint
    try:
        init_monitors(ollash_root_dir, event_publisher)
        logger.info("✓ Monitors (proactive agents) initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize monitors: {e}")

    # Initialize triggers blueprint
    try:
        init_triggers()
        logger.info("✓ Conditional triggers initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize triggers: {e}")

    # Initialize analysis blueprint (Cross-Reference, Knowledge Graph, Decision Context)
    try:
        init_analysis(app)
        logger.info("✓ Analysis system (Cross-Reference, Knowledge Graph, Decision Context) initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize analysis system: {e}")

    # Initialize artifacts blueprint (Interactive Reports, Diagrams, Checklists, etc.)
    try:
        init_artifacts(app)
        logger.info("✓ Artifacts system (Interactive panels) initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize artifacts system: {e}")

    # Initialize learning blueprint (Preferences, Pattern Analysis, Behavior Tuning)
    try:
        init_learning(app)
        logger.info("✓ Learning system (Preferences, Patterns, Behavior Tuning) initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize learning system: {e}")

    # Initialize refinement blueprint (Feedback Refinement, Source Validation)
    try:
        init_refinement(app)
        logger.info("✓ Refinement system (Feedback Cycles, Validation) initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize refinement system: {e}")

    # Initialize multimodal blueprint (OCR, Multimedia Ingestion, Speech Transcription)
    try:
        init_multimodal(app, ollash_root_dir)
        logger.info("✓ Multimodal system (OCR, Ingestion, Speech) initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize multimodal system: {e}")

    # Register blueprints
    app.register_blueprint(common_bp)
    app.register_blueprint(auto_agent_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(benchmark_bp)
    app.register_blueprint(automations_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(monitors_bp)
    app.register_blueprint(triggers_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(automations_api_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(artifacts_bp)
    app.register_blueprint(learning_bp)
    app.register_blueprint(refinement_bp)
    app.register_blueprint(multimodal_bp)

    return app

