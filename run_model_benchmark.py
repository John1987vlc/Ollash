"""run_model_benchmark.py — benchmark AutoAgentWithTools across multiple models.

Tests every model on tasks ordered easy → hard and produces a side-by-side quality
comparison table so you can see which model handles each difficulty tier best.

Usage:
    python run_model_benchmark.py
    python run_model_benchmark.py --models qwen3.5:4b ministral-3:8b
    python run_model_benchmark.py --tasks hello_world calculator todo_api
    python run_model_benchmark.py --skip-on-fail      # skip harder tasks if model fails easy
    python run_model_benchmark.py --only-easy         # easy tasks only (fast smoke test)

Output files (in current directory):
    model_benchmark_<timestamp>.json   — full metric data
    model_benchmark_<timestamp>.txt    — human-readable comparison table
    model_benchmark_logs/<model>/<task>_<ts>.log — per-run logs
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ---------------------------------------------------------------------------
# Models (ordered small → large as requested)
# ---------------------------------------------------------------------------

DEFAULT_MODELS: List[str] = [
    "ministral-3:3b",
    "ministral-3:8b",
    "qwen3-coder:latest",
    "gpt-oss:20b",
]

# ---------------------------------------------------------------------------
# Tasks (ordered easy → hard)
# ---------------------------------------------------------------------------

ALL_TASKS: List[Dict[str, str]] = [
    # ── EASY ──────────────────────────────────────────────────────────────
    {
        "id": "hello_world",
        "difficulty": "easy",
        "name": "hello_world",
        "description": (
            "Create a single Python script (main.py) that prints 'Hello, World!' "
            "to the console and also writes it to a file named output.txt. "
            "No external dependencies allowed."
        ),
    },
    {
        "id": "calculator",
        "difficulty": "easy",
        "name": "calculator",
        "description": (
            "Python CLI calculator (stdlib only, no external libs). "
            "Reads two numbers and an operator (+, -, *, /) from sys.argv "
            "and prints the result. Handle division by zero with a clear error message."
        ),
    },
    # ── MEDIUM ────────────────────────────────────────────────────────────
    {
        "id": "cli_tool",
        "difficulty": "medium",
        "name": "cli_tool",
        "description": (
            "Python CLI tool using Click that converts CSV files to JSON and JSON files "
            "back to CSV. Support --input and --output flags. "
            "Handle missing files and encoding errors gracefully."
        ),
    },
    {
        "id": "data_pipeline",
        "difficulty": "medium",
        "name": "data_pipeline",
        "description": (
            "Python data pipeline (stdlib only) that reads a CSV file, computes "
            "descriptive statistics (mean, median, std dev, min, max) per numeric column, "
            "and writes a formatted summary report to a text file."
        ),
    },
    # ── HARD ──────────────────────────────────────────────────────────────
    {
        "id": "todo_api",
        "difficulty": "hard",
        "name": "todo_api",
        "description": (
            "REST API for a todo list with full CRUD (create, read, update, delete). "
            "Use FastAPI, SQLite via sqlite3, and Pydantic models. "
            "Async endpoints, proper HTTP status codes, and basic error handling."
        ),
    },
    {
        "id": "auth_service",
        "difficulty": "hard",
        "name": "auth_service",
        "description": (
            "Python JWT authentication microservice. "
            "Endpoints: POST /register, POST /login, POST /refresh. "
            "FastAPI framework, passlib for password hashing, python-jose for JWT. "
            "Store users in a SQLite database with proper schema."
        ),
    },
]

TASK_BY_ID = {t["id"]: t for t in ALL_TASKS}
DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}

# Maximum wall-clock seconds per task, by difficulty.
# If exceeded the run is cancelled, partial output is still analysed.
TASK_TIMEOUTS: Dict[str, int] = {
    "easy": 5 * 60,  #  300s — 1-2 file scripts
    "medium": 12 * 60,  #  720s — multi-file projects
    "hard": 25 * 60,  # 1500s — APIs, auth services, DBs
}

# ---------------------------------------------------------------------------
# Quality analysis
# ---------------------------------------------------------------------------

_STUB_PATTERNS = [
    re.compile(r"\bpass\b"),
    re.compile(r"\bTODO\b"),
    re.compile(r"\bNotImplementedError\b"),
    re.compile(r"\.\.\.$", re.MULTILINE),
    re.compile(r"raise NotImplementedError"),
]


def _count_stubs(source: str) -> int:
    return sum(len(p.findall(source)) for p in _STUB_PATTERNS)


def analyze_project_quality(project_dir: Path) -> Dict[str, Any]:
    """Scan a generated project directory and return quality metrics."""
    skip_dirs = {"__pycache__", "node_modules", ".venv", "venv"}

    all_files = [
        f
        for f in project_dir.rglob("*")
        if f.is_file() and not any(part in skip_dirs for part in f.parts) and not f.name.startswith(".")
    ]
    py_files = [f for f in all_files if f.suffix == ".py"]

    if not py_files and not all_files:
        return {
            "files_total": 0,
            "py_files": 0,
            "syntax_valid_pct": 0.0,
            "stub_files_pct": 100.0,
            "avg_lines_per_file": 0.0,
            "quality_score": 0.0,
            "syntax_errors": [],
        }

    total = len(py_files) or 1
    syntax_ok = 0
    stub_files = 0
    total_lines = 0
    syntax_errors: List[Dict[str, str]] = []

    for f in py_files:
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        total_lines += source.count("\n") + 1
        try:
            ast.parse(source)
            syntax_ok += 1
        except SyntaxError as e:
            syntax_errors.append({"file": str(f.relative_to(project_dir)), "error": str(e)})
        if _count_stubs(source) > 0:
            stub_files += 1

    syntax_valid_pct = syntax_ok / total * 100
    stub_files_pct = stub_files / total * 100
    quality_score = (syntax_valid_pct / 100) * 0.6 + ((100 - stub_files_pct) / 100) * 0.4

    return {
        "files_total": len(all_files),
        "py_files": total,
        "syntax_valid_pct": round(syntax_valid_pct, 1),
        "stub_files_pct": round(stub_files_pct, 1),
        "avg_lines_per_file": round(total_lines / total, 1),
        "quality_score": round(quality_score, 3),
        "syntax_errors": syntax_errors[:5],
    }


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def _setup_file_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"bench_{log_path.stem}_{id(log_path)}")
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(message)s"))
    logger.addHandler(handler)
    return logger


class _NullEventPublisher:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self.event_publisher = None  # OllamaClient checks this attribute

    async def publish(self, event_type: str, data: Any) -> None:
        self._logger.debug(f"[SSE] {event_type}: {json.dumps(data, default=str)[:120]}")

    def publish_sync(self, event_type: str, data: Any) -> None:
        self._logger.debug(f"[SSE] {event_type}: {json.dumps(data, default=str)[:120]}")

    def push_event(self, event_type: str, data: Any) -> None:
        self._logger.debug(f"[SSE] {event_type}: {json.dumps(data, default=str)[:120]}")


class _BenchLogger:
    """Minimal agent logger writing to file + stdout. Compatible with OllamaClient."""

    def __init__(self, file_logger: logging.Logger, label: str) -> None:
        self._file = file_logger
        self._label = label
        self.event_publisher = None  # OllamaClient accesses logger.event_publisher

    def _print(self, msg: str) -> None:
        print(f"    [{self._label}] {msg}")

    def debug(self, msg: str, **_: Any) -> None:
        self._file.debug(msg)

    def info(self, msg: str, exc_info: bool = False, **_: Any) -> None:
        self._file.info(msg)
        self._print(msg)

    def info_sync(self, msg: str, **_: Any) -> None:
        self._file.info(msg)

    def warning(self, msg: str, **_: Any) -> None:
        self._file.warning(msg)
        self._print(f"WARN {msg}")

    def warning_sync(self, msg: str, **_: Any) -> None:
        self._file.warning(msg)

    def error(self, msg: str, exc_info: bool = False, **_: Any) -> None:
        self._file.error(msg, exc_info=exc_info)
        self._print(f"ERROR {msg}")


# ---------------------------------------------------------------------------
# LLM manager / model override
# ---------------------------------------------------------------------------


def _build_base_infra() -> tuple[Any, Any, Any, Any]:
    """Return (llm_config, tool_settings_dict, ollama_url, default_timeout) from DI container."""
    from backend.core.containers import main_container

    main_container.init_resources()
    manager = main_container.auto_agent_module.llm_client_manager()
    return (
        manager.config,
        manager.tool_settings.model_dump() if hasattr(manager.tool_settings, "model_dump") else {},
        str(manager.config.ollama_url),
        manager.config.default_timeout,
    )


class _ModelFixedLLMManager:
    """Minimal LLM manager that always returns a single OllamaClient (one specific model)."""

    def __init__(
        self,
        model_name: str,
        ollama_url: str,
        timeout: int,
        bench_logger: _BenchLogger,
        tool_settings_dict: dict,
        recorder: Any = None,
    ) -> None:
        from backend.utils.core.llm.ollama_client import OllamaClient

        self._client = OllamaClient(
            url=ollama_url,
            model=model_name,
            timeout=timeout,
            logger=bench_logger,
            config=tool_settings_dict,
            llm_recorder=recorder,
        )
        self.clients_by_model = {model_name: self._client}

    def get_client(self, role: str) -> Any:
        return self._client

    def get_client_by_model(self, model_name: str, role: str = "custom") -> Any:
        return self._client


def _unload_manager_models(llm_manager: Any, label: str = "") -> None:
    """Unload every cached model from Ollama RAM."""
    clients = getattr(llm_manager, "clients_by_model", {})
    if not clients:
        return
    tag = f"[{label}] " if label else ""
    for model_name, client in list(clients.items()):
        try:
            client.unload_model()
            print(f"    {tag}[unload] ✓ {model_name} freed from RAM")
        except Exception as e:
            print(f"    {tag}[unload] ✗ {model_name}: {e}")


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


async def run_tools_agent_for_model(
    task: Dict[str, str],
    model_name: str,
    project_root: Path,
    llm_manager: Any,
    log_path: Path,
    bench_logger: _BenchLogger,
    max_duration_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Run AutoAgentWithTools with a specific model. Returns metric dict."""
    from backend.agents.auto_agent_with_tools import AutoAgentWithTools

    event_publisher = _NullEventPublisher(bench_logger._file)

    agent = AutoAgentWithTools(
        llm_manager=llm_manager,
        file_manager=None,
        event_publisher=event_publisher,
        logger=bench_logger,
        generated_projects_dir=project_root.parent,
    )

    start = time.time()
    completed = False
    error_msg = ""

    try:
        await agent.run(
            description=task["description"],
            project_name=project_root.name,
            project_root=project_root,
            max_duration_seconds=max_duration_seconds,
        )
        completed = True
    except Exception as e:
        error_msg = str(e)
        bench_logger.error(f"AutoAgentWithTools({model_name}) failed: {e}")

    duration = time.time() - start
    quality = analyze_project_quality(project_root) if project_root.is_dir() else {}

    return {
        "model": model_name,
        "task_id": task["id"],
        "difficulty": task["difficulty"],
        "duration_seconds": round(duration, 1),
        "total_tokens": agent._total_tokens,
        "iterations": agent._iteration_count,
        "files_generated": quality.get("files_total", 0),
        "py_files": quality.get("py_files", 0),
        "quality_score": quality.get("quality_score", 0.0),
        "syntax_valid_pct": quality.get("syntax_valid_pct", 0.0),
        "stub_files_pct": quality.get("stub_files_pct", 100.0),
        "avg_lines_per_file": quality.get("avg_lines_per_file", 0.0),
        "syntax_errors": quality.get("syntax_errors", []),
        "completed": completed,
        "error": error_msg,
        "log_file": str(log_path),
    }


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def _slug(model_name: str) -> str:
    """'qwen3.5:0.8b' → 'qwen3.5_0.8b'"""
    return model_name.replace(":", "_").replace("/", "_")


def _fmt(val: Any, metric: str) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, bool):
        return "Y" if val else "N"
    if metric == "quality_score":
        return f"{val:.3f}"
    if metric in ("syntax_valid_pct", "stub_files_pct"):
        return f"{val:.0f}%"
    if metric == "duration_seconds":
        return f"{val:.0f}s"
    if isinstance(val, float):
        return f"{val:.1f}"
    return str(val)


def _safe_avg(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


ROW_METRICS = [
    ("quality_score", "quality"),
    ("syntax_valid_pct", "syntax%"),
    ("stub_files_pct", "stubs%"),
    ("files_generated", "files"),
    ("avg_lines_per_file", "lines/f"),
    ("duration_seconds", "time"),
    ("iterations", "iters"),
    ("completed", "done?"),
    ("timed_out", "timeout?"),
]


def build_text_report(
    results: Dict[str, Dict[str, Any]],
    models: List[str],
    tasks: List[Dict[str, str]],
    timestamp: str,
) -> str:
    col_w = 11  # width per task column
    label_w = 20

    lines = [
        "=" * 90,
        "  MODEL BENCHMARK — AutoAgentWithTools",
        f"  Date: {timestamp}",
        f"  Models ({len(models)}): {', '.join(models)}",
        f"  Tasks  ({len(tasks)}): {', '.join(t['id'] + ' [' + t['difficulty'][0] + ']' for t in tasks)}",
        "=" * 90,
    ]

    # ── Per-model breakdown ──────────────────────────────────────────────
    for model in models:
        lines.append(f"\n  MODEL: {model}")
        # Header row
        header = f"  {'Metric':<{label_w}}"
        for t in tasks:
            diff_tag = t["difficulty"][0].upper()
            col_label = f"{t['id'][:8]}[{diff_tag}]"
            header += f"  {col_label:>{col_w}}"
        lines.append(header)
        lines.append("  " + "─" * (label_w + (col_w + 2) * len(tasks)))

        for metric_key, metric_label in ROW_METRICS:
            row = f"  {metric_label:<{label_w}}"
            for t in tasks:
                key = f"{model}|{t['id']}"
                r = results.get(key)
                val = r.get(metric_key) if r else None
                row += f"  {_fmt(val, metric_key):>{col_w}}"
            lines.append(row)

    # ── Summary table ────────────────────────────────────────────────────
    lines += ["", "=" * 90, "  SUMMARY — avg quality_score by difficulty", "=" * 90]

    diff_labels = sorted(set(t["difficulty"] for t in tasks), key=lambda d: DIFFICULTY_ORDER[d])
    summary_header = f"  {'Model':<28}"
    for d in diff_labels:
        summary_header += f"  {d:>10}"
    summary_header += f"  {'overall':>10}  {'done':>6}"
    lines.append(summary_header)
    lines.append("  " + "─" * (28 + (12) * len(diff_labels) + 20))

    for model in models:
        row = f"  {model:<28}"
        total_scores = []
        total_done = 0
        total_tasks = 0
        for diff in diff_labels:
            scores = []
            for t in tasks:
                if t["difficulty"] != diff:
                    continue
                key = f"{model}|{t['id']}"
                r = results.get(key)
                if r:
                    total_tasks += 1
                    if r.get("completed"):
                        total_done += 1
                        scores.append(r["quality_score"])
                        total_scores.append(r["quality_score"])
            avg = _safe_avg(scores)
            row += f"  {avg:.3f}     "
        overall = _safe_avg(total_scores)
        row += f"  {overall:.3f}      {total_done}/{total_tasks}"
        lines.append(row)

    lines.append("=" * 90)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-model AutoAgentWithTools benchmark")
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        metavar="MODEL",
        help="Ollama model tags to benchmark (default: all 7)",
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        choices=list(TASK_BY_ID.keys()),
        default=None,
        help="Task IDs to run (default: all, easy→hard)",
    )
    parser.add_argument(
        "--only-easy",
        action="store_true",
        help="Run only easy tasks (hello_world, calculator)",
    )
    parser.add_argument(
        "--skip-on-fail",
        action="store_true",
        help="Skip harder tasks for a model if it fails on easy tasks",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output JSON/TXT files (default: .)",
    )
    parser.add_argument(
        "--projects-dir",
        default="model_benchmark_projects",
        help="Root dir for generated projects (default: model_benchmark_projects/)",
    )
    args = parser.parse_args()

    # Resolve task list
    if args.only_easy:
        tasks = [t for t in ALL_TASKS if t["difficulty"] == "easy"]
    elif args.tasks:
        tasks = sorted(
            [TASK_BY_ID[tid] for tid in args.tasks],
            key=lambda t: DIFFICULTY_ORDER[t["difficulty"]],
        )
    else:
        tasks = list(ALL_TASKS)  # already ordered easy→hard

    models = args.models
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    projects_dir = Path(args.projects_dir).resolve()
    projects_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = output_dir / "model_benchmark_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print("  Ollash — Multi-Model AutoAgentWithTools Benchmark")
    print(f"  Models ({len(models)}): {', '.join(models)}")
    print(f"  Tasks  ({len(tasks)}): {', '.join(t['id'] + '[' + t['difficulty'][0] + ']' for t in tasks)}")
    print(f"  skip-on-fail: {args.skip_on_fail}")
    print("=" * 70 + "\n")

    # Load base infrastructure (Ollama URL, timeout, tool_settings) once
    print("Initializing base infrastructure from DI container...")
    try:
        llm_config, tool_settings_dict, ollama_url, default_timeout = _build_base_infra()
        print(f"  Ollama URL: {ollama_url}")
    except Exception as e:
        print(f"ERROR: Could not initialize DI container: {e}")
        sys.exit(1)

    results: Dict[str, Any] = {}

    for model_idx, model_name in enumerate(models, 1):
        slug = _slug(model_name)
        print(f"\n{'═' * 70}")
        print(f"  [{model_idx}/{len(models)}] MODEL: {model_name}")
        print(f"{'═' * 70}")

        # Create a per-model log file and logger
        model_log = logs_dir / f"{slug}_{timestamp}.log"
        file_logger = _setup_file_logger(model_log)
        bench_logger = _BenchLogger(file_logger, slug)

        # Build a dedicated LLM manager wired to this specific model
        llm_manager = _ModelFixedLLMManager(
            model_name=model_name,
            ollama_url=ollama_url,
            timeout=default_timeout,
            bench_logger=bench_logger,
            tool_settings_dict=tool_settings_dict,
        )

        easy_failed = False  # tracks if easy tasks failed (for --skip-on-fail)

        for task_idx, task in enumerate(tasks, 1):
            task_id = task["id"]
            difficulty = task["difficulty"]

            # --skip-on-fail: skip medium/hard if easy already failed
            if args.skip_on_fail and easy_failed and difficulty != "easy":
                print(f"\n  [{task_idx}/{len(tasks)}] SKIP {task_id} [{difficulty}] (easy failed, --skip-on-fail)")
                results[f"{model_name}|{task_id}"] = {
                    "model": model_name,
                    "task_id": task_id,
                    "difficulty": difficulty,
                    "skipped": True,
                    "completed": False,
                }
                continue

            timeout_s = TASK_TIMEOUTS[difficulty]
            print(f"\n  [{task_idx}/{len(tasks)}] Task: {task_id} [{difficulty}]  (max {timeout_s // 60}min)")

            project_root = projects_dir / slug / task_id
            project_root.mkdir(parents=True, exist_ok=True)
            task_log = logs_dir / slug / f"{task_id}_{timestamp}.log"

            start_ts = time.time()
            timed_out = False
            # The agent enforces a soft limit internally (max_duration_seconds).
            # asyncio.wait_for adds a hard safety net (+2 min) in case a single LLM
            # call hangs after the soft limit fires.
            hard_timeout = timeout_s + 120
            try:
                result = asyncio.run(
                    asyncio.wait_for(
                        run_tools_agent_for_model(
                            task=task,
                            model_name=model_name,
                            project_root=project_root,
                            llm_manager=llm_manager,
                            log_path=task_log,
                            bench_logger=bench_logger,
                            max_duration_seconds=timeout_s,
                        ),
                        timeout=hard_timeout,
                    )
                )
            except asyncio.TimeoutError:
                timed_out = True
                elapsed = time.time() - start_ts
                bench_logger.warning(
                    f"[Benchmark] Task '{task_id}' TIMED OUT after {elapsed:.0f}s (limit {timeout_s}s)"
                )
                # Analyse whatever partial output was written before the timeout
                quality = analyze_project_quality(project_root) if project_root.is_dir() else {}
                result = {
                    "model": model_name,
                    "task_id": task_id,
                    "difficulty": difficulty,
                    "duration_seconds": round(elapsed, 1),
                    "total_tokens": 0,
                    "iterations": 0,
                    "files_generated": quality.get("files_total", 0),
                    "py_files": quality.get("py_files", 0),
                    "quality_score": quality.get("quality_score", 0.0),
                    "syntax_valid_pct": quality.get("syntax_valid_pct", 0.0),
                    "stub_files_pct": quality.get("stub_files_pct", 100.0),
                    "avg_lines_per_file": quality.get("avg_lines_per_file", 0.0),
                    "syntax_errors": quality.get("syntax_errors", []),
                    "completed": False,
                    "timed_out": True,
                    "error": f"Timed out after {timeout_s}s ({timeout_s // 60}min limit)",
                    "log_file": str(task_log),
                }

            result.setdefault("timed_out", False)
            results[f"{model_name}|{task_id}"] = result

            status = "⏱" if timed_out else ("✓" if result["completed"] else "✗")
            print(
                f"  {status} done={result['completed']} "
                f"quality={result['quality_score']:.3f} "
                f"files={result['files_generated']} "
                f"iters={result.get('iterations', 0)} "
                f"time={result['duration_seconds']:.0f}s" + (" [TIMEOUT]" if timed_out else "")
            )

            if args.skip_on_fail and difficulty == "easy" and not result["completed"]:
                easy_failed = True

        # After all tasks for this model, unload it from Ollama RAM before loading next model
        print(f"\n  Unloading {model_name} from RAM...")
        _unload_manager_models(llm_manager, slug)

    # --- Write outputs ---
    json_path = output_dir / f"model_benchmark_{timestamp}.json"
    txt_path = output_dir / f"model_benchmark_{timestamp}.txt"

    json_path.write_text(
        json.dumps(
            {
                "timestamp": timestamp,
                "models": models,
                "tasks": [t["id"] for t in tasks],
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    report = build_text_report(results, models, tasks, timestamp)
    txt_path.write_text(report, encoding="utf-8")

    print("\n" + report)
    print(f"\n✓ JSON results: {json_path}")
    print(f"✓ Text report:  {txt_path}")
    print(f"✓ Logs:         {logs_dir}/")


if __name__ == "__main__":
    main()
