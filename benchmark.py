import json
import time
import requests
from pathlib import Path
from datetime import datetime
from src.utils.core.ollama_client import OllamaClient
from src.utils.core.token_tracker import TokenTracker
from src.utils.core.agent_logger import AgentLogger

class ModelBenchmarker:
    def __init__(self, config_path="config/settings.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        
        self.url = self.config.get("ollama_url", "http://localhost:11434") # Use Ollama URL from config
        self.logger = AgentLogger(log_file="benchmark_debug.log")
        self.results = []

        # Load test tasks from a separate configuration file
        benchmark_tasks_path = Path("config/benchmark_tasks.json")
        if not benchmark_tasks_path.exists():
            raise FileNotFoundError(f"Benchmark tasks file not found: {benchmark_tasks_path}")
        with open(benchmark_tasks_path, "r", encoding="utf-8") as f:
            self.test_tasks = json.load(f)

    def get_local_models(self):
        """Obtiene la lista de todos los modelos disponibles en el Ollama local."""
        try:
            response = requests.get(f"{self.url}/api/tags")
            response.raise_for_status()
            return [m["name"] for m in response.json().get("models", [])]
        except Exception as e:
            print(f"Error conectando a Ollama: {e}")
            return []

    def run_benchmark(self, models_to_test):
        for model_name in models_to_test:
            print(f"\n🚀 Probando modelo: {model_name}")
            tracker = TokenTracker()
            client = OllamaClient(
                url=self.url, 
                model=model_name, 
                timeout=600, # Timeout largo para modelos pesados
                logger=self.logger, 
                config=self.config
            )
            
            model_start_time = time.time()
            model_overall_status = "Success"
            outputs = []

            for task in self.test_tasks: # Use self.test_tasks
                task_status = "Success"
                task_response_content = ""
                task_tokens_prompt = 0
                task_tokens_completion = 0
                
                try:
                    messages = [{"role": "user", "content": task}]
                    # Se envían sin herramientas para probar razonamiento puro y evitar daños
                    response, usage = client.chat(messages, tools=[])
                    
                    task_tokens_prompt = usage.get("prompt_tokens", 0)
                    task_tokens_completion = usage.get("completion_tokens", 0)

                    tracker.add_usage(task_tokens_prompt, task_tokens_completion)
                    task_response_content = response["message"]["content"]
                    
                except Exception as e:
                    task_status = f"Failed: {str(e)}"
                    model_overall_status = "Failed (some tasks failed)" # Update overall model status
                    self.logger.error(f"Error en tarea para modelo {model_name}: {e}")
                
                outputs.append({
                    "task": task,
                    "status": task_status,
                    "response": task_response_content,
                    "tokens_prompt": task_tokens_prompt,
                    "tokens_completion": task_tokens_completion
                })
            
            model_duration = time.time() - model_start_time
            
            self.results.append({
                "model": model_name,
                "overall_status": model_overall_status,
                "duration_sec": round(model_duration, 2),
                "total_tokens_session": {
                    "prompt": tracker.session_prompt_tokens,
                    "completion": tracker.session_completion_tokens,
                    "total": tracker.session_total_tokens
                },
                "tasks_results": outputs
            })

    def generate_summary(self, summary_model):
        """Usa el modelo designado para crear el informe final."""
        summary_client = OllamaClient(url=self.url, model=summary_model, timeout=300, logger=self.logger, config=self.config)
        
        report_data = json.dumps(self.results, indent=2)
        prompt = f"Basado en los siguientes datos de benchmark, genera un resumen ejecutivo comparando el rendimiento, velocidad y eficiencia de tokens de cada modelo:\n\n{report_data}"
        
        try:
            response, _ = summary_client.chat([{"role": "user", "content": prompt}], tools=[])
            return response["message"]["content"]
        except:
            return "No se pudo generar el resumen automático."

    def save_logs(self):
        output_file = f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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
        print(f"Benchmarking all local models: {', '.join(models_to_run)}")

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