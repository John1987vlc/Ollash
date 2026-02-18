"""Multidimensional rubric evaluation for benchmark responses.

Replaces binary pass/fail scoring with dimensional evaluation:
- Strict JSON compliance (critical for Structure Generation)
- Reasoning depth (circular dependency resolution for Logic Planning)
- Context window utilization (summarization precision for Project Analysis)
- Creativity (novel solutions, design patterns)
- Speed (time efficiency relative to limits)
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from backend.utils.core.agent_logger import AgentLogger


class RubricDimension(Enum):
    """Evaluation dimensions for benchmark rubrics."""

    STRICT_JSON = "strict_json_score"
    REASONING_DEPTH = "reasoning_depth_score"
    CONTEXT_UTILIZATION = "context_utilization_score"
    CREATIVITY = "creativity_score"
    SPEED = "speed_score"


@dataclass
class DimensionResult:
    """Result for a single rubric dimension evaluation."""

    dimension: RubricDimension
    score: float  # 0.0 to 1.0
    details: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RubricResult:
    """Aggregated result across all dimensions."""

    model_name: str
    task_name: str
    dimension_results: List[DimensionResult] = field(default_factory=list)
    overall_score: float = 0.0

    def compute_overall(self) -> float:
        """Compute overall score as mean of dimension scores."""
        if not self.dimension_results:
            return 0.0
        total = sum(dr.score for dr in self.dimension_results)
        self.overall_score = total / len(self.dimension_results)
        return self.overall_score

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON output."""
        return {
            "model_name": self.model_name,
            "task_name": self.task_name,
            "overall_score": round(self.overall_score, 4),
            "dimensions": {
                dr.dimension.value: {
                    "score": round(dr.score, 4),
                    "details": dr.details,
                    "raw_data": dr.raw_data,
                }
                for dr in self.dimension_results
            },
        }


class RubricEvaluator:
    """Evaluates LLM responses against multidimensional rubrics."""

    # Reasoning indicators for depth evaluation
    REASONING_KEYWORDS = [
        "dependency",
        "dependencies",
        "circular",
        "cycle",
        "topological",
        "order",
        "sequence",
        "prerequisite",
        "before",
        "after",
        "requires",
        "depends on",
        "step 1",
        "step 2",
        "step 3",
        "first",
        "then",
        "finally",
        "because",
        "therefore",
        "consequently",
        "resolve",
        "break the cycle",
        "interface",
        "abstraction",
        "decouple",
    ]

    # Design patterns for creativity evaluation
    DESIGN_PATTERNS = [
        "singleton",
        "factory",
        "observer",
        "strategy",
        "decorator",
        "adapter",
        "facade",
        "mvc",
        "mvvm",
        "repository",
        "dependency injection",
        "middleware",
        "pipeline",
        "event-driven",
        "pub/sub",
        "microservice",
    ]

    def __init__(self, logger: AgentLogger):
        self.logger = logger
        self._evaluators: Dict[RubricDimension, Callable] = {
            RubricDimension.STRICT_JSON: self._evaluate_json_compliance,
            RubricDimension.REASONING_DEPTH: self._evaluate_reasoning_depth,
            RubricDimension.CONTEXT_UTILIZATION: self._evaluate_context_utilization,
            RubricDimension.CREATIVITY: self._evaluate_creativity,
            RubricDimension.SPEED: self._evaluate_speed,
        }

    def evaluate(
        self,
        model_name: str,
        task_name: str,
        response_content: str,
        task_data: Dict[str, Any],
        duration_sec: float,
        dimensions: Optional[List[RubricDimension]] = None,
    ) -> RubricResult:
        """Evaluate response against specified dimensions (or all).

        Args:
            model_name: Name of the model being evaluated.
            task_name: Name of the benchmark task.
            response_content: The full LLM response text.
            task_data: Task metadata (type, description, ground_truth, etc.).
            duration_sec: Time taken to generate the response.
            dimensions: Specific dimensions to evaluate, or None for all.

        Returns:
            RubricResult with per-dimension scores and overall score.
        """
        dims = dimensions or list(RubricDimension)
        result = RubricResult(model_name=model_name, task_name=task_name)

        for dim in dims:
            evaluator = self._evaluators.get(dim)
            if evaluator:
                try:
                    dim_result = evaluator(response_content, task_data, duration_sec)
                    result.dimension_results.append(dim_result)
                except Exception as e:
                    self.logger.warning(f"Rubric evaluation failed for {dim.value}: {e}")
                    result.dimension_results.append(
                        DimensionResult(
                            dimension=dim,
                            score=0.0,
                            details=f"Evaluation error: {e}",
                        )
                    )

        result.compute_overall()
        return result

    def _evaluate_json_compliance(self, response: str, task_data: Dict, duration: float) -> DimensionResult:
        """Evaluate JSON format compliance.

        Extracts ```json code blocks and standalone JSON objects,
        attempts to parse each, and scores based on valid/total ratio.
        """
        # Extract ```json ... ``` blocks
        json_blocks = re.findall(r"```json\s*(.*?)```", response, re.DOTALL)

        # Also try to find standalone JSON objects/arrays
        standalone_json = re.findall(r"(?:^|\n)\s*(\{[^`]*?\})\s*(?:\n|$)", response, re.DOTALL)
        standalone_json += re.findall(r"(?:^|\n)\s*(\[[^`]*?\])\s*(?:\n|$)", response, re.DOTALL)

        all_blocks = json_blocks + standalone_json

        if not all_blocks:
            return DimensionResult(
                dimension=RubricDimension.STRICT_JSON,
                score=0.5,  # Neutral if no JSON expected/found
                details="No JSON blocks found in response",
                raw_data={"total_blocks": 0, "valid_blocks": 0},
            )

        valid_count = 0
        errors = []
        for i, block in enumerate(all_blocks):
            try:
                json.loads(block.strip())
                valid_count += 1
            except (json.JSONDecodeError, ValueError) as e:
                errors.append(f"Block {i}: {str(e)[:80]}")

        total = len(all_blocks)
        score = valid_count / total if total > 0 else 0.0

        return DimensionResult(
            dimension=RubricDimension.STRICT_JSON,
            score=score,
            details=f"{valid_count}/{total} JSON blocks valid",
            raw_data={
                "total_blocks": total,
                "valid_blocks": valid_count,
                "errors": errors[:5],
            },
        )

    def _evaluate_reasoning_depth(self, response: str, task_data: Dict, duration: float) -> DimensionResult:
        """Evaluate reasoning depth via keyword/pattern heuristics.

        Measures:
        - Presence of dependency ordering logic
        - Detection of circular references
        - Step-by-step breakdown markers
        """
        response_lower = response.lower()

        # Count reasoning indicators
        keyword_hits = sum(1 for kw in self.REASONING_KEYWORDS if kw in response_lower)
        max_keywords = len(self.REASONING_KEYWORDS)

        # Check for structured reasoning (numbered steps, bullet points)
        step_patterns = re.findall(r"(?:^|\n)\s*(?:\d+[\.\)]\s|[-*]\s)", response)
        has_structured_steps = len(step_patterns) >= 3

        # Check for explicit dependency analysis
        has_dependency_analysis = any(
            phrase in response_lower
            for phrase in ["circular dependency", "dependency graph", "topological sort", "import cycle"]
        )

        # Normalize keyword score (0-1)
        keyword_score = min(keyword_hits / max(max_keywords * 0.3, 1), 1.0)

        # Composite score
        score = keyword_score * 0.5
        if has_structured_steps:
            score += 0.25
        if has_dependency_analysis:
            score += 0.25

        return DimensionResult(
            dimension=RubricDimension.REASONING_DEPTH,
            score=min(score, 1.0),
            details=f"Keywords: {keyword_hits}/{max_keywords}, Steps: {len(step_patterns)}, DepAnalysis: {has_dependency_analysis}",
            raw_data={
                "keyword_hits": keyword_hits,
                "structured_steps": len(step_patterns),
                "has_dependency_analysis": has_dependency_analysis,
            },
        )

    def _evaluate_context_utilization(self, response: str, task_data: Dict, duration: float) -> DimensionResult:
        """Evaluate context window utilization and summarization precision.

        If task_data has 'ground_truth_summary', compare response against it
        using token overlap. Also detect potential hallucinations.
        """
        ground_truth = task_data.get("ground_truth_summary", "")

        if not ground_truth:
            # Without ground truth, evaluate response completeness heuristically
            response_length = len(response.split())
            description_length = len(task_data.get("description", "").split())

            # Good utilization: response is substantive relative to input
            if description_length > 0:
                ratio = min(response_length / max(description_length * 2, 1), 1.0)
            else:
                ratio = 0.5

            return DimensionResult(
                dimension=RubricDimension.CONTEXT_UTILIZATION,
                score=min(ratio, 1.0),
                details=f"Response words: {response_length}, no ground truth available",
                raw_data={"response_words": response_length, "has_ground_truth": False},
            )

        # Token overlap comparison with ground truth
        truth_tokens = set(ground_truth.lower().split())
        response_tokens = set(response.lower().split())

        if not truth_tokens:
            return DimensionResult(
                dimension=RubricDimension.CONTEXT_UTILIZATION,
                score=0.5,
                details="Empty ground truth",
                raw_data={"has_ground_truth": True},
            )

        # Precision: what fraction of response tokens are in ground truth
        overlap = truth_tokens & response_tokens
        precision = len(overlap) / max(len(response_tokens), 1)
        recall = len(overlap) / max(len(truth_tokens), 1)

        # F1-like score
        if precision + recall > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0.0

        # Hallucination indicator: response tokens not in truth (excluding common words)
        common_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for", "and", "or", "of"}
        novel_tokens = response_tokens - truth_tokens - common_words
        hallucination_ratio = len(novel_tokens) / max(len(response_tokens - common_words), 1)

        return DimensionResult(
            dimension=RubricDimension.CONTEXT_UTILIZATION,
            score=f1,
            details=f"Precision: {precision:.2f}, Recall: {recall:.2f}, F1: {f1:.2f}, Hallucination: {hallucination_ratio:.2f}",
            raw_data={
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "hallucination_ratio": round(hallucination_ratio, 4),
                "has_ground_truth": True,
            },
        )

    def _evaluate_creativity(self, response: str, task_data: Dict, duration: float) -> DimensionResult:
        """Evaluate creativity and solution quality.

        Measures:
        - Distinct file types generated
        - Design patterns mentioned/used
        - Non-boilerplate code ratio
        """
        response_lower = response.lower()

        # Count distinct file extensions in code blocks or file references
        file_extensions = set(re.findall(r"\.([a-z]{1,6})\b", response_lower))
        code_extensions = file_extensions & {
            "py",
            "js",
            "ts",
            "html",
            "css",
            "json",
            "yaml",
            "yml",
            "toml",
            "md",
            "sql",
            "sh",
            "dockerfile",
            "go",
            "rs",
            "java",
            "rb",
            "php",
        }

        # Count design patterns mentioned
        patterns_found = [p for p in self.DESIGN_PATTERNS if p in response_lower]

        # Check for non-boilerplate indicators
        has_error_handling = any(
            kw in response_lower for kw in ["try:", "except", "catch", "error handling", "validation"]
        )
        has_testing = any(kw in response_lower for kw in ["test_", "pytest", "unittest", "jest", "mocha"])
        has_documentation = any(kw in response_lower for kw in ["docstring", '"""', "readme", "documentation"])

        # Score components
        file_diversity_score = min(len(code_extensions) / 5.0, 1.0)
        pattern_score = min(len(patterns_found) / 3.0, 1.0)
        completeness_score = sum([has_error_handling, has_testing, has_documentation]) / 3.0

        score = file_diversity_score * 0.3 + pattern_score * 0.4 + completeness_score * 0.3

        return DimensionResult(
            dimension=RubricDimension.CREATIVITY,
            score=min(score, 1.0),
            details=f"File types: {len(code_extensions)}, Patterns: {len(patterns_found)}, "
            f"ErrorHandling: {has_error_handling}, Tests: {has_testing}, Docs: {has_documentation}",
            raw_data={
                "file_extensions": sorted(code_extensions),
                "patterns_found": patterns_found,
                "has_error_handling": has_error_handling,
                "has_testing": has_testing,
                "has_documentation": has_documentation,
            },
        )

    def _evaluate_speed(self, response: str, task_data: Dict, duration: float) -> DimensionResult:
        """Evaluate speed efficiency relative to time limit.

        Score = 1.0 - (actual_time / limit_time), clamped to [0, 1].
        Faster responses score higher.
        """
        time_limit_minutes = task_data.get("time_limit_minutes", 5)
        limit_sec = time_limit_minutes * 60

        if limit_sec <= 0:
            score = 0.5
        else:
            ratio = duration / limit_sec
            score = max(0.0, min(1.0 - ratio, 1.0))

        return DimensionResult(
            dimension=RubricDimension.SPEED,
            score=score,
            details=f"Duration: {duration:.1f}s / Limit: {limit_sec}s ({duration / limit_sec * 100:.1f}%)",
            raw_data={
                "duration_sec": round(duration, 2),
                "limit_sec": limit_sec,
                "time_ratio": round(duration / max(limit_sec, 1), 4),
            },
        )


class MultidimensionalRubric:
    """Configuration mapping phase/task types to relevant rubric dimensions."""

    PHASE_DIMENSIONS: Dict[str, List[RubricDimension]] = {
        "structure_generation": [RubricDimension.STRICT_JSON, RubricDimension.REASONING_DEPTH],
        "logic_planning": [RubricDimension.REASONING_DEPTH, RubricDimension.CONTEXT_UTILIZATION],
        "project_analysis": [RubricDimension.CONTEXT_UTILIZATION, RubricDimension.CREATIVITY],
        "file_content": [RubricDimension.CREATIVITY, RubricDimension.STRICT_JSON],
        "review": [RubricDimension.REASONING_DEPTH, RubricDimension.CONTEXT_UTILIZATION],
        "web_app": [RubricDimension.CREATIVITY, RubricDimension.STRICT_JSON, RubricDimension.SPEED],
        "cli_tool": [RubricDimension.CREATIVITY, RubricDimension.SPEED],
        "game_simple": [RubricDimension.CREATIVITY, RubricDimension.SPEED],
        "data_script": [RubricDimension.CONTEXT_UTILIZATION, RubricDimension.SPEED],
        "utility_tool": [RubricDimension.CREATIVITY, RubricDimension.SPEED],
        "logic_flow": [RubricDimension.REASONING_DEPTH, RubricDimension.STRICT_JSON],
        "error_handling": [RubricDimension.REASONING_DEPTH, RubricDimension.CREATIVITY],
        "code_structure": [RubricDimension.STRICT_JSON, RubricDimension.CREATIVITY],
        "readability": [RubricDimension.CREATIVITY, RubricDimension.CONTEXT_UTILIZATION],
        "functionality": [RubricDimension.REASONING_DEPTH, RubricDimension.CREATIVITY],
        "critical_refactoring": [
            RubricDimension.REASONING_DEPTH,
            RubricDimension.CONTEXT_UTILIZATION,
            RubricDimension.CREATIVITY,
        ],
        "dependency_verification": [RubricDimension.STRICT_JSON, RubricDimension.CONTEXT_UTILIZATION],
    }

    @classmethod
    def get_dimensions_for_task(cls, task_type: str) -> List[RubricDimension]:
        """Get relevant rubric dimensions for a task type.

        Falls back to all dimensions if task type is not mapped.
        """
        return cls.PHASE_DIMENSIONS.get(task_type, list(RubricDimension))
