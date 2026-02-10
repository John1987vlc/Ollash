import json
import os
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.token_tracker import TokenTracker
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.heartbeat import Heartbeat
from src.utils.core.llm_response_parser import LLMResponseParser
from src.utils.core.file_validator import FileValidator


class ModelBenchmarker:
    """Benchmarks Ollama models on autonomous project generation tasks."""

    DEFAULT_TASKS = [
        {
            "name": "Generar Aplicacion Web Simple",
            "description": "Crea una aplicacion web simple en Python (Flask o Django) que muestre un 'Hola Mundo' y una ruta `/info` que muestre la fecha y hora actual.",
            "type": "web_app",
            "difficulty": "basic",
            "time_limit_minutes": 5,
        },
        {
            "name": "Generar Herramienta CLI",
            "description": "Desarrolla una herramienta de linea de comandos en Python que tome una ruta de archivo como argumento y cuente el numero de lineas y palabras en ese archivo. Debe manejar errores si el archivo no existe.",
            "type": "cli_tool",
            "difficulty": "intermediate",
            "time_limit_minutes": 5,
        },
        {
            "name": "Generar Juego Simple",
            "description": "Crea un juego simple de 'Adivina el Numero' en Python. La computadora elige un numero aleatorio y el usuario tiene 5 intentos para adivinarlo, recibiendo pistas de 'mas alto' o 'mas bajo'.",
            "type": "game_simple",
            "difficulty": "intermediate",
            "time_limit_minutes": 5,
        },
        {
            "name": "Generar Script de Procesamiento de Datos",
            "description": "Escribe un script en Python que lea un archivo CSV con columnas 'nombre', 'edad', 'ciudad'. El script debe filtrar las personas mayores de 30 anos y guardar los resultados en un nuevo archivo CSV.",
            "type": "data_script",
            "difficulty": "intermediate",
            "time_limit_minutes": 5,
        },
        {
            "name": "Generar Herramienta de Utilidad de Archivos",
            "description": "Desarrolla una herramienta en Python que pueda listar todos los archivos en un directorio dado y sus tamanos en MB. Debe ser capaz de recibir la ruta del directorio como argumento de linea de comandos.",
            "type": "utility_tool",
            "difficulty": "basic",
            "time_limit_minutes": 5,
        },
    ]

    SIZE_TIERS = [
        (10, "small", {"num_ctx": 4096, "num_predict": 2048, "temperature": 0.5, "keep_alive": "0s"}, 300),
        (30, "medium", {"num_ctx": 2048, "num_predict": 1024, "temperature": 0.5, "keep_alive": "0s"}, 480),
        (70, "large", {"num_ctx": 1024, "num_predict": 512, "temperature": 0.5, "keep_alive": "0s"}, 600),
        (float("inf"), "xlarge", {"num_ctx": 512, "num_predict": 256, "temperature": 0.5, "keep_alive": "0s"}, 900),
    ]

    def __init__(self, config_path: str = "config/settings.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.url = os.environ.get(
            "OLLASH_OLLAMA_URL",
            os.environ.get("MOLTBOT_OLLAMA_URL",
            self.config.get("ollama_url", "http://localhost:11434")),
        )
        self.logger = AgentLogger(log_file=str(Path("logs") / "auto_benchmark_debug.log"))
        self.response_parser = LLMResponseParser()
        self.file_validator = FileValidator(logger=self.logger)
        self.results: List[dict] = []
        self._model_sizes: Dict[str, int] = {}

        self.test_tasks = self._load_tasks()

        self.thematic_categories = {
            "Generacion_Aplicaciones": ["web_app", "cli_tool", "game_simple", "data_script", "utility_tool"],
            "Coherencia_Logica": ["logic_flow", "error_handling"],
            "Calidad_Codigo": ["code_structure", "readability", "functionality"],
        }
        self.generated_projects_dir = Path("generated_projects")
        self.generated_projects_dir.mkdir(exist_ok=True)

    def _load_tasks(self) -> list:
        """Load benchmark tasks from config file or use defaults."""
        tasks_path = Path("config/auto_benchmark_tasks.json")
        if tasks_path.exists():
            with open(tasks_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # Create default tasks file
        with open(tasks_path, "w", encoding="utf-8") as f:
            json.dump(self.DEFAULT_TASKS, f, indent=2)
        print(f"Created default auto_benchmark_tasks.json at {tasks_path}")
        return list(self.DEFAULT_TASKS)

    def get_local_models(self) -> List[str]:
        """Get list of locally available Ollama models sorted by size (ascending)."""
        try:
            response = requests.get(f"{self.url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            models_sorted = sorted(models, key=lambda m: m.get("size", 0))
            self._model_sizes = {m["name"]: m.get("size", 0) for m in models_sorted}
            return [m["name"] for m in models_sorted]
        except Exception as e:
            print(f"Error connecting to Ollama: {e}")
            return []

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Convert bytes to human-readable format."""
        if size_bytes >= 1_073_741_824:
            return f"{size_bytes / 1_073_741_824:.1f} GB"
        elif size_bytes >= 1_048_576:
            return f"{size_bytes / 1_048_576:.0f} MB"
        return f"{size_bytes} B"

    def compute_model_options(self, size_bytes: int) -> tuple:
        """Compute adaptive Ollama options based on model size.

        Returns: (options_dict, timeout_seconds, tier_label)
        """
        gb = size_bytes / 1_073_741_824
        for max_gb, tier, opts, timeout in self.SIZE_TIERS:
            if gb < max_gb:
                return opts.copy(), timeout, tier
        # Fallback (should not reach here)
        return self.SIZE_TIERS[-1][2].copy(), self.SIZE_TIERS[-1][3], self.SIZE_TIERS[-1][1]

    def run_benchmark(self, models_to_test: List[str]):
        """Run benchmark across all specified models and tasks."""
        total_models = len(models_to_test)
        total_tasks = len(self.test_tasks)

        for model_idx, model_name in enumerate(models_to_test, 1):
            model_slug = model_name.replace(":", "_").replace("/", "__")
            model_project_dir = self.generated_projects_dir / model_slug
            model_project_dir.mkdir(exist_ok=True)

            model_size = self._model_sizes.get(model_name, 0)
            model_options, model_timeout, size_tier = self.compute_model_options(model_size)
            size_str = f" ({self.format_size(model_size)})" if model_size else ""

            print(f"{'=' * 60}")
            print(f"[{model_idx}/{total_models}] Testing model: {model_name}{size_str}")
            print(f"   Tier: {size_tier} | num_ctx: {model_options['num_ctx']} | "
                  f"num_predict: {model_options['num_predict']} | timeout: {model_timeout}s")
            print(f"{'=' * 60}", flush=True)

            tracker = TokenTracker()
            client = OllamaClient(
                url=self.url,
                model=model_name,
                timeout=model_timeout,
                logger=self.logger,
                config=self.config,
            )

            model_start_time = time.time()
            model_overall_status = "Success"
            outputs = []

            for task_idx, task_data in enumerate(self.test_tasks, 1):
                task_name = task_data["name"]
                task_description = task_data["description"]
                task_type = task_data["type"]
                task_difficulty = task_data.get("difficulty", "unknown")
                time_limit_minutes = task_data.get("time_limit_minutes", 5)

                difficulty_icons = {"basic": "[B]", "intermediate": "[I]", "advanced": "[A]", "extreme": "[E]"}
                diff_icon = difficulty_icons.get(task_difficulty, "[?]")
                task_label = f"Project {task_idx}/{total_tasks} {diff_icon} {task_difficulty} ({task_name})"
                task_status = "Success"
                task_response_content = ""
                task_tokens_prompt = 0
                task_tokens_completion = 0
                project_path = model_project_dir / f"project_{task_idx}_{task_type}"
                project_path.mkdir(exist_ok=True)

                print(f"  > {task_label} (Limit: {time_limit_minutes} min)...", flush=True)
                task_start = time.time()
                heartbeat = Heartbeat(model_name, task_label, logger=self.logger)
                heartbeat.start()

                try:
                    creation_prompt = (
                        "Please act as a senior software engineer. "
                        "Your task is to autonomously create a complete, functional project "
                        "based on the following description. "
                        "Provide all necessary files and instructions to run the project. "
                        "Keep the project self-contained and simple, focusing on core functionality. "
                        "Respond with the project's file structure and content directly. "
                        "Start with a high-level plan and then provide the files. "
                        f"Project description: {task_description}"
                    )
                    messages = [{"role": "user", "content": creation_prompt}]

                    current_task_timeout = time_limit_minutes * 60
                    options_with_timeout = model_options.copy()
                    options_with_timeout["timeout"] = current_task_timeout

                    response, usage = client.chat(messages, tools=[], options_override=options_with_timeout)

                    task_tokens_prompt = usage.get("prompt_tokens", 0)
                    task_tokens_completion = usage.get("completion_tokens", 0)
                    tracker.add_usage(task_tokens_prompt, task_tokens_completion)
                    task_response_content = response["message"]["content"]

                    self._save_generated_project(project_path, task_response_content, task_description)

                except Exception as e:
                    task_status = f"Failed: {str(e)}"
                    model_overall_status = "Failed (some tasks failed)"
                    self.logger.error(f"Error for model {model_name} ({task_name}): {e}")
                finally:
                    heartbeat.stop()

                task_elapsed = time.time() - task_start
                task_mins, task_secs = divmod(int(task_elapsed), 60)
                status_icon = "OK" if task_status == "Success" else "FAIL"
                print(f"  [{status_icon}] {task_label} - {task_mins}m {task_secs}s | "
                      f"tokens: {task_tokens_prompt}+{task_tokens_completion}", flush=True)

                outputs.append({
                    "task_name": task_name,
                    "task_description": task_description,
                    "type": task_type,
                    "status": task_status,
                    "response_preview": (
                        task_response_content[:500] + "..."
                        if len(task_response_content) > 500
                        else task_response_content
                    ),
                    "project_dir": str(project_path),
                    "tokens_prompt": task_tokens_prompt,
                    "tokens_completion": task_tokens_completion,
                    "duration_sec": round(task_elapsed, 2),
                })

            model_duration = time.time() - model_start_time
            model_mins, model_secs = divmod(int(model_duration), 60)
            successful_tasks = sum(1 for o in outputs if o["status"] == "Success")
            print(f"\n  Model {model_name} done: {successful_tasks}/{total_tasks} OK "
                  f"in {model_mins}m {model_secs}s", flush=True)

            # Calculate thematic scores
            thematic_scores = {theme: {"score": 0, "tasks_count": 0} for theme in self.thematic_categories}
            for output in outputs:
                for theme, task_types in self.thematic_categories.items():
                    if output["type"] in task_types:
                        thematic_scores[theme]["tasks_count"] += 1
                        if output["status"] == "Success":
                            thematic_scores[theme]["score"] += 1

            final_thematic = {}
            for theme, data in thematic_scores.items():
                if data["tasks_count"] > 0:
                    final_thematic[theme] = round(data["score"] / data["tasks_count"], 2)
                else:
                    final_thematic[theme] = 0.0

            tokens_generated = tracker.session_total_tokens
            tokens_per_second = round(tokens_generated / model_duration, 2) if model_duration > 0 else 0.0

            self.results.append({
                "model": model_name,
                "model_size_bytes": model_size,
                "model_size_human": self.format_size(model_size) if model_size else "unknown",
                "size_tier": size_tier,
                "options_used": {
                    "num_ctx": model_options["num_ctx"],
                    "num_predict": model_options["num_predict"],
                    "timeout_base": model_timeout,
                    "temperature": model_options["temperature"],
                },
                "overall_status": model_overall_status,
                "duration_sec": round(model_duration, 2),
                "tokens_per_second": tokens_per_second,
                "total_tokens_session": {
                    "prompt": tracker.session_prompt_tokens,
                    "completion": tracker.session_completion_tokens,
                    "total": tokens_generated,
                },
                "thematic_scores": final_thematic,
                "projects_results": outputs,
            })

    def _save_generated_project(self, project_dir: Path, model_response: str, task_description: str):
        """Parse model response and save as project files."""
        project_dir.mkdir(parents=True, exist_ok=True)

        # Always save the raw response and description
        (project_dir / "model_response.txt").write_text(model_response, encoding="utf-8")
        (project_dir / "task_description.txt").write_text(task_description, encoding="utf-8")

        # Extract and save individual files
        files = self.response_parser.extract_multiple_files(model_response)
        for rel_path, content in files.items():
            file_path = project_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                file_path.write_text(content.strip(), encoding="utf-8")
                self.logger.info(f"Saved file: {file_path}")
            except Exception as e:
                self.logger.error(f"Error saving {file_path}: {e}")

    def generate_summary(self, summary_model: str) -> str:
        """Use a designated model to create the final benchmark summary report."""
        summary_timeout = self.config.get("timeout", 300)
        summary_client = OllamaClient(
            url=self.url,
            model=summary_model,
            timeout=summary_timeout,
            logger=self.logger,
            config=self.config,
        )

        report_data = json.dumps(self.results, indent=2)
        prompt = (
            "Based on the following auto-benchmark data for autonomous project generation, "
            "generate an executive summary comparing the performance, speed, token efficiency, "
            "and thematic scores (Generacion_Aplicaciones, Coherencia_Logica, Calidad_Codigo) "
            "of each model.\n\n"
            f"Benchmark Data:\n{report_data}\n\n"
            "For each model, summarize the projects it attempted, noting successes and failures. "
            "Provide insights into which models excel in autonomous project generation."
        )
        try:
            response, _ = summary_client.chat([{"role": "user", "content": prompt}], tools=[])
            return response["message"]["content"]
        except Exception as e:
            self.logger.error(f"Error generating summary: {e}")
            return "Could not generate automatic summary."

    def save_logs(self) -> Path:
        """Save benchmark results to a timestamped JSON file."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        output_file = log_dir / f"auto_benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2)
        return output_file

    def print_model_table(self, models: List[str]):
        """Print a formatted table of models with their options."""
        print("\nModels sorted by size (ascending):")
        print(f"  {'#':<4} {'Model':<35} {'Size':>8}  {'Tier':<7} {'ctx':>5} {'pred':>5} {'tout':>5}")
        print(f"  {'-' * 4} {'-' * 35} {'-' * 8}  {'-' * 7} {'-' * 5} {'-' * 5} {'-' * 5}")
        for i, name in enumerate(models, 1):
            size = self._model_sizes.get(name, 0)
            opts, tout, tier = self.compute_model_options(size)
            print(f"  {i:<4} {name:<35} {self.format_size(size):>8}  {tier:<7} "
                  f"{opts['num_ctx']:>5} {opts['num_predict']:>5} {tout:>5}s")
        print(f"\n  Total: {len(models)} models, {len(self.test_tasks)} projects per model")
