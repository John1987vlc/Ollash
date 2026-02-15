#!/usr/bin/env python3
"""CLI wrapper for AutoAgent autonomous project creation."""
import argparse
import sys
from pathlib import Path

# Ensure the backend is in the Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from backend.core.containers import main_container
from backend.agents.auto_agent import AutoAgent

def main():
    # Wire the container to the modules that need injection
    main_container.wire(modules=[__name__, "backend.agents.auto_agent"])
    
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
    # Add other relevant arguments from the AutoAgent's run method
    parser.add_argument("--num-refine-loops", type=int, default=0)
    parser.add_argument("--template-name", type=str, default="default")
    parser.add_argument("--python-version", type=str, default="3.11")
    parser.add_argument("--license-type", type=str, default="MIT")
    parser.add_argument("--include-docker", action="store_true")
    
    args = parser.parse_args()

    # Instantiate AutoAgent via the DI container
    try:
        agent: AutoAgent = main_container.auto_agent_module.auto_agent()
        
        # Prepare kwargs for the run method
        run_kwargs = {
            "project_description": args.description,
            "project_name": args.name,
            "num_refine_loops": args.num_refine_loops,
            "template_name": args.template_name,
            "python_version": args.python_version,
            "license_type": args.license_type,
            "include_docker": args.include_docker,
        }
        
        path = agent.run(**run_kwargs)

        print(f"\n{'=' * 60}")
        print(f"Autonomous project creation finished")
        print(f"Project saved at: {path}")
        print(f"{'=' * 60}")

    except Exception as e:
        print(f"\n{'!' * 60}")
        print(f"An error occurred during project generation: {e}")
        print(f"{'!' * 60}")
        # Optionally, re-raise or exit with an error code
        sys.exit(1)


if __name__ == "__main__":
    main()
