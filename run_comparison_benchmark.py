"""Comparison benchmark: AutoAgent (classic) vs AutoAgentWithTools (tools).

Runs both agents sequentially on a set of predefined project descriptions,
collects quality/performance metrics for each, and outputs a side-by-side
comparison report.

Usage:
    python run_comparison_benchmark.py
    python run_comparison_benchmark.py --tasks todo_api cli_tool
    python run_comparison_benchmark.py --tasks todo_api --skip-classic
    python run_comparison_benchmark.py --tasks todo_api --skip-tools

Output files (in current directory):
    comparison_results_<timestamp>.json   — full metric data
    comparison_results_<timestamp>.txt    — human-readable comparison table
    logs/classic_<task>_<timestamp>.log   — AutoAgent log for each task
    logs/tools_<task>_<timestamp>.log     — AutoAgentWithTools log for each task
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
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ---------------------------------------------------------------------------
# Benchmark task definitions
# ---------------------------------------------------------------------------

BENCHMARK_TASKS: Dict[str, Dict[str, str]] = {
    "todo_api": {
        "name": "todo_api",
        "description": (
            "REST API for a todo list with CRUD operations (create, read, update, delete), "
            "SQLite persistence using sqlite3, and FastAPI. Include Pydantic models, "
            "async endpoints, and basic error handling."
        ),
    },
    "cli_tool": {
        "name": "cli_tool",
        "description": (
            "Python CLI tool using Click that converts CSV files to JSON and JSON files "
            "back to CSV. Support --input and --output flags. Handle encoding errors gracefully."
        ),
    },
    "web_scraper": {
        "name": "web_scraper",
        "description": (
            "Python web scraper using httpx and BeautifulSoup4 that extracts product names "
            "and prices from an HTML page. Accept a URL argument, output results as JSON."
        ),
    },
    "auth_service": {
        "name": "auth_service",
        "description": (
            "Python microservice for JWT-based user authentication. "
            "Endpoints: POST /register, POST /login, POST /refresh. "
            "Use FastAPI, passlib for password hashing, python-jose for JWT. "
            "Store users in a SQLite database."
        ),
    },
    "data_pipeline": {
        "name": "data_pipeline",
        "description": (
            "Python data pipeline that reads a CSV file, computes descriptive statistics "
            "(mean, median, std dev, min, max) per numeric column using only stdlib, "
            "and writes a summary report to a text file."
        ),
    },
}

# ---------------------------------------------------------------------------
# Quality analysis (adapted from test_run/run_phase_benchmark_custom.py)
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
    py_files = list(project_dir.rglob("*.py"))
    skip_dirs = {"__pycache__", "node_modules", ".venv", "venv"}

    # Filter out files in skip dirs
    py_files = [f for f in py_files if not any(part in skip_dirs for part in f.parts)]

    all_files = [
        f
        for f in project_dir.rglob("*")
        if f.is_file() and not any(part in skip_dirs for part in f.parts) and not f.name.startswith(".")
    ]

    if not py_files and not all_files:
        return {
            "files_total": 0,
            "syntax_valid_pct": 0.0,
            "stub_files_pct": 100.0,
            "avg_lines_per_file": 0.0,
            "quality_score": 0.0,
            "syntax_errors": [],
        }

    total = len(py_files)
    syntax_ok = 0
    stub_files = 0
    total_lines = 0
    syntax_errors: List[Dict[str, str]] = []

    for f in py_files:
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = source.count("\n") + 1
        total_lines += lines

        try:
            ast.parse(source)
            syntax_ok += 1
        except SyntaxError as e:
            syntax_errors.append({"file": str(f.relative_to(project_dir)), "error": str(e)})

        if _count_stubs(source) > 0:
            stub_files += 1

    syntax_valid_pct = (syntax_ok / total * 100) if total > 0 else 100.0
    stub_files_pct = (stub_files / total * 100) if total > 0 else 0.0
    avg_lines = (total_lines / total) if total > 0 else 0.0

    # Quality score: weighted combination of syntax validity and stub absence
    quality_score = (syntax_valid_pct / 100) * 0.6 + ((100 - stub_files_pct) / 100) * 0.4

    return {
        "files_total": len(all_files),
        "py_files": total,
        "syntax_valid_pct": round(syntax_valid_pct, 1),
        "stub_files_pct": round(stub_files_pct, 1),
        "avg_lines_per_file": round(avg_lines, 1),
        "quality_score": round(quality_score, 3),
        "syntax_errors": syntax_errors[:5],  # cap at 5 for readability
    }


# ---------------------------------------------------------------------------
# Agent runner helpers
# ---------------------------------------------------------------------------


def _setup_file_logger(log_path: Path) -> logging.Logger:
    """Create a file logger for capturing agent output."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"bench_{log_path.stem}")
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(message)s"))
    logger.addHandler(handler)
    return logger


class _NullEventPublisher:
    """Minimal event publisher that logs SSE events to a file."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    async def publish(self, event_type: str, data: Any) -> None:
        self._logger.info(f"[SSE] {event_type}: {json.dumps(data, default=str)[:200]}")

    def push_event(self, event_type: str, data: Any) -> None:  # sync compat
        self._logger.info(f"[SSE] {event_type}: {json.dumps(data, default=str)[:200]}")


class _NullFileManager:
    """Stub file manager — not used by either agent directly in the benchmark."""

    pass


class _BenchLogger:
    """Minimal agent logger that writes to both file and stdout."""

    def __init__(self, file_logger: logging.Logger, label: str) -> None:
        self._file = file_logger
        self._label = label

    def _log(self, level: str, msg: str) -> None:
        fn = getattr(self._file, level, self._file.info)
        fn(msg)
        print(f"  [{self._label}] {msg}")

    def info(self, msg: str, **_: Any) -> None:
        self._log("info", msg)

    def warning(self, msg: str, **_: Any) -> None:
        self._log("warning", msg)

    def debug(self, msg: str, **_: Any) -> None:
        self._file.debug(msg)  # debug only to file

    def error(self, msg: str, exc_info: bool = False, **_: Any) -> None:
        self._log("error", msg)


def _build_llm_manager() -> Any:
    """Build the LLM client manager from the DI container."""
    from backend.core.containers import main_container

    main_container.init_resources()
    return main_container.auto_agent_module.llm_client_manager()


def _unload_all_models(llm_manager: Any) -> None:
    """Unload every cached Ollama model from RAM.

    Called between agent runs so the next model doesn't OOM when loading.
    LLMClientManager caches one OllamaClient per model in .clients_by_model.
    """
    clients = getattr(llm_manager, "clients_by_model", {})
    if not clients:
        return
    print(f"\n  [unload] Freeing {len(clients)} model(s) from Ollama RAM: {', '.join(clients)}")
    for model_name, client in clients.items():
        try:
            client.unload_model()
            print(f"  [unload] ✓ {model_name}")
        except Exception as e:
            print(f"  [unload] ✗ {model_name}: {e}")


def run_classic_agent(
    task: Dict[str, str],
    project_root: Path,
    llm_manager: Any,
    log_path: Path,
) -> Dict[str, Any]:
    """Run AutoAgent (classic) on a task. Returns metric dict."""
    from backend.agents.auto_agent import AutoAgent

    file_logger = _setup_file_logger(log_path)
    agent_logger = _BenchLogger(file_logger, "classic")
    event_publisher = _NullEventPublisher(file_logger)
    file_manager = _NullFileManager()

    agent = AutoAgent(
        llm_manager=llm_manager,
        file_manager=file_manager,
        event_publisher=event_publisher,
        logger=agent_logger,
        generated_projects_dir=project_root.parent,
    )
    # Patch event_publisher so phases can call it (they access agent.event_publisher)
    agent.event_publisher = event_publisher

    start = time.time()
    completed = False
    error_msg = ""

    try:
        agent.run(
            description=task["description"],
            project_name=project_root.name,
            project_root=project_root,
        )
        completed = True
    except Exception as e:
        error_msg = str(e)
        agent_logger.error(f"AutoAgent failed: {e}")

    duration = time.time() - start

    quality = analyze_project_quality(project_root) if project_root.is_dir() else {}

    return {
        "agent": "classic",
        "project_id": task["name"],
        "duration_seconds": round(duration, 1),
        "total_tokens": 0,  # AutoAgent doesn't expose total tokens directly
        "files_generated": quality.get("files_total", 0),
        "quality_score": quality.get("quality_score", 0.0),
        "syntax_valid_pct": quality.get("syntax_valid_pct", 0.0),
        "stub_files_pct": quality.get("stub_files_pct", 100.0),
        "avg_lines_per_file": quality.get("avg_lines_per_file", 0.0),
        "error_count": len(quality.get("syntax_errors", [])),
        "completed": completed,
        "error": error_msg,
        "log_file": str(log_path),
    }


async def run_tools_agent(
    task: Dict[str, str],
    project_root: Path,
    llm_manager: Any,
    log_path: Path,
) -> Dict[str, Any]:
    """Run AutoAgentWithTools on a task. Returns metric dict."""
    from backend.agents.auto_agent_with_tools import AutoAgentWithTools

    file_logger = _setup_file_logger(log_path)
    agent_logger = _BenchLogger(file_logger, "tools")
    event_publisher = _NullEventPublisher(file_logger)
    file_manager = _NullFileManager()

    agent = AutoAgentWithTools(
        llm_manager=llm_manager,
        file_manager=file_manager,
        event_publisher=event_publisher,
        logger=agent_logger,
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
        )
        completed = True
    except Exception as e:
        error_msg = str(e)
        agent_logger.error(f"AutoAgentWithTools failed: {e}")

    duration = time.time() - start

    quality = analyze_project_quality(project_root) if project_root.is_dir() else {}

    return {
        "agent": "tools",
        "project_id": task["name"],
        "duration_seconds": round(duration, 1),
        "total_tokens": agent._total_tokens,
        "iterations": agent._iteration_count,
        "files_generated": quality.get("files_total", 0),
        "quality_score": quality.get("quality_score", 0.0),
        "syntax_valid_pct": quality.get("syntax_valid_pct", 0.0),
        "stub_files_pct": quality.get("stub_files_pct", 100.0),
        "avg_lines_per_file": quality.get("avg_lines_per_file", 0.0),
        "error_count": len(quality.get("syntax_errors", [])),
        "completed": completed,
        "error": error_msg,
        "log_file": str(log_path),
    }


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def _fmt(val: Any, metric: str) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, bool):
        return "Yes" if val else "No"
    if metric in ("quality_score",):
        return f"{val:.3f}"
    if metric in ("syntax_valid_pct", "stub_files_pct"):
        return f"{val:.1f}%"
    if metric in ("duration_seconds",):
        return f"{val:.1f}s"
    if isinstance(val, float):
        return f"{val:.1f}"
    return str(val)


DISPLAY_METRICS = [
    ("duration_seconds", "Duration"),
    ("total_tokens", "Tokens"),
    ("iterations", "Tool iterations"),
    ("files_generated", "Files generated"),
    ("quality_score", "Quality score"),
    ("syntax_valid_pct", "Syntax valid (%)"),
    ("stub_files_pct", "Stub files (%)"),
    ("avg_lines_per_file", "Avg lines/file"),
    ("error_count", "Syntax errors"),
    ("completed", "Completed"),
]


def build_text_report(
    results: Dict[str, Dict[str, Any]],
    tasks: List[str],
    timestamp: str,
) -> str:
    lines = [
        "=" * 60,
        "  CLASSIC vs TOOLS — Comparison Benchmark",
        f"  Date: {timestamp}",
        "=" * 60,
    ]

    for task_id in tasks:
        classic = results.get(f"{task_id}_classic")
        tools = results.get(f"{task_id}_tools")

        lines.append(f"\nPROJECT: {task_id}")
        lines.append("-" * 60)
        lines.append(f"{'Metric':<28} {'Classic':>14} {'Tools':>14}")
        lines.append("-" * 60)

        for metric_key, metric_label in DISPLAY_METRICS:
            c_val = _fmt(classic.get(metric_key) if classic else None, metric_key)
            t_val = _fmt(tools.get(metric_key) if tools else None, metric_key)
            lines.append(f"{metric_label:<28} {c_val:>14} {t_val:>14}")

    lines.append("\n" + "=" * 60)

    # Overall summary
    completed_classic = sum(1 for k, v in results.items() if k.endswith("_classic") and v.get("completed"))
    completed_tools = sum(1 for k, v in results.items() if k.endswith("_tools") and v.get("completed"))
    total_tasks = len(tasks)

    avg_quality_classic = _safe_avg(
        [
            results[f"{t}_classic"].get("quality_score", 0)
            for t in tasks
            if f"{t}_classic" in results and results[f"{t}_classic"].get("completed")
        ]
    )
    avg_quality_tools = _safe_avg(
        [
            results[f"{t}_tools"].get("quality_score", 0)
            for t in tasks
            if f"{t}_tools" in results and results[f"{t}_tools"].get("completed")
        ]
    )

    lines += [
        "\nSUMMARY",
        "-" * 60,
        f"{'Tasks completed':<28} {f'{completed_classic}/{total_tasks}':>14} {f'{completed_tools}/{total_tasks}':>14}",
        f"{'Avg quality score':<28} {f'{avg_quality_classic:.3f}':>14} {f'{avg_quality_tools:.3f}':>14}",
        "=" * 60,
    ]

    return "\n".join(lines)


def _safe_avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Classic vs Tools agent comparison benchmark")
    parser.add_argument(
        "--tasks",
        nargs="+",
        choices=list(BENCHMARK_TASKS.keys()),
        default=list(BENCHMARK_TASKS.keys()),
        help="Task IDs to run (default: all)",
    )
    parser.add_argument("--skip-classic", action="store_true", help="Skip AutoAgent (classic)")
    parser.add_argument("--skip-tools", action="store_true", help="Skip AutoAgentWithTools (tools)")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for output JSON/TXT files (default: .)",
    )
    parser.add_argument(
        "--projects-dir",
        default="comparison_benchmark_projects",
        help="Directory for generated projects (default: comparison_benchmark_projects/)",
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    projects_dir = Path(args.projects_dir).resolve()
    projects_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("  Ollash — Classic vs Tools Comparison Benchmark")
    print(f"  Tasks: {', '.join(args.tasks)}")
    print(f"  Classic: {'SKIP' if args.skip_classic else 'YES'}")
    print(f"  Tools:   {'SKIP' if args.skip_tools else 'YES'}")
    print("=" * 60 + "\n")

    # Build LLM manager once (shared by both agents)
    print("Initializing LLM manager...")
    try:
        llm_manager = _build_llm_manager()
    except Exception as e:
        print(f"ERROR: Could not build LLM manager: {e}")
        print("Make sure the Ollash DI container is properly configured.")
        sys.exit(1)

    results: Dict[str, Any] = {}

    for task_id in args.tasks:
        task = BENCHMARK_TASKS[task_id]
        print(f"\n{'─' * 60}")
        print(f"  TASK: {task_id}")
        print(f"{'─' * 60}")

        # --- Classic agent ---
        if not args.skip_classic:
            print(f"\n[1/2] Running AutoAgent (classic) on '{task_id}'...")
            classic_root = projects_dir / f"{task_id}_classic"
            classic_log = logs_dir / f"classic_{task_id}_{timestamp}.log"
            result = run_classic_agent(task, classic_root, llm_manager, classic_log)
            results[f"{task_id}_classic"] = result
            print(
                f"  Done: completed={result['completed']} "
                f"files={result['files_generated']} "
                f"quality={result['quality_score']:.3f} "
                f"time={result['duration_seconds']:.1f}s"
            )
            # Unload classic agent models before the next phase/task (save RAM)
            _unload_all_models(llm_manager)

        # --- Tools agent ---
        if not args.skip_tools:
            print(f"\n[2/2] Running AutoAgentWithTools on '{task_id}'...")
            tools_root = projects_dir / f"{task_id}_tools"
            tools_log = logs_dir / f"tools_{task_id}_{timestamp}.log"
            result = asyncio.run(run_tools_agent(task, tools_root, llm_manager, tools_log))
            results[f"{task_id}_tools"] = result
            print(
                f"  Done: completed={result['completed']} "
                f"files={result['files_generated']} "
                f"quality={result['quality_score']:.3f} "
                f"time={result['duration_seconds']:.1f}s "
                f"iters={result.get('iterations', '?')}"
            )
            # Unload tools agent model before next task (AutoAgentWithTools already calls
            # unload_model() internally, but this covers any residual cached entries)
            _unload_all_models(llm_manager)

    # --- Write outputs ---
    json_path = output_dir / f"comparison_results_{timestamp}.json"
    txt_path = output_dir / f"comparison_results_{timestamp}.txt"

    json_path.write_text(
        json.dumps({"timestamp": timestamp, "tasks": args.tasks, "results": results}, indent=2),
        encoding="utf-8",
    )

    report = build_text_report(results, args.tasks, timestamp)
    txt_path.write_text(report, encoding="utf-8")

    print("\n" + report)
    print(f"\n✓ JSON results: {json_path}")
    print(f"✓ Text report:  {txt_path}")
    print(f"✓ Agent logs:   {logs_dir}/")


if __name__ == "__main__":
    main()
