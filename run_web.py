#!/usr/bin/env python3
"""Ollash Web UI entry point."""

import os
import sys
import signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from frontend.app import create_app

def signal_handler(sig, frame):
    """Graceful shutdown handler for Ctrl+C and other termination signals."""
    print("\n🛑 Ollash Web UI is shutting down...")
    # Add any cleanup logic here if needed
    os._exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    app = create_app()
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    
    print(f"🚀 Starting Ollash Web UI on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)
