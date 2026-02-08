import json
import os
import time
import threading
import requests
from pathlib import Path
from datetime import datetime
from src.utils.core.ollama_client import OllamaClient
from src.utils.core.token_tracker import TokenTracker
from src.utils.core.agent_logger import AgentLogger

class _Heartbeat:
    """Background thread that prints elapsed time periodically while waiting for a slow model response."""
    def __init__(self, model_name, task_label, interval=30):
        self.model_name = model_name
        self.task_label = task_label
        self.interval = interval
        self._stop = threading.Event()
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.wait(self.interval):
            elapsed = int(time.time() - self._start_time)
            mins, secs = divmod(elapsed, 60)
            print(f"    ⏳ {self.model_name} | {self.task_label} — {mins}m {secs}s transcurridos...", flush=True)

    def start(self):
        self._start_time = time.time()
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)


class ModelBenchmarker:
    def __init__(self, config_path="config/settings.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        
        self.url = os.environ.get("OLLAMA_HOST", self.config.get("ollama_url", "http://localhost:11434"))
        self.logger = AgentLogger(log_file=str(Path("logs") / "benchmark_debug.log"))
        self.results = []

        # Load test tasks from a separate configuration file
        benchmark_tasks_path = Path("config/benchmark_tasks.json")
        if not benchmark_tasks_path.exists():
            raise FileNotFoundError(f"Benchmark tasks file not found: {benchmark_tasks_path}")
        with open(benchmark_tasks_path, "r", encoding="utf-8") as f:
            self.test_tasks = json.load(f)

        # Define thematic categories and their mapping to task types
        self.thematic_categories = {
            "Inteligencia de Seguridad": ["security_sandbox"],
            "Capacidad de Coding": ["code_generation", "code_analysis", "tool_integration", "technical_content_generation", "architecture_design"],
            "Fiabilidad Autónoma": ["reasoning", "reasoning_architecture", "logic_edge_cases", "autonomous_flow"]
        }

    def get_local_models(self):
        """Obtiene la lista de modelos locales ordenados por tamaño (menor a mayor)."""
        try:
            response = requests.get(f"{self.url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            # Sort by size ascending (smallest first)
            models_sorted = sorted(models, key=lambda m: m.get("size", 0))
            # Store size mapping for display later
            self._model_sizes = {m["name"]: m.get("size", 0) for m in models_sorted}
            return [m["name"] for m in models_sorted]
        except Exception as e:
            print(f"Error conectando a Ollama: {e}")
            return []

    def _format_size(self, size_bytes):
        """Convierte bytes a formato legible (GB/MB)."""
        if size_bytes >= 1_073_741_824:
            return f"{size_bytes / 1_073_741_824:.1f} GB"
        elif size_bytes >= 1_048_576:
            return f"{size_bytes / 1_048_576:.0f} MB"
        return f"{size_bytes} B"

    def _compute_model_options(self, size_bytes):
        """
        Calcula opciones de Ollama adaptativas según el tamaño del modelo.

        Modelos grandes consumen más VRAM por token de contexto, así que
        reducimos num_ctx y num_predict para que quepan y respondan rápido.
        Modelos pequeños pueden permitirse ventanas más amplias.

        Returns: (ollama_options_dict, timeout_seconds, tier_label)
        """
        gb = size_bytes / 1_073_741_824

        if gb < 10:
            # Small (ej. 8b quantized ~4-5 GB)
            tier = "small"
            opts = {"num_ctx": 4096, "num_predict": 2048, "temperature": 0.1, "keep_alive": "0s"}
            timeout = 300
        elif gb < 30:
            # Medium (ej. 14b, 20b ~8-18 GB)
            tier = "medium"
            opts = {"num_ctx": 2048, "num_predict": 1024, "temperature": 0.1, "keep_alive": "0s"}
            timeout = 480
        elif gb < 70:
            # Large (ej. 30b, 32b ~18-42 GB)
            tier = "large"
            opts = {"num_ctx": 1024, "num_predict": 512, "temperature": 0.1, "keep_alive": "0s"}
            timeout = 600
        else:
            # XLarge (ej. 120b ~68+ GB)
            tier = "xlarge"
            opts = {"num_ctx": 512, "num_predict": 256, "temperature": 0.1, "keep_alive": "0s"}
            timeout = 900

        return opts, timeout, tier

    def run_benchmark(self, models_to_test):
        total_models = len(models_to_test)
        total_tasks = len(self.test_tasks)

        for model_idx, model_name in enumerate(models_to_test, 1):
            model_size = getattr(self, '_model_sizes', {}).get(model_name, 0)
            model_options, model_timeout, size_tier = self._compute_model_options(model_size)
            size_str = f" ({self._format_size(model_size)})" if model_size else ""
            print(f"\n{'='*60}")
            print(f"🚀 [{model_idx}/{total_models}] Probando modelo: {model_name}{size_str}")
            print(f"   Tier: {size_tier} | num_ctx: {model_options['num_ctx']} | num_predict: {model_options['num_predict']} | timeout: {model_timeout}s")
            print(f"{'='*60}", flush=True)
            tracker = TokenTracker()
            client = OllamaClient(
                url=self.url,
                model=model_name,
                timeout=model_timeout,
                logger=self.logger,
                config=self.config
            )

            model_start_time = time.time()
            model_overall_status = "Success"
            outputs = []

            for task_idx, task_data in enumerate(self.test_tasks, 1): # Iterate over task dictionaries
                task_content = task_data["task"]
                task_type = task_data["type"] # Extract task type
                task_difficulty = task_data.get("difficulty", "unknown")
                difficulty_icons = {"basic": "🟢", "intermediate": "🟡", "advanced": "🟠", "extreme": "🔴"}
                diff_icon = difficulty_icons.get(task_difficulty, "⚪")
                task_label = f"Tarea {task_idx}/{total_tasks} {diff_icon} {task_difficulty} ({task_type})"
                task_status = "Success"
                task_response_content = ""
                task_tokens_prompt = 0
                task_tokens_completion = 0

                print(f"  ▶ {task_label}...", flush=True)
                task_start = time.time()
                heartbeat = _Heartbeat(model_name, task_label)
                heartbeat.start()

                try:
                    messages = [{"role": "user", "content": task_content}] # Use task_content
                    # Se envían sin herramientas para probar razonamiento puro y evitar daños
                    response, usage = client.chat(messages, tools=[], options_override=model_options)

                    task_tokens_prompt = usage.get("prompt_tokens", 0)
                    task_tokens_completion = usage.get("completion_tokens", 0)

                    tracker.add_usage(task_tokens_prompt, task_tokens_completion)
                    task_response_content = response["message"]["content"]

                except Exception as e:
                    task_status = f"Failed: {str(e)}"
                    model_overall_status = "Failed (some tasks failed)" # Update overall model status
                    self.logger.error(f"Error en tarea para modelo {model_name} (Tipo: {task_type}): {e}") # Log task type
                finally:
                    heartbeat.stop()

                task_elapsed = time.time() - task_start
                task_mins, task_secs = divmod(int(task_elapsed), 60)
                status_icon = "✅" if task_status == "Success" else "❌"
                print(f"  {status_icon} {task_label} — {task_mins}m {task_secs}s | tokens: {task_tokens_prompt}+{task_tokens_completion}", flush=True)

                outputs.append({
                    "task": task_content,
                    "type": task_type, # Include task type in results
                    "status": task_status,
                    "response": task_response_content,
                    "tokens_prompt": task_tokens_prompt,
                    "tokens_completion": task_tokens_completion
                })
            
            model_duration = time.time() - model_start_time
            model_mins, model_secs = divmod(int(model_duration), 60)
            successful_tasks = sum(1 for o in outputs if o["status"] == "Success")
            print(f"\n  📊 Modelo {model_name} completado: {successful_tasks}/{total_tasks} tareas OK en {model_mins}m {model_secs}s", flush=True)

            # Calculate thematic scores
            thematic_scores = {theme: {"score": 0, "tasks_count": 0} for theme in self.thematic_categories}
            
            for output in outputs:
                for theme, task_types in self.thematic_categories.items():
                    if output["type"] in task_types:
                        thematic_scores[theme]["tasks_count"] += 1
                        if output["status"] == "Success":
                            thematic_scores[theme]["score"] += 1
            
            # Convert sums to averages
            final_thematic_scores = {}
            for theme, data in thematic_scores.items():
                if data["tasks_count"] > 0:
                    final_thematic_scores[theme] = round(data["score"] / data["tasks_count"], 2)
                else:
                    final_thematic_scores[theme] = 0.0 # No tasks for this theme

            tokens_generated = tracker.session_total_tokens
            tokens_per_second = round(tokens_generated / model_duration, 2) if model_duration > 0 else 0.0

            self.results.append({
                "model": model_name,
                "model_size_bytes": model_size,
                "model_size_human": self._format_size(model_size) if model_size else "unknown",
                "size_tier": size_tier,
                "options_used": {
                    "num_ctx": model_options["num_ctx"],
                    "num_predict": model_options["num_predict"],
                    "timeout": model_timeout
                },
                "overall_status": model_overall_status,
                "duration_sec": round(model_duration, 2),
                "tokens_per_second": tokens_per_second, # New Metascore
                "total_tokens_session": {
                    "prompt": tracker.session_prompt_tokens,
                    "completion": tracker.session_completion_tokens,
                    "total": tokens_generated
                },
                "thematic_scores": final_thematic_scores, # Added thematic scores
                "tasks_results": outputs
            })

    def generate_summary(self, summary_model):
        """Usa el modelo designado para crear el informe final."""
        summary_timeout = self.config.get("timeout", 300)
        summary_client = OllamaClient(url=self.url, model=summary_model, timeout=summary_timeout, logger=self.logger, config=self.config)
        
        report_data = json.dumps(self.results, indent=2)
        
        # Enhanced prompt to include thematic scores
        prompt = f"""Based on the following benchmark data, generate an executive summary comparing the performance, speed, token efficiency, and thematic scores (Inteligencia de Seguridad, Capacidad de Coding, Fiabilidad Autónoma) of each model.

Benchmark Data:
{report_data}

Provide insights into which models excel in specific thematic areas and overall.
"""
        try:
            response, _ = summary_client.chat([{"role": "user", "content": prompt}], tools=[])
            return response["message"]["content"]
        except Exception as e:
            self.logger.error(f"Error generating summary: {e}")
            return "No se pudo generar el resumen automático."

    def save_logs(self):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True) # Ensure the logs directory exists
        output_file = log_dir / f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2)
        return output_file

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run benchmarks on Ollama models.")
    parser.add_argument("--models", nargs='*', help="List of model names to benchmark. If not provided, all local models will be benchmarked.")
    args = parser.parse_args()

    benchmarker = ModelBenchmarker()
    
    models_to_run = []
    if args.models:
        models_to_run = args.models
        print(f"Benchmarking specific models: {', '.join(models_to_run)}")
    else:
        all_local_models = benchmarker.get_local_models()
        if not all_local_models:
            print("No local Ollama models found to benchmark. Please pull some models first (e.g., 'ollama pull llama2').")
            exit(1)
        models_to_run = all_local_models
        print(f"\nModelos ordenados por tamaño (menor a mayor):")
        print(f"  {'#':<4} {'Modelo':<35} {'Tamaño':>8}  {'Tier':<7} {'ctx':>5} {'pred':>5} {'tout':>5}")
        print(f"  {'─'*4} {'─'*35} {'─'*8}  {'─'*7} {'─'*5} {'─'*5} {'─'*5}")
        for i, name in enumerate(models_to_run, 1):
            size = benchmarker._model_sizes.get(name, 0)
            opts, tout, tier = benchmarker._compute_model_options(size)
            print(f"  {i:<4} {name:<35} {benchmarker._format_size(size):>8}  {tier:<7} {opts['num_ctx']:>5} {opts['num_predict']:>5} {tout:>5}s")
        print(f"\n  Total: {len(models_to_run)} modelos, {len(benchmarker.test_tasks)} tareas por modelo")

    if models_to_run:
        benchmarker.run_benchmark(models_to_run)
        log_path = benchmarker.save_logs()
        
        summary_model = benchmarker.config.get("summary_model", "ministral-3:8b") # Get summary model from config
        print(f"\nGenerando resumen con el modelo: {summary_model}")
        final_report = benchmarker.generate_summary(summary_model)
        
        print("\n" + "="*50)
        print("REPORTE FINAL DE BENCHMARK")
        print("="*50)
        print(final_report)
        print(f"\nDetalles guardados en: {log_path}")
    else:
        print("No models selected for benchmarking.")