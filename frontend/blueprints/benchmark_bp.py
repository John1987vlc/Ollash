"""Blueprint for model benchmarking routes.

Includes endpoints for:
- Model listing, benchmark execution, result streaming
- Radar chart visualization data per model
- Optimal pipeline recommendation based on affinity matrix + cost-efficiency
"""

import json
import os
import queue
import threading
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

import requests
from flask import Blueprint, Response, jsonify, request, stream_with_context, current_app

from backend.agents.auto_benchmarker import ModelBenchmarker
from frontend.middleware import rate_limit_benchmark, require_api_key

benchmark_bp = Blueprint("benchmark", __name__)

_ollash_root_dir: Path = None
_active_run: dict = None  # {"thread": Thread, "queue": Queue, "benchmarker": ModelBenchmarker}


def init_app(app):
    global _ollash_root_dir
    _ollash_root_dir = app.config.get("ollash_root_dir")


@benchmark_bp.route("/api/benchmark/models")
def list_models():
    """Fetch available models from an Ollama server.

    Query params: ?url=http://... (optional, overrides config)
    """
    ollama_url = request.args.get("url", "").strip()

    if not ollama_url:
        try:
            config = current_app.config.get("config", {})
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
            name = m["name"]
            # Detect if it's likely an embedding model
            is_embedding = "embed" in name.lower()
            
            result.append(
                {
                    "name": name,
                    "size_bytes": size_bytes,
                    "size_human": ModelBenchmarker.format_size(size_bytes),
                    "supports_chat": not is_embedding
                }
            )
        return jsonify({"status": "ok", "ollama_url": ollama_url, "models": result})
    except requests.ConnectionError:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Cannot connect to Ollama at {ollama_url}",
                }
            ),
            503,
        )
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
        return (
            jsonify({"status": "error", "message": "A benchmark is already running."}),
            429,
        )

    data = request.get_json(force=True)
    models = data.get("models", [])
    ollama_url = data.get("ollama_url", "").strip()

    if not models:
        return (
            jsonify({"status": "error", "message": "At least one model is required."}),
            400,
        )

    event_queue = queue.Queue()
    # F12: Use current_app.config for benchmarker or pass None to use default centralized config
    def _run():
        try:
            from backend.core.config import config as backend_config
            benchmarker = ModelBenchmarker() # It will use central config by default
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
            all_results = []

            for model_idx, model_name in enumerate(models, 1):
                event_queue.put(
                    json.dumps(
                        {
                            "type": "model_start",
                            "model": model_name,
                            "index": model_idx,
                            "total": total_models,
                        }
                    )
                )

                # Run benchmark for this single model
                benchmarker.results = [] # Clear for this specific run
                benchmarker.run_benchmark([model_name])

                if benchmarker.results:
                    result = benchmarker.results[0]
                    all_results.append(result)
                    event_queue.put(
                        json.dumps(
                            {
                                "type": "model_done",
                                "model": model_name,
                                "index": model_idx,
                                "total": total_models,
                                "result": result,
                            }
                        )
                    )

            # F14: Generate Summary after all models are done
            summary_text = "No summary generated."
            try:
                from backend.core.config import get_config
                config = get_config()
                summary_model = config.LLM_MODELS.get("models", {}).get("summarization", config.DEFAULT_MODEL)
                
                event_queue.put(json.dumps({"type": "info", "message": f"Generating final report with {summary_model}..."}))
                
                # Update benchmarker with all results for summary generation
                benchmarker.results = all_results
                summary_text = benchmarker.generate_summary(summary_model)
            except Exception as e:
                summary_text = f"Error generating summary: {str(e)}"

            # Save all results to disk
            log_path = benchmarker.save_logs()

            event_queue.put(
                json.dumps(
                    {
                        "type": "benchmark_done",
                        "results_file": str(log_path),
                        "results": all_results,
                        "summary": summary_text
                    }
                )
            )

        except Exception as e:
            event_queue.put(
                json.dumps(
                    {
                        "type": "error",
                        "message": str(e),
                    }
                )
            )
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
                    yield 'data: {"type": "stream_end"}\n\n'
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
            results.append(
                {
                    "filename": f.name,
                    "path": str(f),
                    "modified": f.stat().st_mtime,
                }
            )
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


def _load_latest_results() -> Optional[List[Dict[str, Any]]]:
    """Load the most recent benchmark results file."""
    if not _ollash_root_dir:
        return None
    log_dir = _ollash_root_dir / "logs"
    if not log_dir.exists():
        return None
    files = sorted(log_dir.glob("auto_benchmark_results_*.json"), reverse=True)
    if not files:
        return None
    try:
        with open(files[0], "r") as f:
            return json.load(f)
    except Exception:
        return None


def _extract_radar_dimensions(model_result: Dict[str, Any]) -> Dict[str, float]:
    """Extract 5 radar chart dimensions from a model's benchmark result.

    Maps rubric_scores and thematic_scores to:
    - Code: quality of code generation (Calidad_Codigo + creativity)
    - Logic: reasoning and coherence (Coherencia_Logica + reasoning_depth)
    - Speed: performance efficiency (speed_score + tokens_per_second)
    - Format: JSON/structure compliance (strict_json_score)
    - Creativity: solution diversity (creativity_score)
    """
    rubric = model_result.get("rubric_scores", {})
    thematic = model_result.get("thematic_scores", {})

    # Code dimension: thematic code quality + rubric creativity
    code_thematic = thematic.get("Calidad_Codigo", 0.0)
    code_rubric = rubric.get("creativity_score", 0.0)
    code = (code_thematic + code_rubric) / 2.0 * 10 if code_rubric else code_thematic * 10

    # Logic dimension: thematic coherence + rubric reasoning depth
    logic_thematic = thematic.get("Coherencia_Logica", 0.0)
    logic_rubric = rubric.get("reasoning_depth_score", 0.0)
    logic = (logic_thematic + logic_rubric) / 2.0 * 10 if logic_rubric else logic_thematic * 10

    # Speed dimension: from rubric speed_score or tokens_per_second
    speed_rubric = rubric.get("speed_score", 0.0)
    tps = model_result.get("tokens_per_second", 0.0)
    # Normalize tokens_per_second to 0-1 range (assume max ~100 t/s)
    tps_normalized = min(tps / 100.0, 1.0) if tps > 0 else 0.0
    speed = (speed_rubric + tps_normalized) / 2.0 * 10 if speed_rubric else tps_normalized * 10

    # Format dimension: strict JSON compliance
    format_score = rubric.get("strict_json_score", 0.0) * 10

    # Creativity dimension
    creativity = rubric.get("creativity_score", 0.0) * 10

    # If no rubric data, derive from thematic + success
    if not rubric:
        gen_score = thematic.get("Generacion_Aplicaciones", 0.0)
        code = code_thematic * 10
        logic = logic_thematic * 10
        speed = tps_normalized * 10
        format_score = gen_score * 10  # Proxy: successful generation implies good format
        creativity = gen_score * 5  # Conservative estimate

    return {
        "Code": round(min(code, 10.0), 2),
        "Logic": round(min(logic, 10.0), 2),
        "Speed": round(min(speed, 10.0), 2),
        "Format": round(min(format_score, 10.0), 2),
        "Creativity": round(min(creativity, 10.0), 2),
    }


@benchmark_bp.route("/api/benchmark/radar/<model_name>")
def radar_chart_data(model_name: str):
    """Return radar chart data for a model across 5 dimensions.

    Dimensions: Code, Logic, Speed, Format, Creativity.
    Aggregated from the most recent benchmark results file.

    Response:
        {
            "status": "ok",
            "model": "qwen3-coder",
            "dimensions": {"Code": 7.5, "Logic": 8.2, "Speed": 6.0, "Format": 9.1, "Creativity": 5.8},
            "max_value": 10
        }
    """
    results = _load_latest_results()
    if results is None:
        return jsonify({"status": "error", "message": "No benchmark results found."}), 404

    # Find the model in results
    model_result = None
    for r in results:
        if r.get("model") == model_name:
            model_result = r
            break

    if model_result is None:
        return (
            jsonify({"status": "error", "message": f"Model '{model_name}' not found in results."}),
            404,
        )

    dimensions = _extract_radar_dimensions(model_result)

    return jsonify(
        {
            "status": "ok",
            "model": model_name,
            "dimensions": dimensions,
            "max_value": 10,
        }
    )


@benchmark_bp.route("/api/benchmark/optimal-pipeline")
def optimal_pipeline():
    """Return recommended model-per-phase mapping based on benchmark data.

    Uses affinity scores and cost-efficiency to determine the best model
    for each pipeline phase.

    Query params:
        ?efficiency_weight=0.3  (optional, weight for cost-efficiency vs quality)

    Response:
        {
            "status": "ok",
            "pipeline": {
                "phase_name": {"model": "model_name", "affinity": 8.5, "efficiency": 12.3},
                ...
            },
            "model_rankings": {"model_name": {"dimensions": {...}, "overall": 7.5}},
            "total_efficiency_score": 8.7
        }
    """
    results = _load_latest_results()
    if results is None:
        return jsonify({"status": "error", "message": "No benchmark results found."}), 404

    efficiency_weight = float(request.args.get("efficiency_weight", 0.3))

    # Build model rankings from radar dimensions
    model_rankings: Dict[str, Dict[str, Any]] = {}
    for r in results:
        model = r.get("model", "unknown")
        dimensions = _extract_radar_dimensions(r)
        overall = mean(dimensions.values()) if dimensions else 0.0
        model_rankings[model] = {
            "dimensions": dimensions,
            "overall": round(overall, 2),
            "size_tier": r.get("size_tier", "unknown"),
            "tokens_per_second": r.get("tokens_per_second", 0.0),
        }

    # Phase-to-dimension mapping for optimal assignment
    phase_requirements: Dict[str, Dict[str, float]] = {
        "ReadmeGenerationPhase": {"Creativity": 0.4, "Format": 0.3, "Speed": 0.3},
        "StructureGenerationPhase": {"Format": 0.5, "Logic": 0.3, "Code": 0.2},
        "LogicPlanningPhase": {"Logic": 0.5, "Code": 0.3, "Creativity": 0.2},
        "FileContentGenerationPhase": {"Code": 0.5, "Creativity": 0.2, "Speed": 0.3},
        "TestGenerationExecutionPhase": {"Code": 0.4, "Logic": 0.4, "Format": 0.2},
        "SeniorReviewPhase": {"Logic": 0.4, "Code": 0.4, "Format": 0.2},
        "SecurityScanPhase": {"Logic": 0.5, "Code": 0.3, "Speed": 0.2},
        "FileRefinementPhase": {"Code": 0.5, "Logic": 0.3, "Creativity": 0.2},
    }

    pipeline: Dict[str, Dict[str, Any]] = {}
    for phase, requirements in phase_requirements.items():
        best_model = None
        best_score = -1.0

        for model, data in model_rankings.items():
            dims = data["dimensions"]
            # Weighted score based on phase requirements
            quality_score = sum(dims.get(dim, 0) * weight for dim, weight in requirements.items())

            # Apply cost-efficiency bonus for smaller/faster models
            tps = data.get("tokens_per_second", 1.0)
            speed_bonus = min(tps / 50.0, 1.0) * efficiency_weight * 2

            final_score = quality_score * (1 - efficiency_weight) + speed_bonus * 10

            if final_score > best_score:
                best_score = final_score
                best_model = model

        if best_model:
            pipeline[phase] = {
                "model": best_model,
                "affinity": round(best_score, 2),
                "efficiency": round(model_rankings[best_model].get("tokens_per_second", 0), 2),
            }

    # Total efficiency score
    total_efficiency = mean(p["affinity"] for p in pipeline.values()) if pipeline else 0.0

    return jsonify(
        {
            "status": "ok",
            "pipeline": pipeline,
            "model_rankings": model_rankings,
            "total_efficiency_score": round(total_efficiency, 2),
            "efficiency_weight_used": efficiency_weight,
        }
    )
