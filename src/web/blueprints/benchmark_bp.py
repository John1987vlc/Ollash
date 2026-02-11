"""Blueprint for model benchmarking routes."""
import json
import os
import threading
import queue

import requests
from flask import Blueprint, jsonify, request, Response, stream_with_context
from pathlib import Path

from src.agents.auto_benchmarker import ModelBenchmarker
from src.web.middleware import rate_limit_benchmark, require_api_key

benchmark_bp = Blueprint("benchmark", __name__)

_ollash_root_dir: Path = None
_active_run: dict = None  # {"thread": Thread, "queue": Queue, "benchmarker": ModelBenchmarker}


def init_app(ollash_root_dir: Path):
    global _ollash_root_dir
    _ollash_root_dir = ollash_root_dir


@benchmark_bp.route("/api/benchmark/models")
def list_models():
    """Fetch available models from an Ollama server.

    Query params: ?url=http://... (optional, overrides config)
    """
    ollama_url = request.args.get("url", "").strip()

    if not ollama_url:
        config_path = _ollash_root_dir / "config" / "settings.json"
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            ollama_url = os.environ.get(
                "OLLASH_OLLAMA_URL",
                config.get("ollama_url", "http://localhost:11434"),
            )
        except Exception:
            ollama_url = "http://localhost:11434"

    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=10)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        models_sorted = sorted(models, key=lambda m: m.get("size", 0))
        result = []
        for m in models_sorted:
            size_bytes = m.get("size", 0)
            result.append({
                "name": m["name"],
                "size_bytes": size_bytes,
                "size_human": ModelBenchmarker.format_size(size_bytes),
            })
        return jsonify({"status": "ok", "ollama_url": ollama_url, "models": result})
    except requests.ConnectionError:
        return jsonify({"status": "error", "message": f"Cannot connect to Ollama at {ollama_url}"}), 503
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@benchmark_bp.route("/api/benchmark/start", methods=["POST"])
@require_api_key
@rate_limit_benchmark
def start_benchmark():
    """Start a benchmark run.

    Body JSON: { "models": ["model1", "model2"], "ollama_url": "..." (optional) }
    """
    global _active_run

    if _active_run and _active_run["thread"].is_alive():
        return jsonify({"status": "error", "message": "A benchmark is already running."}), 429

    data = request.get_json(force=True)
    models = data.get("models", [])
    ollama_url = data.get("ollama_url", "").strip()

    if not models:
        return jsonify({"status": "error", "message": "At least one model is required."}), 400

    event_queue = queue.Queue()
    config_path = str(_ollash_root_dir / "config" / "settings.json")

    def _run():
        try:
            benchmarker = ModelBenchmarker(config_path=config_path)
            if ollama_url:
                benchmarker.url = ollama_url
            _active_run["benchmarker"] = benchmarker

            # Override get_local_models since we already have the list
            benchmarker._model_sizes = {}
            try:
                resp = requests.get(f"{benchmarker.url}/api/tags", timeout=10)
                resp.raise_for_status()
                for m in resp.json().get("models", []):
                    benchmarker._model_sizes[m["name"]] = m.get("size", 0)
            except Exception:
                pass

            total_models = len(models)

            for model_idx, model_name in enumerate(models, 1):
                event_queue.put(json.dumps({
                    "type": "model_start",
                    "model": model_name,
                    "index": model_idx,
                    "total": total_models,
                }))

                # Run benchmark for this single model
                benchmarker.results = []
                benchmarker.run_benchmark([model_name])

                if benchmarker.results:
                    result = benchmarker.results[0]
                    event_queue.put(json.dumps({
                        "type": "model_done",
                        "model": model_name,
                        "index": model_idx,
                        "total": total_models,
                        "result": result,
                    }))

            # Save all results
            benchmarker.results = []
            benchmarker.run_benchmark(models)
            log_path = benchmarker.save_logs()

            event_queue.put(json.dumps({
                "type": "benchmark_done",
                "results_file": str(log_path),
                "results": benchmarker.results,
            }))

        except Exception as e:
            event_queue.put(json.dumps({
                "type": "error",
                "message": str(e),
            }))
        finally:
            event_queue.put(None)  # Sentinel

    _active_run = {"thread": None, "queue": event_queue, "benchmarker": None}
    t = threading.Thread(target=_run, daemon=True)
    _active_run["thread"] = t
    t.start()

    return jsonify({"status": "started"})


@benchmark_bp.route("/api/benchmark/stream")
def stream_benchmark():
    """SSE endpoint for benchmark progress."""
    global _active_run

    if not _active_run or not _active_run["queue"]:
        return jsonify({"status": "error", "message": "No benchmark running."}), 404

    event_queue = _active_run["queue"]

    def generate():
        while True:
            try:
                msg = event_queue.get(timeout=30)
                if msg is None:
                    yield "data: {\"type\": \"stream_end\"}\n\n"
                    return
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@benchmark_bp.route("/api/benchmark/results")
def list_results():
    """List available benchmark result files."""
    log_dir = _ollash_root_dir / "logs"
    results = []
    if log_dir.exists():
        for f in sorted(log_dir.glob("auto_benchmark_results_*.json"), reverse=True):
            results.append({
                "filename": f.name,
                "path": str(f),
                "modified": f.stat().st_mtime,
            })
    return jsonify({"status": "ok", "results": results})


@benchmark_bp.route("/api/benchmark/results/<filename>")
def get_result(filename):
    """Load a specific benchmark result file."""
    # Security: only allow expected filenames
    if not filename.startswith("auto_benchmark_results_") or not filename.endswith(".json"):
        return jsonify({"status": "error", "message": "Invalid filename."}), 400

    file_path = _ollash_root_dir / "logs" / filename
    if not file_path.exists():
        return jsonify({"status": "error", "message": "File not found."}), 404

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
