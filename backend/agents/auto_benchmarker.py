import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests

# Use the new centralized config
from backend.core.config import get_config
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.benchmark_rubrics import MultidimensionalRubric, RubricEvaluator
from backend.utils.core.file_validator import FileValidator
from backend.utils.core.heartbeat import Heartbeat
from backend.utils.core.llm_recorder import LLMRecorder
from backend.utils.core.llm_response_parser import LLMResponseParser
from backend.utils.core.ollama_client import OllamaClient
from backend.utils.core.structured_logger import StructuredLogger
from backend.utils.core.token_tracker import TokenTracker


class ModelBenchmarker:
    """Benchmarks Ollama models on autonomous project generation tasks."""

    SIZE_TIERS = [
        (
            10,
            "small",
            {
                "num_ctx": 4096,
                "num_predict": 2048,
                "temperature": 0.5,
                "keep_alive": "0s",
            },
            300,
        ),
        (
            30,
            "medium",
            {
                "num_ctx": 2048,
                "num_predict": 1024,
                "temperature": 0.5,
                "keep_alive": "0s",
            },
            480,
        ),
        (
            70,
            "large",
            {
                "num_ctx": 1024,
                "num_predict": 512,
                "temperature": 0.5,
                "keep_alive": "0s",
            },
            600,
        ),
        (
            float("inf"),
            "xlarge",
            {
                "num_ctx": 512,
                "num_predict": 256,
                "temperature": 0.5,
                "keep_alive": "0s",
            },
            900,
        ),
    ]

    def __init__(self):
        # Ensure config is fresh from disk
        config = get_config(reload=True)

        # Use the centralized configuration
        self.url = config.OLLAMA_URL

        # This config object is passed to OllamaClient, which expects a dictionary.
        self.config = {
            **(config.TOOL_SETTINGS or {}),
            **(config.LLM_MODELS or {}),
            **(config.AGENT_FEATURES or {}),
        }

        log_file_path = Path("logs") / "auto_benchmark_debug.log"
        structured_logger = StructuredLogger(log_file_path=log_file_path, logger_name="AutoBenchmarkLogger")
        self.logger = AgentLogger(structured_logger=structured_logger, logger_name="AutoBenchmark")
        self.response_parser = LLMResponseParser()
        self.file_validator = FileValidator(logger=self.logger)
        self.results: List[dict] = []
        self._model_sizes: Dict[str, int] = {}

        embedding_model_name = config.LLM_MODELS.get("models", {}).get("embedding", "all-minilm:latest")
        self.embedding_models = [embedding_model_name]

        self.test_tasks = self._load_tasks()
        self.rubric_evaluator = RubricEvaluator(logger=self.logger)

        self.thematic_categories = {
            "Generacion_Aplicaciones": [
                "web_app",
                "cli_tool",
                "game_simple",
                "data_script",
                "utility_tool",
            ],
            "Coherencia_Logica": ["logic_flow", "error_handling"],
            "Calidad_Codigo": ["code_structure", "readability", "functionality"],
        }
        self.generated_projects_dir = Path("generated_projects") / "auto_benchmark_projects"
        self.generated_projects_dir.mkdir(parents=True, exist_ok=True)

    def _load_tasks(self) -> list:
        """Load benchmark tasks from the central configuration."""
        tasks = get_config().AUTO_BENCHMARK_TASKS
        if not tasks:
            self.logger.warning("Auto benchmark tasks not found in config. Using empty list.")
            return []
        return tasks

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
        return (
            self.SIZE_TIERS[-1][2].copy(),
            self.SIZE_TIERS[-1][3],
            self.SIZE_TIERS[-1][1],
        )

    def run_benchmark(self, models_to_test: List[str]):
        """Run benchmark across all specified models and tasks."""
        # Filter out obvious embedding models that don't support chat
        models_to_test = [m for m in models_to_test if "embed" not in m.lower()]

        total_models = len(models_to_test)
        if total_models == 0:
            self.logger.warning("No suitable chat models found for benchmark.")
            return

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
            print(
                f"   Tier: {size_tier} | num_ctx: {model_options['num_ctx']} | "
                f"num_predict: {model_options['num_predict']} | timeout: {model_timeout}s"
            )
            print(f"{'=' * 60}", flush=True)

            tracker = TokenTracker()
            llm_recorder = LLMRecorder(logger=self.logger)
            client = OllamaClient(
                url=self.url,
                model=model_name,
                timeout=model_timeout,
                logger=self.logger,
                config=self.config,
                llm_recorder=llm_recorder,
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

                difficulty_icons = {
                    "basic": "[B]",
                    "intermediate": "[I]",
                    "advanced": "[A]",
                    "extreme": "[E]",
                }
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

                    # Rubric evaluation (multidimensional scoring)
                    try:
                        rubric_dimensions = MultidimensionalRubric.get_dimensions_for_task(task_type)
                        rubric_result = self.rubric_evaluator.evaluate(
                            model_name=model_name,
                            task_name=task_name,
                            response_content=task_response_content,
                            task_data=task_data,
                            duration_sec=time.time() - task_start,
                            dimensions=rubric_dimensions,
                        )
                    except Exception as rubric_err:
                        self.logger.warning(f"Rubric evaluation failed: {rubric_err}")
                        rubric_result = None

                    # Specialized validation for specific task types
                    try:
                        validation_type = task_data.get("validation")
                        validation_result = {}
                        if validation_type == "dependency_hallucination":
                            validation_result = self._validate_dependency_hallucination(task_response_content)
                        elif validation_type == "refactoring":
                            validation_result = self._validate_refactoring_quality(
                                task_response_content,
                                task_data.get("original_framework", ""),
                                task_data.get("target_framework", ""),
                            )
                    except Exception as val_err:
                        self.logger.warning(f"Validation failed: {val_err}")
                        validation_result = {}

                except Exception as e:
                    task_status = f"Failed: {str(e)}"
                    model_overall_status = "Failed (some tasks failed)"
                    self.logger.error(f"Error for model {model_name} ({task_name}): {e}")
                finally:
                    heartbeat.stop()

                task_elapsed = time.time() - task_start
                task_mins, task_secs = divmod(int(task_elapsed), 60)
                status_icon = "OK" if task_status == "Success" else "FAIL"
                print(
                    f"  [{status_icon}] {task_label} - {task_mins}m {task_secs}s | "
                    f"tokens: {task_tokens_prompt}+{task_tokens_completion}",
                    flush=True,
                )

                task_output = {
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
                }

                # Attach rubric scores if available
                if task_status == "Success" and rubric_result is not None:
                    task_output["rubric_scores"] = rubric_result.to_dict()

                # Attach validation results if available
                if task_status == "Success" and validation_result:
                    task_output["validation_result"] = validation_result

                outputs.append(task_output)

            # F13: Unload model from RAM after finishing all tasks for this model
            client.unload_model()

            model_duration = time.time() - model_start_time
            model_mins, model_secs = divmod(int(model_duration), 60)
            successful_tasks = sum(1 for o in outputs if o["status"] == "Success")
            print(
                f"\n  Model {model_name} done: {successful_tasks}/{total_tasks} OK in {model_mins}m {model_secs}s",
                flush=True,
            )

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

            # Aggregate rubric scores across all tasks for this model
            aggregated_rubric_scores = self._aggregate_rubric_scores(outputs)

            self.results.append(
                {
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
                    "rubric_scores": aggregated_rubric_scores,
                    "projects_results": outputs,
                }
            )

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

    # Special benchmark tasks for advanced evaluation
    SPECIAL_BENCHMARK_TASKS = [
        {
            "name": "flask_to_fastapi_refactor",
            "type": "critical_refactoring",
            "difficulty": "advanced",
            "description": (
                "Refactor the following Flask application to FastAPI, preserving all "
                "route logic, error handling, and middleware. The app has: "
                "GET /api/users, POST /api/users, GET /api/users/<id>, "
                "DELETE /api/users/<id>, with JWT auth middleware and SQLAlchemy ORM. "
                "Ensure all endpoints use async/await and Pydantic models for validation."
            ),
            "validation": "refactoring",
            "original_framework": "flask",
            "target_framework": "fastapi",
            "time_limit_minutes": 8,
        },
        {
            "name": "dependency_hallucination_check",
            "type": "dependency_verification",
            "difficulty": "intermediate",
            "description": (
                "Generate a complete requirements.txt for a Python ML pipeline that "
                "performs: image segmentation using U-Net, data augmentation with albumentations, "
                "experiment tracking with MLflow, distributed training with Horovod, "
                "and model serving with BentoML. Include exact version pins."
            ),
            "validation": "dependency_hallucination",
            "time_limit_minutes": 3,
        },
    ]

    # Well-known Python packages for hallucination detection
    KNOWN_PACKAGES = {
        "flask",
        "fastapi",
        "django",
        "requests",
        "numpy",
        "pandas",
        "scipy",
        "scikit-learn",
        "sklearn",
        "torch",
        "pytorch",
        "tensorflow",
        "keras",
        "transformers",
        "pytest",
        "black",
        "ruff",
        "mypy",
        "pydantic",
        "sqlalchemy",
        "alembic",
        "celery",
        "redis",
        "pillow",
        "pil",
        "matplotlib",
        "seaborn",
        "plotly",
        "uvicorn",
        "gunicorn",
        "jinja2",
        "click",
        "typer",
        "rich",
        "httpx",
        "aiohttp",
        "beautifulsoup4",
        "bs4",
        "lxml",
        "cryptography",
        "jwt",
        "pyjwt",
        "bcrypt",
        "passlib",
        "boto3",
        "botocore",
        "docker",
        "psycopg2",
        "pymongo",
        "motor",
        "elasticsearch",
        "mlflow",
        "albumentations",
        "bentoml",
        "horovod",
        "opencv-python",
        "cv2",
        "tqdm",
        "loguru",
        "structlog",
        "starlette",
        "werkzeug",
        "marshmallow",
        "attrs",
        "dataclasses",
        "typing-extensions",
        "python-dotenv",
        "toml",
        "pyyaml",
        "yaml",
        "orjson",
        "ujson",
        "onnx",
        "onnxruntime",
        "ray",
        "dask",
        "joblib",
        "multiprocessing",
        "asyncio",
        "aiofiles",
        "websockets",
        "grpcio",
        "protobuf",
        "pika",
        "kombu",
    }

    def _aggregate_rubric_scores(self, outputs: List[Dict]) -> Dict[str, Any]:
        """Aggregate rubric scores across all tasks for a model.

        Returns averaged scores per dimension and overall.
        """
        dimension_totals: Dict[str, List[float]] = {}

        for output in outputs:
            rubric = output.get("rubric_scores")
            if not rubric or "dimensions" not in rubric:
                continue
            for dim_name, dim_data in rubric["dimensions"].items():
                if dim_name not in dimension_totals:
                    dimension_totals[dim_name] = []
                dimension_totals[dim_name].append(dim_data.get("score", 0.0))

        aggregated = {}
        for dim_name, scores in dimension_totals.items():
            aggregated[dim_name] = round(sum(scores) / len(scores), 4) if scores else 0.0

        overall_scores = [s for scores in dimension_totals.values() for s in scores]
        aggregated["overall"] = round(sum(overall_scores) / len(overall_scores), 4) if overall_scores else 0.0

        return aggregated

    def _validate_dependency_hallucination(self, response_content: str) -> Dict[str, Any]:
        """Parse requirements from response and check for hallucinated packages.

        Extracts package names from requirements.txt-style content and
        verifies against a known-good package list.

        Returns:
            Dict with total_packages, verified_packages, hallucinated_packages,
            and hallucination_rate.
        """
        # Extract requirements.txt content from code blocks or inline
        req_pattern = re.compile(
            r"(?:```(?:text|txt|requirements)?\s*\n)(.*?)(?:```)",
            re.DOTALL,
        )
        req_blocks = req_pattern.findall(response_content)

        # Also try to find inline package==version patterns
        if not req_blocks:
            lines = response_content.split("\n")
            req_lines = [
                line.strip()
                for line in lines
                if re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*(?:\[.*\])?\s*[=<>!~]", line.strip())
            ]
            req_blocks = ["\n".join(req_lines)] if req_lines else []

        packages = []
        for block in req_blocks:
            for line in block.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                # Extract package name (before version specifier)
                match = re.match(r"^([a-zA-Z][a-zA-Z0-9_.-]*)", line)
                if match:
                    pkg_name = match.group(1).lower().replace("-", "_").replace(".", "_")
                    packages.append(pkg_name)

        if not packages:
            return {
                "total_packages": 0,
                "verified_packages": 0,
                "hallucinated_packages": [],
                "hallucination_rate": 0.0,
            }

        # Check against known packages
        known_normalized = {p.lower().replace("-", "_").replace(".", "_") for p in self.KNOWN_PACKAGES}
        verified = []
        hallucinated = []
        for pkg in packages:
            if pkg in known_normalized:
                verified.append(pkg)
            else:
                hallucinated.append(pkg)

        total = len(packages)
        return {
            "total_packages": total,
            "verified_packages": len(verified),
            "hallucinated_packages": hallucinated,
            "hallucination_rate": round(len(hallucinated) / total, 4) if total > 0 else 0.0,
        }

    def _validate_refactoring_quality(
        self, response_content: str, original_framework: str, target_framework: str
    ) -> Dict[str, Any]:
        """Validate quality of framework refactoring.

        Checks:
        1. Original framework imports removed
        2. Target framework imports added
        3. Route/endpoint preservation
        4. Overall refactoring score

        Returns:
            Dict with original_removed, target_added, route_preservation_ratio,
            and refactoring_score.
        """
        response_lower = response_content.lower()

        # Check framework import patterns
        framework_imports = {
            "flask": [r"from\s+flask\s+import", r"import\s+flask"],
            "fastapi": [r"from\s+fastapi\s+import", r"import\s+fastapi"],
            "django": [r"from\s+django", r"import\s+django"],
            "express": [r"require\(['\"]express['\"]\)", r"from\s+['\"]express['\"]"],
        }

        # Check if original framework references are removed
        original_patterns = framework_imports.get(original_framework, [])
        original_found = any(re.search(p, response_content, re.IGNORECASE) for p in original_patterns)
        original_removed = not original_found

        # Check if target framework is present
        target_patterns = framework_imports.get(target_framework, [])
        target_added = any(re.search(p, response_content, re.IGNORECASE) for p in target_patterns)

        # Count route definitions in both frameworks
        route_patterns = {
            "flask": [r"@app\.route\(", r"@bp\.route\(", r"@blueprint\.route\("],
            "fastapi": [r"@app\.(get|post|put|delete|patch)\(", r"@router\.(get|post|put|delete|patch)\("],
            "django": [r"path\(", r"url\("],
            "express": [r"app\.(get|post|put|delete|patch)\(", r"router\.(get|post|put|delete|patch)\("],
        }

        # Count target routes
        target_route_patterns = route_patterns.get(target_framework, [])
        target_route_count = sum(len(re.findall(p, response_content, re.IGNORECASE)) for p in target_route_patterns)

        # Estimate expected routes from description
        expected_routes = max(response_lower.count("endpoint"), 1)
        route_preservation = min(target_route_count / max(expected_routes, 1), 1.0)

        # Compute overall score
        score = 0.0
        if original_removed:
            score += 0.3
        if target_added:
            score += 0.3
        score += route_preservation * 0.4

        return {
            "original_removed": original_removed,
            "target_added": target_added,
            "target_route_count": target_route_count,
            "route_preservation_ratio": round(route_preservation, 4),
            "refactoring_score": round(score, 4),
        }

    def generate_summary(self, summary_model: str) -> str:
        """Use a designated model to create the final benchmark summary report."""
        summary_timeout = get_config().DEFAULT_TIMEOUT
        llm_recorder = LLMRecorder(logger=self.logger)
        summary_client = OllamaClient(
            url=self.url,
            model=summary_model,
            timeout=summary_timeout,
            logger=self.logger,
            config=self.config,
            llm_recorder=llm_recorder,
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
            print(
                f"  {i:<4} {name:<35} {self.format_size(size):>8}  {tier:<7} "
                f"{opts['num_ctx']:>5} {opts['num_predict']:>5} {tout:>5}s"
            )
        print(f"\n  Total: {len(models)} models, {len(self.test_tasks)} projects per model")
