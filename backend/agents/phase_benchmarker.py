import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests

from backend.core.config import get_config
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.ollama_client import OllamaClient
from backend.utils.core.system.structured_logger import StructuredLogger
from backend.utils.core.llm.llm_recorder import LLMRecorder


class PhaseBenchmarker:
    """Benchmarks Ollama models on specific AutoAgent phases."""

    def __init__(self, tasks_file: str = "auto_benchmark_tasks_phases.json"):
        config = get_config(reload=True)
        self.url = config.OLLAMA_URL
        self.config = {
            **(config.TOOL_SETTINGS or {}),
            **(config.LLM_MODELS or {}),
        }

        log_file_path = Path("logs") / "phase_benchmark_debug.log"
        structured_logger = StructuredLogger(log_file_path=log_file_path, logger_name="PhaseBenchmarkLogger")
        self.logger = AgentLogger(structured_logger=structured_logger, logger_name="PhaseBenchmark")

        self.tasks_file = tasks_file
        self.test_tasks = self._load_tasks()
        self.results: List[dict] = []
        self._model_sizes: Dict[str, int] = {}

    def _load_tasks(self) -> list:
        file_path = Path("backend/config") / self.tasks_file
        if file_path.exists():
            with open(file_path, "r") as f:
                return json.load(f)
        return []

    def get_local_models(self) -> List[str]:
        try:
            response = requests.get(f"{self.url}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            return [m["name"] for m in models if "embed" not in m["name"].lower()]
        except Exception as e:
            print(f"Error connecting to Ollama: {e}")
            return []

    def run_benchmark(self, models_to_test: List[str]):
        total_models = len(models_to_test)
        total_tasks = len(self.test_tasks)

        for model_idx, model_name in enumerate(models_to_test, 1):
            print(f"\n[{model_idx}/{total_models}] Testing model: {model_name}")
            llm_recorder = LLMRecorder(logger=self.logger)
            client = OllamaClient(
                url=self.url,
                model=model_name,
                timeout=300,
                logger=self.logger,
                config=self.config,
                llm_recorder=llm_recorder,
            )

            model_results = []
            for task_idx, task in enumerate(self.test_tasks, 1):
                phase = task.get("phase", "General")
                name = task["name"]
                print(f"  ({task_idx}/{total_tasks}) [{phase}] {name}...", end="", flush=True)

                start_time = time.time()
                try:
                    prompt = self._build_prompt(task)
                    messages = [{"role": "user", "content": prompt}]

                    response, usage = client.chat(messages, tools=[])

                    elapsed = time.time() - start_time
                    content = response["message"]["content"]

                    # Basic automated scoring
                    score = self._evaluate_output(task, content)

                    model_results.append(
                        {
                            "task": name,
                            "phase": phase,
                            "score": score,
                            "duration": round(elapsed, 2),
                            "tokens": usage.get("total_tokens", 0),
                            "success": score > 0.5,
                        }
                    )
                    print(f" Done ({round(elapsed, 1)}s, Score: {score})")
                except Exception as e:
                    print(f" Failed: {e}")
                    model_results.append(
                        {"task": name, "phase": phase, "score": 0, "duration": 0, "success": False, "error": str(e)}
                    )

            # Aggregate results for this model
            phase_scores = {}
            for res in model_results:
                p = res["phase"]
                if p not in phase_scores:
                    phase_scores[p] = []
                phase_scores[p].append(res["score"])

            avg_phase_scores = {p: round(sum(s) / len(s), 2) for p, s in phase_scores.items()}

            self.results.append(
                {"model": model_name, "phase_scores": avg_phase_scores, "detailed_results": model_results}
            )

    def _build_prompt(self, task: dict) -> str:
        phase = task.get("phase")
        desc = task["description"]

        if phase == "ReadmeGenerationPhase":
            return f"Act as a technical writer. Generate a README.md based on this description: {desc}. Output only the README content."
        elif phase == "StructureGenerationPhase":
            return f"Act as a solution architect. Respond ONLY with a JSON object representing the file structure for: {desc}. Format: {{'path': './', 'folders': [{{'name': '...', 'folders': [], 'files': []}}], 'files': []}}"
        elif phase == "LogicPlanningPhase":
            return f"Act as an expert architect. Create a detailed JSON implementation plan for: {desc}. For each file, specify: purpose, exports, imports, main_logic (list), validation (list)."
        elif phase == "FileContentGenerationPhase":
            return f"Act as an expert developer. Generate COMPLETE, production-ready code for the file '{task.get('file_path', 'code.py')}' based on: {desc}. No TODOs, no placeholders."
        elif phase == "SeniorReviewPhase":
            return f"Act as a senior reviewer. Analyze this project and provide 3 criticisms and 3 recommendations: {task.get('input_summary', desc)}"
        else:
            return desc

    def _evaluate_output(self, task: dict, content: str) -> float:
        """Strict heuristic evaluation of the output quality."""
        if not content or len(content.strip()) < 100:
            return 0.0

        score = 0.2  # Base score for non-empty, minimum length output

        # 1. HARD PENALTIES (Laziness)
        placeholders = ["TODO", "...", "FIXME", "implementation goes here", "add your logic"]
        for p in placeholders:
            if p.lower() in content.lower():
                score -= 0.3

        # 2. PHASE-SPECIFIC RIGOR
        phase = task.get("phase")

        # README: check for markdown richness
        if phase == "ReadmeGenerationPhase":
            if content.count("#") >= 3:
                score += 0.2  # Good heading structure
            if "```" in content:
                score += 0.2  # Includes code examples
            if len(content) > 1000:
                score += 0.1  # Depth

        # Structure/Logic: JSON richness
        elif phase in ["StructureGenerationPhase", "LogicPlanningPhase"]:
            try:
                import re

                json_match = re.search(r"\{[\s\S]*\}", content)
                if json_match:
                    data = json.loads(json_match.group())
                    score += 0.2  # It's valid JSON

                    if phase == "LogicPlanningPhase":
                        # Check if it actually planned multiple files and has depth
                        if len(data) >= 2:
                            score += 0.2
                        # Check for mandatory fields in the first item
                        first_item = list(data.values())[0]
                        if isinstance(first_item, dict):
                            required = ["purpose", "exports", "main_logic"]
                            if all(k in first_item for k in required):
                                score += 0.2
                    else:  # Structure
                        if len(data.get("folders", [])) + len(data.get("files", [])) > 3:
                            score += 0.2
                else:
                    score -= 0.4
            except:
                score -= 0.5

        # Code content: completeness
        elif phase == "FileContentGenerationPhase":
            if any(x in content for x in ["def ", "class ", "import ", "function ", "const "]):
                score += 0.3
            if '"""' in content or "/*" in content or "//" in content:
                score += 0.2  # Documented
            if len(content) > 500:
                score += 0.1  # Non-trivial

        # 3. TASK-SPECIFIC KEYWORDS
        expected_sections = task.get("expected_sections", [])
        if expected_sections:
            found = sum(1 for s in expected_sections if s.lower() in content.lower())
            score += (found / len(expected_sections)) * 0.2

        expected_folders = task.get("expected_folders", [])
        if expected_folders:
            found = sum(1 for f in expected_folders if f.lower() in content.lower())
            score += (found / len(expected_folders)) * 0.2

        return min(max(round(score, 2), 0.0), 1.0)

    def save_results(self):
        """Save benchmark results to a timestamped JSON file."""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        output_file = log_dir / f"phase_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\nResults saved to {output_file}")
        return output_file

    def print_recommendations(self):
        """Analyze results and print recommendations by profiles."""
        if not self.results:
            print("No results to analyze.")
            return

        print("\n" + "=" * 70)
        print("   PHASE BENCHMARK: MODEL PROFILES & RECOMMENDATIONS")
        print("=" * 70)

        self.phase_data = {}  # Store for application

        for model_res in self.results:
            model_name = model_res["model"]
            for res in model_res["detailed_results"]:
                p = res["phase"]
                if p not in self.phase_data:
                    self.phase_data[p] = []
                self.phase_data[p].append(
                    {
                        "model": model_name,
                        "score": res["score"],
                        "duration": res["duration"],
                        "tps": res["tokens"] / res["duration"] if res["duration"] > 0 else 0,
                    }
                )

        self.profiles = {"1": "POTENCIA", "2": "EQUILIBRIO", "3": "VELOCIDAD"}
        self.winners_by_profile = {"POTENCIA": {}, "EQUILIBRIO": {}, "VELOCIDAD": {}}

        for phase in sorted(self.phase_data.keys()):
            models = self.phase_data[phase]
            print(f"\n--- PHASE: {phase} ---")

            beast = max(models, key=lambda x: x["score"])
            fast_models = [m for m in models if m["score"] >= 0.4]
            flash = max(fast_models, key=lambda x: x["tps"]) if fast_models else beast
            balanced = max(models, key=lambda x: x["score"] * 0.7 + (x["tps"] / 100) * 0.3)

            self.winners_by_profile["POTENCIA"][phase] = beast["model"]
            self.winners_by_profile["EQUILIBRIO"][phase] = balanced["model"]
            self.winners_by_profile["VELOCIDAD"][phase] = flash["model"]

            print(f"  [1] POTENCIA   Winner: {beast['model']:.<30} Score: {beast['score']:.2f}")
            print(f"  [2] EQUILIBRIO Winner: {balanced['model']:.<30} Score: {balanced['score']:.2f}")
            print(f"  [3] VELOCIDAD  Winner: {flash['model']:.<30} TPS: {flash['tps']:.1f}")

        print("\n" + "=" * 70)

    def apply_profile(self, profile_key: str):
        """Update backend/config/llm_models.json with the winners of a profile."""
        profile_name = self.profiles.get(profile_key)
        if not profile_name:
            print("Invalid profile selection.")
            return

        config_path = Path("backend/config/llm_models.json")
        if not config_path.exists():
            print(f"Error: {config_path} not found.")
            return

        with open(config_path, "r") as f:
            config_data = json.load(f)

        winners = self.winners_by_profile[profile_name]

        # Map phases to roles in config
        role_map = {
            "ReadmeGenerationPhase": "writer",
            "StructureGenerationPhase": "prototyper",
            "LogicPlanningPhase": "planner",
            "FileContentGenerationPhase": "coder",
            "SeniorReviewPhase": "senior_reviewer",
        }

        print(f"\nApplying profile [{profile_name}] to {config_path}...")
        for phase, model in winners.items():
            role = role_map.get(phase)
            if role and "agent_roles" in config_data:
                old_model = config_data["agent_roles"].get(role)
                config_data["agent_roles"][role] = model
                print(f"  - Role '{role}': {old_model} -> {model}")

        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=4)

        print("\nConfig updated successfully! You can now run 'python run_web.py'.")
