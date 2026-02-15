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

from frontend.blueprints import register_blueprints
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

    # Initialize core services that blueprints will depend on
    alert_manager = None
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
        logger.info("✅ Automation Manager and core services started")

    except Exception as e:
        logger.error(f"Failed to initialize core automation/alert system: {e}", exc_info=True)
        # If core systems fail, it might be better to exit, but for now we'll log and continue

    # Register all blueprints and their initializers
    register_blueprints(
        app=app,
        ollash_root_dir=ollash_root_dir,
        event_publisher=event_publisher,
        chat_event_bridge=chat_event_bridge,
        alert_manager=alert_manager  # Pass the initialized manager
    )

    return app

