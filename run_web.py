#!/usr/bin/env python3
"""
Ollash Web UI entry point.

Starts the FastAPI application with uvicorn (ASGI).
The old Flask app is preserved in frontend/app.py for CLI tools that depend on it.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import uvicorn

from backend.api.app import create_app

# FastAPI app instance (module-level so uvicorn can import it via "run_web:app")
app = create_app()


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    reload = os.environ.get("RELOAD", "0") == "1"
    workers = int(os.environ.get("WORKERS", "1"))

    print(f"\U0001f680 Starting Ollash Web UI (FastAPI) on http://{host}:{port}")
    uvicorn.run(
        "run_web:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level="info",
    )
