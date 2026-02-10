#!/usr/bin/env python3
"""Ollash Web UI entry point."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.web.app import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000, threaded=True)
