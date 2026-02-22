#!/usr/bin/env python3
"""CLI wrapper for model benchmarking on autonomous project generation.

Usage:
    python auto_benchmark.py
    python auto_benchmark.py --models model1 model2
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse

# Use the new centralized config
from backend.core.config import get_config
from backend.agents.auto_benchmarker import ModelBenchmarker


def main():
    config = get_config()
    parser = argparse.ArgumentParser(description="Benchmark Ollama models on autonomous project generation.")
    parser.add_argument(
        "--models",
        nargs="*",
        help="Models to benchmark. If not provided, all local models are used.",
    )
    args = parser.parse_args()

    # Instantiate the benchmarker without config path
    benchmarker = ModelBenchmarker()

    if args.models:
        models_to_run = args.models
        print(f"Benchmarking specific models: {', '.join(models_to_run)}")
    else:
        all_local_models = benchmarker.get_local_models()
        if not all_local_models:
            print("No local Ollama models found. Pull some first (e.g., 'ollama pull llama2').")
            return

        chat_models = [m for m in all_local_models if m not in benchmarker.embedding_models and "embed" not in m]
        excluded_models = [m for m in all_local_models if m not in chat_models]

        if excluded_models:
            print(f"\nExcluding embedding models: {', '.join(excluded_models)}")

        models_to_run = chat_models
        benchmarker.print_model_table(models_to_run)

    benchmarker.run_benchmark(models_to_run)
    log_path = benchmarker.save_logs()

    # Get summary model from the new centralized config
    summary_model = config.LLM_MODELS.get("models", {}).get("summarization", config.DEFAULT_MODEL)

    print(f"\nGenerating summary with model: {summary_model}")
    report = benchmarker.generate_summary(summary_model)

    print(f"\n{'=' * 50}")
    print("AUTO-BENCHMARK REPORT - PROJECT GENERATION")
    print(f"{'=' * 50}")
    print(report)
    print(f"\nResults saved to: {log_path.parent} and {benchmarker.generated_projects_dir}")


if __name__ == "__main__":
    main()
