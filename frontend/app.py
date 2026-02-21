"""Flask application factory for the Ollash Web UI."""

import logging
from pathlib import Path
from flask import Flask

from backend.utils.core.system.event_publisher import EventPublisher
from frontend.core.config_manager import setup_app_config
from frontend.core.service_manager import init_app_services
from frontend.blueprints import register_blueprints
from frontend.middleware import add_cors_headers
from frontend.services.chat_event_bridge import ChatEventBridge

# Global instances for event handling
event_publisher = EventPublisher()
chat_event_bridge = ChatEventBridge(event_publisher)


def create_app(ollash_root_dir: Path = None) -> Flask:
    """Ollash App Factory."""
    if ollash_root_dir is None:
        ollash_root_dir = Path(__file__).resolve().parent.parent

    app = Flask(
        __name__,
        static_folder=str(Path(__file__).parent / "static"),
        template_folder=str(Path(__file__).parent / "templates"),
    )

    # 1. Setup Logging
    app.config["logger"] = logging.getLogger("ollash")

    # 2. Setup Configuration
    setup_app_config(app, ollash_root_dir)

    # 3. Setup CORS
    app.after_request(add_cors_headers)

    # 4. Initialize Core Services (Managers)
    init_app_services(app, ollash_root_dir, event_publisher)

    # 5. Register Blueprints
    register_blueprints(
        app=app,
        ollash_root_dir=ollash_root_dir,
        event_publisher=event_publisher,
        chat_event_bridge=chat_event_bridge,
        alert_manager=app.config.get("alert_manager"),
    )

    return app
