"""Flask application factory for the Ollash Web UI."""
import os
import logging
from pathlib import Path
from flask import Flask

from src.utils.core.event_publisher import EventPublisher # ADDED
from src.web.services.chat_event_bridge import ChatEventBridge # ADDED
from src.utils.core.automation_manager import get_automation_manager
from src.utils.core.alert_manager import get_alert_manager
from src.utils.core.notification_manager import get_notification_manager

from src.web.blueprints.common_bp import common_bp, init_app as init_common
from src.web.blueprints.auto_agent_bp import auto_agent_bp, init_app as init_auto_agent
from src.web.blueprints.chat_bp import chat_bp, init_app as init_chat
from src.web.blueprints.benchmark_bp import benchmark_bp, init_app as init_benchmark
from src.web.blueprints.automations_bp import automations_bp, init_app as init_automations
from src.web.blueprints.metrics_bp import metrics_bp, init_app as init_metrics
from src.web.blueprints.monitors_bp import monitors_bp, init_app as init_monitors
from src.web.blueprints.triggers_bp import triggers_bp, init_app as init_triggers
from src.web.blueprints.alerts_bp import alerts_bp, init_app as init_alerts
from src.web.blueprints.automations_bp_api import automations_bp as automations_api_bp, init_app as init_automations_api
from src.web.middleware import add_cors_headers

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

    return app

