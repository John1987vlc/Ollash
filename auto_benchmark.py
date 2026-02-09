#!/usr/bin/env python3
"""CLI wrapper for model benchmarking on autonomous project generation.

Usage:
    python auto_benchmark.py
    python auto_benchmark.py --models model1 model2
"""
import argparse

from src.agents.auto_benchmarker import ModelBenchmarker


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Ollama models on autonomous project generation."
    )
    parser.add_argument(
        "--models", nargs="*",
        help="Models to benchmark. If not provided, all local models are used.",
    )
    parser.add_argument(
        "--config", default="config/settings.json",
        help="Path to the configuration file.",
    )
    args = parser.parse_args()

    benchmarker = ModelBenchmarker(config_path=args.config)

    if args.models:
        models = args.models
        print(f"Benchmarking specific models: {', '.join(models)}")
    else:
        models = benchmarker.get_local_models()
        if not models:
            print("No local Ollama models found. Pull some first (e.g., 'ollama pull llama2').")
            return
        benchmarker.print_model_table(models)

    benchmarker.run_benchmark(models)
    log_path = benchmarker.save_logs()

    summary_model = benchmarker.config.get("summary_model", "ministral-3:8b")
    print(f"\nGenerating summary with model: {summary_model}")
    report = benchmarker.generate_summary(summary_model)

    print(f"\n{'=' * 50}")
    print("AUTO-BENCHMARK REPORT - PROJECT GENERATION")
    print(f"{'=' * 50}")
    print(report)
    print(f"\nResults saved to: {log_path.parent} and {benchmarker.generated_projects_dir}")


if __name__ == "__main__":
    main()
