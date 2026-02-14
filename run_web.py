#!/usr/bin/env python3
"""Ollash Web UI entry point."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from frontend.app import create_app

if __name__ == "__main__":
    app = create_app()
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug, threaded=True)
