"""Blueprint for shared routes (index page, health check)."""

import json
from pathlib import Path

import requests
from flask import Blueprint, jsonify, render_template, current_app

common_bp = Blueprint("common", __name__)

_ollash_root_dir: Path = None


def init_app(app):
    global _ollash_root_dir
    _ollash_root_dir = app.config.get("ollash_root_dir")


@common_bp.route("/")
def index():
    return render_template("index.html")


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
