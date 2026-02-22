"""Blueprint for shared routes (index page, health check)."""

from pathlib import Path

import requests
from flask import Blueprint, jsonify, render_template, current_app
from backend.core.containers import main_container

common_bp = Blueprint("common", __name__)

_ollash_root_dir: Path = None


def init_app(app):
    global _ollash_root_dir
    _ollash_root_dir = app.config.get("ollash_root_dir")


@common_bp.route("/")
def index():
    return render_template("index.html")


@common_bp.route("/chat")
def chat_page():
    return render_template("pages/chat.html")


@common_bp.route("/auto_agent")
def auto_agent_page():
    return render_template("pages/auto_agent.html")


@common_bp.route("/architecture")
def architecture_page():
    return render_template("pages/architecture.html")


@common_bp.route("/docs")
def docs_page():
    return render_template("pages/docs.html")


@common_bp.route("/costs")
def costs_page():
    return render_template("pages/costs.html")


@common_bp.route("/security")
def security_page():
    return render_template("pages/security.html")


@common_bp.route("/swarm")
def swarm_page():
    return render_template("pages/swarm.html")


@common_bp.route("/create")
def create_page():
    return render_template("pages/create_project.html")


@common_bp.route("/projects")
def projects_page():
    return render_template("pages/projects.html")


@common_bp.route("/benchmark")
def benchmark_page():
    return render_template("pages/benchmark.html")


@common_bp.route("/automations")
def automations_page():
    return render_template("pages/automations.html")


@common_bp.route("/brain")
def brain_page():
    return render_template("pages/brain.html")


@common_bp.route("/plugins")
def plugins_page():
    return render_template("pages/plugins.html")


@common_bp.route("/settings")
def settings_page():
    return render_template("pages/settings.html")


@common_bp.route("/prompts")
def prompts_page():
    return render_template("pages/prompts.html")


@common_bp.route("/audit")
def audit_page():
    return render_template("pages/audit.html")


@common_bp.route("/knowledge")
def knowledge_page():
    return render_template("pages/knowledge.html")


@common_bp.route("/tuning")
def tuning_page():
    return render_template("pages/tuning.html")


@common_bp.route("/policies")
def policies_page():
    return render_template("pages/policies.html")


@common_bp.route("/fragments")
def fragments_page():
    return render_template("pages/fragments.html")


@common_bp.route("/api/docs/tree")
def get_docs_tree():
    """Returns the dynamic documentation tree."""
    try:
        doc_manager = main_container.core.documentation_manager()
        tree = doc_manager.get_documentation_tree()
        return jsonify(tree)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@common_bp.route("/api/docs/content/<path:rel_path>")
def get_doc_content(rel_path):
    """Returns the content of a specific documentation file."""
    try:
        doc_manager = main_container.core.documentation_manager()
        content = doc_manager.get_documentation_content(rel_path)
        if content is None:
            return jsonify({"error": "File not found or access denied"}), 404
        return jsonify({"content": content, "path": rel_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@common_bp.route("/api/status")
def status():
    """Health check — verifies Ollama connectivity."""
    try:
        config = current_app.config.get("config", {})
        import os

        ollama_url = os.environ.get(
            "OLLASH_OLLAMA_URL",
            config.get("ollama_url", "http://localhost:11434"),
        )
        resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        return jsonify({"status": "ok", "ollama_url": ollama_url, "models": models})
    except requests.ConnectionError:
        return jsonify({"status": "error", "message": "Cannot connect to Ollama"}), 503
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
