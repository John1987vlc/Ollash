#!/usr/bin/env python3
"""CLI wrapper for phase-specific model benchmarking.

Usage:
    python run_phase_benchmark.py
    python run_phase_benchmark.py --models model1 model2
"""
import argparse
import sys
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent))

from backend.agents.phase_benchmarker import PhaseBenchmarker


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Ollama models on specific AutoAgent phases."
    )
    parser.add_argument(
        "--models", nargs="*",
        help="Models to benchmark. If not provided, a subset of local models is used.",
    )
    args = parser.parse_args()

    benchmarker = PhaseBenchmarker()

    if args.models:
        models_to_run = args.models
    else:
        all_models = benchmarker.get_local_models()
        # Filtro ampliado para detectar tus modelos de última generación
        families = ["ministral", "qwen", "llama", "mistral", "phi", "deepseek", "gemma", "gpt-oss"]
        # Excluir explícitamente modelos que sabemos que no son para chat de texto general
        exclude = ["image", "turbo", "ocr", "vl", "embedding"]
        
        models_to_run = [
            m for m in all_models 
            if any(f in m.lower() for f in families) and not any(e in m.lower() for e in exclude)
        ]
        
        if not models_to_run:
            models_to_run = all_models[:5]

    if not models_to_run:
        print("No models found to benchmark.")
        return

    print(f"Starting phase-specific benchmark for {len(models_to_run)} models: {', '.join(models_to_run)}")
    
    benchmarker.run_benchmark(models_to_run)
    benchmarker.save_results()
    benchmarker.print_recommendations()
    
    print("\n¿Qué perfil deseas aplicar a backend/config/llm_models.json?")
    print("  [1] POTENCIA   (Máxima calidad, ideal para dejarlo trabajando solo)")
    print("  [2] EQUILIBRIO (Buen balance calidad/velocidad)")
    print("  [3] VELOCIDAD  (Prototipado rápido)")
    print("  [n] Ninguno    (No realizar cambios)")
    
    choice = input("\nSelecciona una opción (1/2/3/n): ").strip().lower()
    
    if choice in ["1", "2", "3"]:
        benchmarker.apply_profile(choice)
    else:
        print("\nNo se han realizado cambios en la configuración.")
    
    print("\nBenchmark complete.")


if __name__ == "__main__":
    main()
