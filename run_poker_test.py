"""Test runner: Texas Hold'em Poker via AutoAgent with 3 refine loops.

Usage:
    python run_poker_test.py

Output: generated_projects/auto_agent_projects/JuegoPokerTexas/
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.core.containers import main_container

PROJECT_NAME = "JuegoPokerTexas"
PROJECT_DESCRIPTION = """
Texas Hold'em Poker game: HTML/CSS/JS single-page app, no server required.

REQUIRED FEATURES:
1. Full Texas Hold'em rules:
   - Small blind / big blind system
   - Betting rounds: preflop, flop, turn, river
   - Player actions: fold, check, call, raise
   - Side pots when all-in

2. Hand evaluation:
   - All 10 hand types: royal flush, straight flush, four of a kind,
     full house, flush, straight, three of a kind, two pair, one pair, high card
   - Correct winner determination with kicker comparison

3. 4 AI opponents:
   - Basic strategy: fold weak hands, call/raise strong hands
   - Each has a chip count and visible betting decisions

4. UI:
   - Card display with suit symbols (♠ ♥ ♦ ♣) and ranks
   - Community cards (flop/turn/river) area
   - Player hand area (face-up for human, face-down for AI)
   - Pot display and per-player chip counts
   - Action buttons: Fold, Check, Call, Raise (with input)
   - Win/loss message with hand name

STACK: Pure HTML + CSS + JavaScript (no npm, no build step).
Files: index.html, static/style.css, static/game.js (poker logic),
static/ai.js (AI decision engine), static/ui.js (DOM updates).
"""

NUM_REFINE_LOOPS = 3


def main() -> None:
    print("=" * 60)
    print(f"AutoAgent Test: {PROJECT_NAME}")
    print(f"Refine loops: {NUM_REFINE_LOOPS}")
    print("=" * 60)

    agent = main_container.auto_agent_module.auto_agent()

    start = time.monotonic()
    try:
        project_root = agent.run(
            description=PROJECT_DESCRIPTION,
            project_name=PROJECT_NAME,
            num_refine_loops=NUM_REFINE_LOOPS,
        )
        elapsed = time.monotonic() - start
        print(f"\n[OK] Project generated in {elapsed:.1f}s")
        print(f"     Path: {project_root}")
        _summarize(project_root)
    except Exception as exc:
        elapsed = time.monotonic() - start
        print(f"\n[ERROR] Pipeline failed after {elapsed:.1f}s: {exc}")
        raise


def _summarize(project_root: Path) -> None:
    """Print a quick file tree + size overview."""
    all_files = sorted(project_root.rglob("*"))
    code_files = [f for f in all_files if f.is_file() and not any(part.startswith(".") for part in f.parts)]
    print(f"\nGenerated {len(code_files)} files:")
    for f in code_files:
        size = f.stat().st_size
        rel = f.relative_to(project_root)
        print(f"  {rel}  ({size:,} bytes)")


if __name__ == "__main__":
    main()
