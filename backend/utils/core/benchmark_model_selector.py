"""Automatic model selection based on benchmark results.

This module reads benchmark data and dynamically reconfigures CoreAgent's
model assignments based on empirically measured performance.

Design: Decoupled from CoreAgent; pulls results from auto_benchmark.py.
Benefit: Self-tuning configuration without manual settings.json edits.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional, Tuple

from backend.utils.core.agent_logger import AgentLogger


@dataclass
class ModelBenchmarkResult:
    """Stores a benchmark result for a model on a specific task."""

    model_name: str
    task_type: str  # "refinement", "coder", "planner", "generalist", etc.
    success_rate: float  # 0.0 to 1.0
    avg_tokens: float
    avg_time_ms: float
    quality_score: float  # 1-10

    # NEW: Metrics for advanced phase evaluation
    hallucination_ratio: float = 0.0  # LogicPlanningPhase: plan_vs_implementation mismatch
    repair_efficiency: float = 0.0  # ExhaustiveReviewRepairPhase: errors_fixed_in_one_pass / total_errors
    rag_context_effectiveness: float = 0.0  # DependencyReconciliationPhase: relevant_files_retrieved / total_relevant
    logic_plan_coverage: float = 0.0  # Percentage of logic plan items implemented
    circular_dep_resolution_rate: float = 0.0  # StructurePreReviewPhase: successfully resolved circular deps
    code_smell_detection_rate: float = 0.0  # SeniorReviewPhase: subtle errors detected / total injected

    timestamp: Optional[str] = None
    phase_name: Optional[str] = None  # Phase that was benchmarked


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
                        hallucination_ratio=data.get("hallucination_ratio", 0.0),
                        repair_efficiency=data.get("repair_efficiency", 0.0),
                        rag_context_effectiveness=data.get("rag_context_effectiveness", 0.0),
                        logic_plan_coverage=data.get("logic_plan_coverage", 0.0),
                        circular_dep_resolution_rate=data.get("circular_dep_resolution_rate", 0.0),
                        code_smell_detection_rate=data.get("code_smell_detection_rate", 0.0),
                        timestamp=data.get("timestamp"),
                        phase_name=data.get("phase_name"),
                    )
                    self.results.append(result)
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.warning(f"Failed to load benchmark result {result_file}: {e}")

    def get_best_model(
        self,
        task_type: str,
        metric: str = "success_rate",
    ) -> Optional[ModelBenchmarkResult]:  # Changed return type hint
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
        elif metric == "avg_time_ms":  # Changed to avg_time_ms
            best = min(relevant_results, key=lambda r: r.avg_time_ms)  # Changed to avg_time_ms
        else:
            return None

        return best  # Return the full object

    def get_model_rank(self, task_type: str) -> List[Tuple[str, float]]:
        """Get all models ranked by success rate for a task."""
        relevant = [r for r in self.results if r.task_type == task_type]
        grouped = {}
        for r in relevant:
            if r.model_name not in grouped:
                grouped[r.model_name] = []
            grouped[r.model_name].append(r.success_rate)

        # Average success rate per model
        model_scores = {model: mean(scores) for model, scores in grouped.items()}

        return sorted(model_scores.items(), key=lambda x: x[1], reverse=True)

    def get_stats_for_model(self, model_name: str, task_type: str) -> Optional[Dict]:
        """Get aggregated statistics for a model on a task."""
        relevant = [r for r in self.results if r.model_name == model_name and r.task_type == task_type]

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

    def evaluate_model_performance(
        self,
        model_name: str,
        phase_name: str,
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Evaluate model performance on a specific phase with weighted metrics.

        NEW METRICS INTEGRATION:
        - Hallucination Ratio: LogicPlanningPhase metric (lower is better)
        - Repair Efficiency: ExhaustiveReviewRepairPhase (higher is better)
        - RAG Context Effectiveness: DependencyReconciliationPhase (higher is better)
        - Code Smell Detection: SeniorReviewPhase (higher is better)

        Args:
            model_name: Model to evaluate
            phase_name: Phase being evaluated
            weights: Custom weights for different metrics. Default:
                {
                    "success_rate": 0.25,
                    "quality_score": 0.20,
                    "response_time": -0.10,  # Negative = lower is better
                    "hallucination_ratio": -0.15,
                    "repair_efficiency": 0.15,
                    "rag_context_effectiveness": 0.15,
                    "code_smell_detection": 0.10,
                }

        Returns:
            Weighted performance score (0-10)
        """
        if weights is None:
            weights = {
                "success_rate": 0.25,
                "quality_score": 0.20,
                "response_time": -0.10,  # Negative = prefer faster
                "hallucination_ratio": -0.15,  # Negative = prefer lower hallucination
                "repair_efficiency": 0.15,
                "rag_context_effectiveness": 0.15,
                "code_smell_detection": 0.10,
            }

        # Get relevant results for this model and phase
        relevant = [r for r in self.results if r.model_name == model_name and r.phase_name == phase_name]

        if not relevant:
            return 0.0

        # Calculate average metrics
        avg_success = mean(r.success_rate for r in relevant)
        avg_quality = mean(r.quality_score for r in relevant) / 10.0  # Normalize to 0-1
        avg_time = mean(r.avg_time_ms for r in relevant)
        max_time = max((r.avg_time_ms for r in relevant), default=1000)
        time_efficiency = 1.0 - min(avg_time / max_time, 1.0)  # Normalize: faster = higher

        avg_hallucination = mean(r.hallucination_ratio for r in relevant)
        avg_repair_efficiency = mean(r.repair_efficiency for r in relevant)
        avg_rag_effectiveness = mean(r.rag_context_effectiveness for r in relevant)
        avg_code_smell_detection = mean(r.code_smell_detection_rate for r in relevant)

        # Calculate weighted score
        score = 0.0
        score += weights.get("success_rate", 0.0) * avg_success * 10
        score += weights.get("quality_score", 0.0) * avg_quality * 10
        score += weights.get("response_time", 0.0) * time_efficiency * 10
        score += weights.get("hallucination_ratio", 0.0) * (1.0 - avg_hallucination) * 10
        score += weights.get("repair_efficiency", 0.0) * avg_repair_efficiency * 10
        score += weights.get("rag_context_effectiveness", 0.0) * avg_rag_effectiveness * 10
        score += weights.get("code_smell_detection", 0.0) * avg_code_smell_detection * 10

        # Normalize to 0-10 range
        return max(0.0, min(score, 10.0))


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

    # Fallback models for critical phases (rescue models)
    RESCUE_MODELS = {
        "senior_reviewer": ["gpt-oss:70b", "api:gpt-4", "api:claude-3"],
        "coder": ["gpt-oss:70b", "qwen3-coder-max", "api:gpt-4"],
        "planner": ["gpt-oss:70b", "api:claude-3"],
        "prototyper": ["gpt-oss:70b", "api:gpt-4"],
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

    def get_rescue_model(self, role: str, failed_model: str) -> Optional[str]:
        """
        NEW: Get a rescue model for a failed role.

        If a model fails in a critical phase (senior_reviewer, coder, planner),
        activate a higher-capacity rescue model.

        Args:
            role: The role that failed (e.g., "senior_reviewer")
            failed_model: The model that failed

        Returns:
            Rescue model name or None if no rescue available
        """
        rescue_candidates = self.RESCUE_MODELS.get(role, [])

        if not rescue_candidates:
            return None

        # Filter out the failed model itself
        available = [m for m in rescue_candidates if m != failed_model]

        if available:
            self.logger.warning(
                f"🚨 RESCUE ACTIVATION: {failed_model} failed for {role}. Activating rescue model: {available[0]}"
            )
            return available[0]

        return None

    def evaluate_phase_criticality(self, phase_name: str) -> float:
        """
        NEW: Evaluate the criticality level of a phase (0.0-1.0).

        Critical phases (senior_reviewer, logic planning) warrant rescue models
        if the primary model fails.

        Args:
            phase_name: Name of the phase

        Returns:
            Criticality score (0.0 = low, 1.0 = critical)
        """
        critical_phases = {
            "SeniorReviewPhase": 1.0,
            "LogicPlanningPhase": 0.9,
            "ExhaustiveReviewRepairPhase": 0.8,
            "FileContentGenerationPhase": 0.7,
            "StructurePreReviewPhase": 0.8,
        }

        return critical_phases.get(phase_name, 0.5)

    def generate_optimized_config(
        self,
        base_config: Dict,
    ) -> Dict:
        """Generate optimized model configuration based on benchmarks.

        NEW: Integrates weighted metrics and includes rescue model assignments.

        Args:
            base_config: Base configuration from settings.json

        Returns:
            Updated config with optimized model assignments and rescue models
        """
        optimized = base_config.copy()
        models_section = optimized.get("models", {})
        rescue_models_section = {}

        self.logger.info("🧪 Optimizing model assignments based on benchmarks...")

        for task_type, role in self.TASK_TO_ROLE.items():
            best_model = self.benchmark_db.get_best_model(
                task_type=task_type,
                metric="success_rate",
            )

            if best_model:
                # Get statistics to ensure confidence
                stats = self.benchmark_db.get_stats_for_model(best_model.model_name, task_type)
                if stats and stats["avg_success_rate"] >= self.confidence_threshold:
                    old_model = models_section.get(role, "unknown")
                    models_section[role] = best_model.model_name

                    success_pct = stats["avg_success_rate"] * 100
                    self.logger.info(
                        f"  📊 {role}: {old_model} → {best_model.model_name} ({success_pct:.1f}% success rate)"
                    )

                    # Assign rescue model if this is a critical role
                    rescue = self.get_rescue_model(role, best_model.model_name)
                    if rescue:
                        rescue_models_section[role] = rescue
                        self.logger.info(f"  🚨 {role} rescue model: {rescue}")

        optimized["models"] = models_section
        if rescue_models_section:
            optimized["rescue_models"] = rescue_models_section
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
                    suggestions.append(
                        {
                            "role": role,
                            "current_recommendation": best,
                            "alternative": second,
                            "improvement_percent": improvement_margin,
                            "confidence": best_score,
                        }
                    )

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
