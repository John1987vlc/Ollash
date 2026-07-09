#!/usr/bin/env python3
"""run_poker_test.py — Auto-generate a HTML/CSS/JS/SVG poker game using AutoAgent.

This script creates a complete, playable poker game with:
- HTML5 structure (no external images, SVG cards)
- CSS3 styling with responsive layout
- Vanilla JavaScript for game logic
- Pure SVG for card rendering

Usage:
    python run_poker_test.py
    python run_poker_test.py --model "nemotron-cascade-2:30b"
    python run_poker_test.py --model "ministral-3:8b" --project-name "my_poker"

Output:
    generated_projects/auto_agent_projects/poker_game_<timestamp>/
        ├── index.html
        ├── style.css
        ├── game.js
        └── cards.svg
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent))


def setup_logger() -> logging.Logger:
    """Setup console logger with colored output."""
    logger = logging.getLogger("run_poker_test")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


class MinimalEventPublisher:
    """Minimal event publisher for AutoAgent."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    async def publish(self, event_type: str, data: Any = None, **kwargs: Any) -> None:
        """Async publish (required by AutoAgent phases)."""
        msg = data.get('message', '') if data else kwargs.get('message', '')
        if event_type in ("iteration", "phase_complete"):
            self._logger.info(f"→ {event_type}: {msg[:100]}")

    def publish_sync(self, event_type: str, event_data: dict = None, **kwargs: Any) -> None:
        """Synchronous publish (required by AutoAgent phases)."""
        msg = event_data.get('message', '') if event_data else kwargs.get('message', '')
        if event_type in ("iteration", "phase_complete"):
            self._logger.info(f"→ {event_type}: {msg[:100]}")

    def push_event(self, event_type: str, data: Any) -> None:
        """Sync version for backward compatibility."""
        pass


class MinimalLogger:
    """Minimal logger for AutoAgent phases."""

    def __init__(self, base_logger: logging.Logger) -> None:
        self._logger = base_logger

    def info(self, msg: str, **_: Any) -> None:
        self._logger.info(msg)

    def warning(self, msg: str, **_: Any) -> None:
        self._logger.warning(msg)

    def debug(self, msg: str, **_: Any) -> None:
        pass  # silence debug

    def error(self, msg: str, **_: Any) -> None:
        self._logger.error(msg)


def consolidate_into_single_html(project_root: Path, logger: logging.Logger) -> None:
    """Combine CSS and JS files into a single index.html with embedded content.
    
    Reads all CSS files and places them in <style> tags in <head>.
    Reads all JS files and places them in <script> tags in <body>.
    Deletes original CSS and JS files, keeping only index.html.
    """
    logger.info("=" * 70)
    logger.info("Consolidating multi-file project into single index.html...")
    logger.info("=" * 70)

    index_path = project_root / "index.html"
    if not index_path.exists():
        logger.warning("index.html not found, skipping consolidation")
        return

    # Read original index.html
    html_content = index_path.read_text(encoding="utf-8")
    
    # Collect all CSS files
    css_files = list(project_root.rglob("*.css"))
    all_css = ""
    for css_file in css_files:
        try:
            css_content = css_file.read_text(encoding="utf-8")
            all_css += f"\n/* From: {css_file.relative_to(project_root)} */\n{css_content}\n"
            logger.info(f"  ✓ Embedded CSS: {css_file.relative_to(project_root)}")
        except Exception as e:
            logger.warning(f"  ✗ Failed to read {css_file}: {e}")

    # Collect all JS files (except any that might be in node_modules or .ollash)
    skip_dirs = {"node_modules", ".ollash", "__pycache__", ".git"}
    js_files = [
        f for f in project_root.rglob("*.js")
        if not any(part in skip_dirs for part in f.parts)
    ]
    all_js = ""
    for js_file in js_files:
        try:
            js_content = js_file.read_text(encoding="utf-8")
            all_js += f"\n// ========== From: {js_file.relative_to(project_root)} ==========\n{js_content}\n"
            logger.info(f"  ✓ Embedded JS: {js_file.relative_to(project_root)}")
        except Exception as e:
            logger.warning(f"  ✗ Failed to read {js_file}: {e}")

    # Build consolidated HTML
    # Check if there's already a <head> and <body> tag
    if "<head>" in html_content:
        # Insert CSS before closing </head>
        html_content = html_content.replace(
            "</head>",
            f"\n<style>\n{all_css}\n</style>\n</head>"
        )
    else:
        # Create <head> with CSS if it doesn't exist
        html_content = html_content.replace(
            "<!DOCTYPE html>",
            f"<!DOCTYPE html>\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n<title>Poker Game</title>\n<style>\n{all_css}\n</style>\n</head>"
        )

    # Insert JS before closing </body> or at end
    if "</body>" in html_content:
        html_content = html_content.replace(
            "</body>",
            f"\n<script>\n{all_js}\n</script>\n</body>"
        )
    else:
        # Append <body> with JS if it doesn't exist
        html_content += f"\n<body>\n<div id='app'></div>\n<script>\n{all_js}\n</script>\n</body>"

    # Write consolidated index.html
    index_path.write_text(html_content, encoding="utf-8")
    logger.info(f"  ✓ Consolidated index.html: {len(all_css)} bytes CSS + {len(all_js)} bytes JS")

    # Delete original CSS and JS files
    for css_file in css_files:
        try:
            css_file.unlink()
            logger.info(f"  ✓ Deleted: {css_file.relative_to(project_root)}")
        except Exception as e:
            logger.warning(f"  ✗ Failed to delete {css_file}: {e}")

    for js_file in js_files:
        try:
            js_file.unlink()
            logger.info(f"  ✓ Deleted: {js_file.relative_to(project_root)}")
        except Exception as e:
            logger.warning(f"  ✗ Failed to delete {js_file}: {e}")

    # Delete empty directories
    for dir_path in sorted(project_root.rglob("*"), reverse=True):
        if dir_path.is_dir() and not any(dir_path.iterdir()):
            try:
                dir_path.rmdir()
                logger.info(f"  ✓ Removed empty dir: {dir_path.relative_to(project_root)}")
            except Exception as e:
                logger.warning(f"  ✗ Failed to remove {dir_path}: {e}")

    logger.info("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate a playable poker game with HTML/CSS/JS/SVG"
    )
    parser.add_argument(
        "--model",
        default="nemotron-cascade-2:30b",
        help="Ollama model to use (default: nemotron-cascade-2:30b)",
    )
    parser.add_argument(
        "--project-name",
        default="poker_game",
        help="Project name (default: poker_game)",
    )
    parser.add_argument(
        "--refine-loops",
        type=int,
        default=2,
        help="Number of refinement loops (default: 2)",
    )

    args = parser.parse_args()

    logger = setup_logger()
    logger.info("=" * 70)
    logger.info("  POKER GAME GENERATOR — HTML/CSS/JS/SVG")
    logger.info("=" * 70)

    # Initialize DI container
    logger.info("Initializing Ollash DI container...")
    from backend.core.containers import main_container

    try:
        main_container.init_resources()
    except Exception as e:
        logger.error(f"Failed to initialize container: {e}")
        sys.exit(1)

    # Build AutoAgent
    logger.info(f"Building AutoAgent with model: {args.model}")

    try:
        llm_manager = main_container.auto_agent_module.llm_client_manager()
        file_manager = main_container.core.storage.file_manager()
    except Exception as e:
        logger.error(f"Failed to get LLM manager or file manager: {e}")
        sys.exit(1)

    from backend.agents.auto_agent import AutoAgent

    event_publisher = MinimalEventPublisher(logger)
    agent_logger = MinimalLogger(logger)

    generated_base = Path(__file__).resolve().parent / "generated_projects" / "auto_agent_projects"
    generated_base.mkdir(parents=True, exist_ok=True)

    agent = AutoAgent(
        llm_manager=llm_manager,
        file_manager=file_manager,
        event_publisher=event_publisher,
        logger=agent_logger,
        generated_projects_dir=generated_base,
    )
    agent.event_publisher = event_publisher

    # Define the poker game prompts
    project_description = """
Create a single, self-contained index.html file with an embedded, playable Texas Hold'em poker game.

REQUIREMENTS:
- Only ONE file: index.html
- Embedded CSS in <style> tag (felt table, card styling, responsive layout)
- Embedded JavaScript in <script> tag (all game logic in vanilla ES6+)
- All 52 cards rendered as inline SVG (no image files)
- Game features: Human vs AI, hand evaluation, betting rounds, pot management
- No external libraries, imports, or CDNs
- No separate CSS or JS files — everything embedded in index.html
    """

    logger.info(f"Project name: {args.project_name}")
    logger.info(f"Refinement loops: {args.refine_loops}")
    logger.info("=" * 70)
    logger.info("Starting project generation pipeline...")
    logger.info("=" * 70)

    start_time = time.time()
    project_root = None
    error_msg = ""

    try:
        project_root = agent.run(
            description=project_description,
            project_name=args.project_name,
            num_refine_loops=args.refine_loops,
        )
        logger.info(f"✓ Project generated successfully: {project_root}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"✗ Project generation failed: {e}", exc_info=True)
        sys.exit(1)

    finally:
        duration = time.time() - start_time

    # Consolidate into single HTML file
    if project_root and project_root.exists():
        consolidate_into_single_html(project_root, logger)

    # Display results
    logger.info("=" * 70)
    logger.info("  PROJECT GENERATION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Duration: {duration:.1f}s")
    logger.info(f"Project root: {project_root}")

    if project_root and project_root.exists():
        logger.info("\nGenerated files:")
        all_files = sorted([f for f in project_root.rglob("*") if f.is_file()])
        for file in all_files[:20]:  # show first 20 files
            rel_path = file.relative_to(project_root)
            size = file.stat().st_size
            logger.info(f"  • {rel_path} ({size} bytes)")

        if len(all_files) > 20:
            logger.info(f"  ... and {len(all_files) - 20} more files")

        logger.info(f"\nTotal files: {len(all_files)}")

    logger.info("=" * 70)


if __name__ == "__main__":
    main()
