#!/usr/bin/env python3
"""CLI wrapper for AutoAgent autonomous project creation.

Usage:
    python auto_agent.py --description "project description" --name "project_name"
"""
import argparse

from src.agents.auto_agent import AutoAgent


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous project creation with specialized LLMs."
    )
    parser.add_argument(
        "--description", required=True,
        help="Detailed description of the project to create.",
    )
    parser.add_argument(
        "--name", default="auto_generated_project",
        help="Name of the project directory.",
    )
    parser.add_argument(
        "--config", default="config/settings.json",
        help="Path to the configuration file.",
    )
    parser.add_argument(
        "--refine-loops", type=int, default=0,
        help="Number of iterative refinement loops to run after initial generation.",
    )
    args = parser.parse_args()

    agent = AutoAgent(config_path=args.config)
    path = agent.run(args.description, project_name=args.name, num_refine_loops=args.refine_loops)

    print(f"\n{'=' * 60}")
    print(f"Autonomous project creation finished")
    print(f"Project saved at: {path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
