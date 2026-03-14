import asyncio
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.agents.phase_benchmarker import PhaseBenchmarker


async def main():
    benchmarker = PhaseBenchmarker()
    models_to_test = ["qwen3.5:0.8b", "qwen3.5:4b", "qwen3.5:9b", "qwen3-coder:30b", "gpt-oss:120b"]

    print(f"Starting phase benchmark for: {models_to_test}")
    benchmarker.run_benchmark(models_to_test)

    output_file = Path("phase_benchmark_results.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("============================================================\n")
        f.write("PHASE BENCHMARK REPORT\n")
        f.write(
            f"Date: {benchmarker.results[0]['detailed_results'][0].get('timestamp', 'N/A') if benchmarker.results else 'N/A'}\n"
        )
        f.write("============================================================\n\n")

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
                f.write(f"    Score: {task.get('score', 0)}\n")
                f.write(f"    Duration: {task.get('duration', 0)}s\n")
                f.write(f"    Tokens: {task.get('tokens', 0)}\n")
                if not task.get("success", False) and "error" in task:
                    f.write(f"    Error: {task.get('error', 'Unknown error')}\n")
                f.write("\n")
            f.write("=" * 60 + "\n\n")

    print(f"Benchmark complete. Results saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
