"""
benchmark_router - migrated from benchmark_bp.py.
Handles model benchmarking, result tracking, and streaming.
"""

import asyncio
import json
import queue
from typing import List, Optional, AsyncIterator

import requests
from fastapi import APIRouter, HTTPException, Request, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agents.auto_benchmarker import ModelBenchmarker

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])

_active_run: dict = {}  # session_id -> {"queue": Queue, "benchmarker": ModelBenchmarker}


class StartBenchmarkRequest(BaseModel):
    models: List[str]
    ollama_url: Optional[str] = ""


class ParallelEvalRequest(BaseModel):
    models: List[str]
    prompts: Optional[List[str]] = ["Write a quicksort in Python", "Explain quantum entanglement"]


@router.get("/models")
async def list_models(url: str = Query("")):
    """Fetch available models from an Ollama server."""
    ollama_url = url.strip()

    if not ollama_url:
        import os

        ollama_url = os.environ.get("OLLAMA_URL", os.environ.get("OLLASH_OLLAMA_URL", "http://127.0.0.1:11434"))

    ollama_url = ollama_url.rstrip("/")

    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=10)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        models_sorted = sorted(models, key=lambda m: m.get("size", 0))
        result = []
        for m in models_sorted:
            size_bytes = m.get("size", 0)
            name = m["name"]
            is_embedding = "embed" in name.lower()

            result.append(
                {
                    "name": name,
                    "size_bytes": size_bytes,
                    "size_human": ModelBenchmarker.format_size(size_bytes),
                    "supports_chat": not is_embedding,
                }
            )
        return {"status": "ok", "ollama_url": ollama_url, "models": result}
    except requests.ConnectionError:
        raise HTTPException(status_code=503, detail=f"Cannot connect to Ollama at {ollama_url}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_benchmark(payload: StartBenchmarkRequest, background_tasks: BackgroundTasks, request: Request):
    """Start a benchmark run."""
    global _active_run

    # For simplicity, we use a single active run or could use session_id
    session_id = "default"

    event_queue = queue.Queue()

    def _run():
        try:
            benchmarker = ModelBenchmarker()
            if payload.ollama_url:
                benchmarker.url = payload.ollama_url

            _active_run[session_id] = {"benchmarker": benchmarker, "queue": event_queue}

            # Initialize model sizes
            benchmarker._model_sizes = {}
            try:
                resp = requests.get(f"{benchmarker.url}/api/tags", timeout=10)
                resp.raise_for_status()
                for m in resp.json().get("models", []):
                    benchmarker._model_sizes[m["name"]] = m.get("size", 0)
            except Exception:
                pass

            def benchmark_callback(data):
                event_queue.put(json.dumps(data))

            benchmarker.results = []
            benchmarker.run_benchmark(payload.models, callback=benchmark_callback)

            all_results = benchmarker.results

            # Generate Summary
            summary_text = "No summary generated."
            try:
                from backend.core.config_loader import get_config_loader

                config = get_config_loader().get_full_config()
                summary_model = config.get("LLM_MODELS", {}).get("models", {}).get("summarization", "qwen3-coder:30b")

                event_queue.put(
                    json.dumps({"type": "info", "message": f"Generating final report with {summary_model}..."})
                )

                benchmarker.results = all_results
                summary_text = benchmarker.generate_summary(summary_model)
            except Exception as e:
                summary_text = f"Error generating summary: {str(e)}"

            log_path = benchmarker.save_logs()

            event_queue.put(
                json.dumps(
                    {
                        "type": "benchmark_done",
                        "results_file": str(log_path),
                        "results": all_results,
                        "summary": summary_text,
                    }
                )
            )

        except Exception as e:
            event_queue.put(json.dumps({"type": "error", "message": str(e)}))
        finally:
            event_queue.put(None)

    background_tasks.add_task(_run)
    return {"status": "started"}


@router.get("/stream")
async def stream_benchmark():
    """SSE endpoint for benchmark progress."""
    session_id = "default"
    if session_id not in _active_run:
        raise HTTPException(status_code=404, detail="No benchmark running.")

    event_queue = _active_run[session_id]["queue"]

    async def _gen() -> AsyncIterator[str]:
        loop = asyncio.get_event_loop()
        while True:
            try:
                msg = await loop.run_in_executor(None, event_queue.get, True, 30)
                if msg is None:
                    yield 'data: {"type": "stream_end"}\n\n'
                    break
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/results")
async def list_results(request: Request):
    """List available benchmark result files."""
    ollash_root_dir = request.app.state.ollash_root_dir
    log_dir = ollash_root_dir / "logs"
    results = []
    if log_dir.exists():
        for f in sorted(log_dir.glob("auto_benchmark_results_*.json"), reverse=True):
            results.append(
                {
                    "filename": f.name,
                    "path": str(f),
                    "modified": f.stat().st_mtime,
                }
            )
    return {"status": "ok", "results": results}


@router.get("/results/{filename}")
async def get_result(filename: str, request: Request):
    """Load a specific benchmark result file."""
    if not filename.startswith("auto_benchmark_results_") or not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    ollash_root_dir = request.app.state.ollash_root_dir
    file_path = ollash_root_dir / "logs" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return {"status": "ok", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def benchmark_index():
    return {"status": "ok", "router": "benchmark"}
