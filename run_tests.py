"""
Run unit tests in separate subprocess batches to avoid memory accumulation.
Usage:
    python run_tests.py            # all unit tests in batches
    python run_tests.py memory     # only memory/ tests
    python run_tests.py agents     # only agent phase tests
"""

import subprocess
import sys
from pathlib import Path

BATCHES = [
    # (label, path)
    ("memory",      "tests/unit/backend/utils/core/memory"),
    ("core utils",  "tests/unit/backend/utils/core/llm"),
    ("auto_gen",    "tests/unit/backend/utils/domains/auto_generation"),
    ("domains",     "tests/unit/backend/utils/domains"),
    ("phases",      "tests/unit/backend/agents/auto_agent_phases"),
    ("agents",      "tests/unit/backend/agents"),
    ("services",    "tests/unit/backend/services"),
    ("core",        "tests/unit/backend/core"),
    ("frontend",    "tests/unit/frontend"),
    ("llm",         "tests/unit/llm"),
]


def run_batch(label: str, path: str, extra_args: list[str]) -> int:
    if not Path(path).exists():
        return 0
    print(f"\n{'='*60}")
    print(f"  {label.upper()}: {path}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", path, "-q", "--tb=short", "--no-header", *extra_args],
        check=False,
    )
    return result.returncode


def main() -> None:
    filter_arg = sys.argv[1] if len(sys.argv) > 1 else None
    extra = sys.argv[2:] if len(sys.argv) > 2 else []

    failures = 0
    for label, path in BATCHES:
        if filter_arg and filter_arg.lower() not in label.lower():
            continue
        rc = run_batch(label, path, extra)
        if rc != 0:
            failures += 1

    print(f"\n{'='*60}")
    if failures:
        print(f"  {failures} batch(es) had failures.")
    else:
        print("  All batches passed.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
