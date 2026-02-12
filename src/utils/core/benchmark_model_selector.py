"""Automatic model selection based on benchmark results.

This module reads benchmark data and dynamically reconfigures CoreAgent's
model assignments based on empirically measured performance.

Design: Decoupled from CoreAgent; pulls results from auto_benchmark.py.
Benefit: Self-tuning configuration without manual settings.json edits.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from statistics import mean, median

from src.utils.core.agent_logger import AgentLogger


@dataclass
class ModelBenchmarkResult:
    """Stores a benchmark result for a model on a specific task."""

    model_name: str
    task_type: str  # "refinement", "coder", "planner", "generalist", etc.
    success_rate: float  # 0.0 to 1.0
    avg_tokens: float
    avg_time_ms: float
    quality_score: float  # 1-10
    timestamp: Optional[str] = None


class BenchmarkDatabase:
    """Manages reading and querying benchmark results."""

    def __init__(self, benchmark_dir: Path, logger: AgentLogger):
        self.benchmark_dir = benchmark_dir
        self.logger = logger
        self.results: List[ModelBenchmarkResult] = []
        self._load_results()

    def _load_results(self):
        """Load all benchmark results from the benchmark directory."""
        if not self.benchmark_dir.exists():
            self.logger.warning(f"Benchmark directory not found: {self.benchmark_dir}")
            return

        for result_file in self.benchmark_dir.glob("*.json"):
            try:
                with open(result_file) as f:
                    data = json.load(f)
                    result = ModelBenchmarkResult(
                        model_name=data["model_name"],
                        task_type=data["task_type"],
                        success_rate=data["success_rate"],
                        avg_tokens=data["avg_tokens"],
                        avg_time_ms=data["avg_time_ms"],
                        quality_score=data["quality_score"],
                        timestamp=data["timestamp"],
                    )
                    self.results.append(result)
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.warning(f"Failed to load benchmark result {result_file}: {e}")

    def get_best_model(
        self,
        task_type: str,
        metric: str = "success_rate",
    ) -> Optional[ModelBenchmarkResult]: # Changed return type hint
        """Get the best-performing model for a task.
        
        Args:
            task_type: Task category (refinement, coder, planner, etc.)
            metric: Ranking metric (success_rate, quality_score, avg_time_ms) # Updated metric comment
            
        Returns:
            Best model name or None if no data available
        """
        relevant_results = [r for r in self.results if r.task_type == task_type]
        if not relevant_results:
            return None

        if metric == "success_rate":
            best = max(relevant_results, key=lambda r: r.success_rate)
        elif metric == "quality_score":
            best = max(relevant_results, key=lambda r: r.quality_score)
        elif metric == "avg_time_ms": # Changed to avg_time_ms
            best = min(relevant_results, key=lambda r: r.avg_time_ms) # Changed to avg_time_ms
        else:
            return None

        return best # Return the full object

    def get_model_rank(self, task_type: str) -> List[Tuple[str, float]]:
        """Get all models ranked by success rate for a task."""
        relevant = [r for r in self.results if r.task_type == task_type]
        grouped = {}
        for r in relevant:
            if r.model_name not in grouped:
                grouped[r.model_name] = []
            grouped[r.model_name].append(r.success_rate)

        # Average success rate per model
        model_scores = {
            model: mean(scores) for model, scores in grouped.items()
        }
        
        return sorted(model_scores.items(), key=lambda x: x[1], reverse=True)

    def get_stats_for_model(self, model_name: str, task_type: str) -> Optional[Dict]:
        """Get aggregated statistics for a model on a task."""
        relevant = [
            r for r in self.results
            if r.model_name == model_name and r.task_type == task_type
        ]
        
        if not relevant:
            return None

        return {
            "model": model_name,
            "task": task_type,
            "samples": len(relevant),
            "avg_success_rate": mean(r.success_rate for r in relevant),
            "median_quality": median(r.quality_score for r in relevant),
            "avg_time_ms": mean(r.avg_time_ms for r in relevant),
            "avg_tokens": mean(r.avg_tokens for r in relevant),
        }


class AutoModelSelector:
    """Automatically selects model assignments based on benchmark data."""

    # Task type to model role mapping
    TASK_TO_ROLE = {
        "refinement": "coder",
        "coder": "coder",
        "planner": "planner",
        "prototyper": "prototyper",
        "generalist": "generalist",
        "suggester": "suggester",
        "improvement_planner": "improvement_planner",
        "test_generator": "test_generator",
        "senior_reviewer": "senior_reviewer",
        "orchestration": "orchestration",
        "self_correction": "self_correction",
    }

    def __init__(
        self,
        benchmark_dir: Path,
        logger: AgentLogger,
        confidence_threshold: float = 0.7,
    ):
        self.logger = logger
        self.benchmark_db = BenchmarkDatabase(benchmark_dir, logger)
        self.confidence_threshold = confidence_threshold

    def generate_optimized_config(
        self,
        base_config: Dict,
    ) -> Dict:
        """Generate optimized model configuration based on benchmarks.
        
        Args:
            base_config: Base configuration from settings.json
            
        Returns:
            Updated config with optimized model assignments
        """
        optimized = base_config.copy()
        models_section = optimized.get("models", {})

        self.logger.info("🧪 Optimizing model assignments based on benchmarks...")

        for task_type, role in self.TASK_TO_ROLE.items():
            best_model = self.benchmark_db.get_best_model(
                task_type=task_type,
                metric="success_rate",
            )

            if best_model:
                # Get statistics to ensure confidence
                stats = self.benchmark_db.get_stats_for_model(best_model, task_type)
                if stats and stats["avg_success_rate"] >= self.confidence_threshold:
                    old_model = models_section.get(role, "unknown")
                    models_section[role] = best_model
                    
                    success_pct = stats["avg_success_rate"] * 100
                    self.logger.info(
                        f"  📊 {role}: {old_model} → {best_model} "
                        f"({success_pct:.1f}% success rate)"
                    )

        optimized["models"] = models_section
        optimized["benchmark_optimized"] = True
        optimized["optimization_timestamp"] = __import__("datetime").datetime.now().isoformat()

        return optimized

    def suggest_model_improvements(self) -> List[Dict]:
        """Suggest model improvements based on benchmark data.
        
        Returns:
            List of improvement suggestions
        """
        suggestions = []

        for task_type, role in self.TASK_TO_ROLE.items():
            ranking = self.benchmark_db.get_model_rank(task_type)
            
            if len(ranking) >= 2:
                best, best_score = ranking[0]
                second, second_score = ranking[1] if len(ranking) > 1 else (None, 0)
                
                improvement_margin = (best_score - second_score) * 100 if second else 0
                
                if improvement_margin > 10:  # >10% improvement
                    suggestions.append({
                        "role": role,
                        "current_recommendation": best,
                        "alternative": second,
                        "improvement_percent": improvement_margin,
                        "confidence": best_score,
                    })

        return suggestions

    def save_optimized_config(
        self,
        optimized_config: Dict,
        output_path: Path,
    ):
        """Save optimized configuration to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(optimized_config, f, indent=2)
        self.logger.info(f"✅ Saved optimized config to {output_path}")


def integrate_benchmark_results(
    settings_path: Path,
    benchmark_dir: Path,
    logger: AgentLogger,
    dry_run: bool = True,
) -> Dict:
    """High-level function to integrate benchmark results into configuration.
    
    Args:
        settings_path: Path to settings.json
        benchmark_dir: Directory containing benchmark results
        logger: Logger instance
        dry_run: If True, don't save; just return optimized config
        
    Returns:
        Optimized configuration
    """
    # Load base config
    with open(settings_path) as f:
        base_config = json.load(f)

    # Generate optimized config
    selector = AutoModelSelector(benchmark_dir, logger)
    optimized_config = selector.generate_optimized_config(base_config)

    # Log suggestions
    suggestions = selector.suggest_model_improvements()
    if suggestions:
        logger.info(f"💡 {len(suggestions)} improvement suggestions available:")
        for sugg in suggestions:
            logger.info(
                f"    - {sugg['role']}: {sugg['current_recommendation']} "
                f"(+{sugg['improvement_percent']:.1f}% vs {sugg['alternative']})"
            )

    # Save if not dry run
    if not dry_run:
        selector.save_optimized_config(
            optimized_config,
            settings_path.parent / "settings_optimized.json",
        )

    return optimized_config
