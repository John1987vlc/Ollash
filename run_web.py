#!/usr/bin/env python3
"""
Ollash Web UI entry point.

Starts the FastAPI application with uvicorn (ASGI).
The old Flask app is preserved in frontend/app.py for CLI tools that depend on it.
"""

import os
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import uvicorn

from backend.api.app import create_app

# FastAPI app instance (module-level so uvicorn can import it via "run_web:app")
app = create_app()


def main():
    parser = argparse.ArgumentParser(description="Run the Ollash Web UI")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"), help="Host to bind to")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5000")), help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode (reload and debug logging)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", "1")), help="Number of workers")

    args = parser.parse_args()

    host = args.host
    port = args.port
    reload = args.reload or args.debug or (os.environ.get("RELOAD", "0") == "1")
    workers = args.workers
    log_level = "debug" if args.debug else "info"

    print(f"\U0001f680 Starting Ollash Web UI (FastAPI) on http://{host}:{port} {'(DEBUG MODE)' if args.debug else ''}")

    uvicorn.run(
        "run_web:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
