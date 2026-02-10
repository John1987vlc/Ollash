"""Flask application factory for the Ollash Web UI."""
from pathlib import Path
from flask import Flask

from src.web.blueprints.common_bp import common_bp, init_app as init_common
from src.web.blueprints.auto_agent_bp import auto_agent_bp, init_app as init_auto_agent
from src.web.blueprints.chat_bp import chat_bp, init_app as init_chat


def create_app(ollash_root_dir: Path = None) -> Flask:
    if ollash_root_dir is None:
        ollash_root_dir = Path(__file__).resolve().parent.parent.parent  # repo root

    app = Flask(
        __name__,
        static_folder=str(Path(__file__).parent / "static"),
        template_folder=str(Path(__file__).parent / "templates"),
    )

    # Initialize blueprint-level singletons
    init_common(ollash_root_dir)
    init_auto_agent(ollash_root_dir)
    init_chat(ollash_root_dir)

    # Register blueprints
    app.register_blueprint(common_bp)
    app.register_blueprint(auto_agent_bp)
    app.register_blueprint(chat_bp)

    return app
