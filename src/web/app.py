"""Flask application factory for the Ollash Web UI."""
import os
from pathlib import Path
from flask import Flask

from src.utils.core.event_publisher import EventPublisher # ADDED
from src.web.services.chat_event_bridge import ChatEventBridge # ADDED

from src.web.blueprints.common_bp import common_bp, init_app as init_common
from src.web.blueprints.auto_agent_bp import auto_agent_bp, init_app as init_auto_agent
from src.web.blueprints.chat_bp import chat_bp, init_app as init_chat
from src.web.blueprints.benchmark_bp import benchmark_bp, init_app as init_benchmark
from src.web.middleware import add_cors_headers

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

    # Initialize blueprint-level singletons, passing the event publisher
    init_common(ollash_root_dir)
    init_auto_agent(ollash_root_dir, event_publisher, chat_event_bridge) # MODIFIED
    init_chat(ollash_root_dir, event_publisher)
    init_benchmark(ollash_root_dir)

    # Register blueprints
    app.register_blueprint(common_bp)
    app.register_blueprint(auto_agent_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(benchmark_bp)

    return app
