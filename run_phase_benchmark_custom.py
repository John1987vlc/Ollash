"""Phase benchmark runner with quality metrics.

Usage:
    python run_phase_benchmark_custom.py
    python run_phase_benchmark_custom.py --quality-check <project_dir>

The --quality-check flag skips LLM benchmarking and instead scans an
already-generated project directory for syntax validity and stub presence.
"""

from __future__ import annotations

import ast
import asyncio
import re
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.agents.phase_benchmarker import PhaseBenchmarker

# ---------------------------------------------------------------------------
# Quality analysis helpers
# ---------------------------------------------------------------------------

_STUB_PATTERNS = [
    re.compile(r"\bpass\b"),
    re.compile(r"\bTODO\b"),
    re.compile(r"\bNotImplementedError\b"),
    re.compile(r"\.\.\.$", re.MULTILINE),
    re.compile(r"raise NotImplementedError"),
]


def _count_stubs(source: str) -> int:
    """Count the number of stub indicators in *source*."""
    return sum(len(p.findall(source)) for p in _STUB_PATTERNS)


def analyze_project_quality(project_dir: Path) -> dict:
    """Scan a generated project directory and return quality metrics.

    Checks:
    - Python syntax validity (ast.parse)
    - Presence of stub patterns (pass / TODO / NotImplementedError / ...)
    - Average lines per file

    Returns a dict with summary statistics.
    """
    py_files = list(project_dir.rglob("*.py"))
    if not py_files:
        return {"error": f"No .py files found in {project_dir}"}

    total = len(py_files)
    syntax_ok = 0
    stub_files = 0
    total_lines = 0
    errors: list[dict] = []

    for f in py_files:
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        lines = source.count("\n") + 1
        total_lines += lines

        # Syntax check
        try:
            ast.parse(source)
            syntax_ok += 1
        except SyntaxError as e:
            errors.append({"file": str(f.relative_to(project_dir)), "error": str(e)})

        # Stub check
        if _count_stubs(source) > 0:
            stub_files += 1

    return {
        "project_dir": str(project_dir),
        "total_py_files": total,
        "syntax_valid": syntax_ok,
        "syntax_valid_pct": round(100.0 * syntax_ok / total, 1),
        "stub_files": stub_files,
        "stub_files_pct": round(100.0 * stub_files / total, 1),
        "avg_lines_per_file": round(total_lines / total, 1),
        "syntax_errors": errors,
    }


def print_quality_report(metrics: dict) -> None:
    print("\n" + "=" * 60)
    print("PROJECT QUALITY REPORT")
    print("=" * 60)
    if "error" in metrics:
        print(f"  ERROR: {metrics['error']}")
        return
    print(f"  Directory     : {metrics['project_dir']}")
    print(f"  Python files  : {metrics['total_py_files']}")
    print(f"  Syntax valid  : {metrics['syntax_valid']} ({metrics['syntax_valid_pct']}%)")
    print(f"  Files w/ stubs: {metrics['stub_files']} ({metrics['stub_files_pct']}%)")
    print(f"  Avg lines/file: {metrics['avg_lines_per_file']}")
    if metrics["syntax_errors"]:
        print("\n  Syntax errors:")
        for e in metrics["syntax_errors"][:10]:
            print(f"    [{e['file']}] {e['error']}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------


async def main() -> None:
    # Quality-only mode: python run_phase_benchmark_custom.py --quality-check <dir>
    if "--quality-check" in sys.argv:
        idx = sys.argv.index("--quality-check")
        if idx + 1 >= len(sys.argv):
            print("Usage: run_phase_benchmark_custom.py --quality-check <project_dir>")
            sys.exit(1)
        target = Path(sys.argv[idx + 1])
        if not target.exists():
            print(f"Directory not found: {target}")
            sys.exit(1)
        metrics = analyze_project_quality(target)
        print_quality_report(metrics)
        return

    # Full LLM benchmark
    benchmarker = PhaseBenchmarker()
    models_to_test = ["qwen3.5:0.8b", "qwen3.5:4b", "qwen3.5:9b", "qwen3-coder:30b", "gpt-oss:120b"]

    print(f"Starting phase benchmark for: {models_to_test}")
    benchmarker.run_benchmark(models_to_test)

    output_file = Path("phase_benchmark_results.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("PHASE BENCHMARK REPORT\n")
        ts = benchmarker.results[0]["detailed_results"][0].get("timestamp", "N/A") if benchmarker.results else "N/A"
        f.write(f"Date: {ts}\n")
        f.write("=" * 60 + "\n\n")

        for model_res in benchmarker.results:
            model_name = model_res["model"]
            f.write(f"MODEL: {model_name}\n")
            f.write("-" * 40 + "\n")
            f.write("PHASE SCORES:\n")
            for phase, score in model_res["phase_scores"].items():
                f.write(f"  - {phase}: {score}\n")
            f.write("\nDETAILED TASKS:\n")
            for task in model_res["detailed_results"]:
                f.write(f"  [{task.get('phase', 'N/A')}] {task.get('task', 'N/A')}\n")
                f.write(f"    Score   : {task.get('score', 0)}\n")
                f.write(f"    Duration: {task.get('duration', 0)}s\n")
                f.write(f"    Tokens  : {task.get('tokens', 0)}\n")
                if not task.get("success", False) and "error" in task:
                    f.write(f"    Error   : {task.get('error', 'Unknown error')}\n")
                f.write("\n")

            # Per-model quality check on generated output directory (if present)
            gen_dir = Path("generated_projects") / "auto_agent_projects"
            if gen_dir.exists():
                subdirs = sorted(gen_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                if subdirs:
                    q = analyze_project_quality(subdirs[0])
                    f.write("QUALITY METRICS (most recent generated project):\n")
                    f.write(f"  Syntax valid : {q.get('syntax_valid_pct', 'N/A')}%\n")
                    f.write(f"  Stub files   : {q.get('stub_files_pct', 'N/A')}%\n")
                    f.write(f"  Avg lines/file: {q.get('avg_lines_per_file', 'N/A')}\n")
            f.write("=" * 60 + "\n\n")

    print(f"Benchmark complete. Results saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
