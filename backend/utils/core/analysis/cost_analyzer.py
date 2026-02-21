"""
Model Cost Analyzer

Monitors token consumption per phase/model and suggests lighter models
for trivial tasks to optimize resource usage.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger


@dataclass
class UsageRecord:
    """A single token usage record."""

    model_name: str
    phase_name: str
    task_type: str
    prompt_tokens: int
    completion_tokens: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ModelSuggestion:
    """Suggestion to switch to a more cost-effective model."""

    current_model: str
    suggested_model: str
    phase: str
    estimated_savings_pct: float
    reason: str


@dataclass
class PhaseEfficiency:
    """Efficiency metrics for a specific phase."""

    phase_name: str
    total_tokens: int
    request_count: int
    avg_tokens_per_request: float
    primary_model: str
    models_used: List[str]


@dataclass
class CostReport:
    """Complete cost analysis report."""

    total_tokens: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_requests: int
    usage_by_model: Dict[str, Dict[str, int]]
    usage_by_phase: Dict[str, Dict[str, int]]
    phase_efficiencies: List[PhaseEfficiency]
    suggestions: List[ModelSuggestion]
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_requests": self.total_requests,
            "usage_by_model": self.usage_by_model,
            "usage_by_phase": self.usage_by_phase,
            "phase_efficiencies": [
                {
                    "phase": pe.phase_name,
                    "total_tokens": pe.total_tokens,
                    "requests": pe.request_count,
                    "avg_tokens": pe.avg_tokens_per_request,
                    "primary_model": pe.primary_model,
                }
                for pe in self.phase_efficiencies
            ],
            "suggestions": [
                {
                    "current": s.current_model,
                    "suggested": s.suggested_model,
                    "phase": s.phase,
                    "savings_pct": s.estimated_savings_pct,
                    "reason": s.reason,
                }
                for s in self.suggestions
            ],
            "timestamp": self.timestamp,
        }


# Model tiers for cost estimation (relative cost multiplier)
MODEL_COST_TIERS: Dict[str, float] = {
    "ministral-3:8b": 0.1,
    "ministral": 0.1,
    "llama3.2:3b": 0.1,
    "gemma2:2b": 0.1,
    "phi3:mini": 0.15,
    "llama3.2:8b": 0.2,
    "mistral:latest": 0.3,
    "llama3:8b": 0.3,
    "codellama:7b": 0.3,
    "qwen2.5-coder:7b": 0.3,
    "mixtral:8x7b": 0.6,
    "llama3:70b": 0.8,
    "qwen3-coder:30b": 0.7,
    "deepseek-coder-v2:16b": 0.5,
    "codestral:latest": 0.6,
}

# Phases that typically don't need heavy models
LIGHTWEIGHT_PHASES = {
    "ReadmeGenerationPhase",
    "EmptyFileScaffoldingPhase",
    "VerificationPhase",
    "LicenseCompliancePhase",
    "DependencyReconciliationPhase",
    "DocumentationTranslationPhase",
}

# Phases requiring high-capability models
HEAVYWEIGHT_PHASES = {
    "FileContentGenerationPhase",
    "ExhaustiveReviewRepairPhase",
    "SeniorReviewPhase",
    "TestGenerationExecutionPhase",
    "RefactoringPhase",
}


class CostAnalyzer:
    """Analyzes token usage patterns and suggests cost optimizations.

    Tracks usage records per model and phase, then provides reports
    and suggestions for using lighter models where appropriate.
    """

    def __init__(self, logger: AgentLogger, llm_config: Optional[Dict] = None):
        self.logger = logger
        self.llm_config = llm_config or {}
        self._records: List[UsageRecord] = []

    def record_usage(
        self,
        model_name: str,
        phase_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        task_type: str = "generation",
    ) -> None:
        """Record a token usage event."""
        record = UsageRecord(
            model_name=model_name,
            phase_name=phase_name,
            task_type=task_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        self._records.append(record)

    def get_usage_by_model(self) -> Dict[str, Dict[str, int]]:
        """Aggregate usage by model."""
        by_model: Dict[str, Dict[str, int]] = {}
        for r in self._records:
            if r.model_name not in by_model:
                by_model[r.model_name] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "requests": 0,
                }
            by_model[r.model_name]["prompt_tokens"] += r.prompt_tokens
            by_model[r.model_name]["completion_tokens"] += r.completion_tokens
            by_model[r.model_name]["total_tokens"] += r.total_tokens
            by_model[r.model_name]["requests"] += 1
        return by_model

    def get_usage_by_phase(self) -> Dict[str, Dict[str, int]]:
        """Aggregate usage by phase."""
        by_phase: Dict[str, Dict[str, int]] = {}
        for r in self._records:
            if r.phase_name not in by_phase:
                by_phase[r.phase_name] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "requests": 0,
                }
            by_phase[r.phase_name]["prompt_tokens"] += r.prompt_tokens
            by_phase[r.phase_name]["completion_tokens"] += r.completion_tokens
            by_phase[r.phase_name]["total_tokens"] += r.total_tokens
            by_phase[r.phase_name]["requests"] += 1
        return by_phase

    def get_phase_efficiencies(self) -> List[PhaseEfficiency]:
        """Calculate efficiency metrics per phase."""
        by_phase = self.get_usage_by_phase()
        efficiencies = []

        for phase_name, usage in by_phase.items():
            # Find models used in this phase
            models_in_phase: Dict[str, int] = {}
            for r in self._records:
                if r.phase_name == phase_name:
                    models_in_phase[r.model_name] = models_in_phase.get(r.model_name, 0) + r.total_tokens

            primary_model = max(models_in_phase, key=models_in_phase.get) if models_in_phase else "unknown"
            requests = usage["requests"]

            efficiencies.append(
                PhaseEfficiency(
                    phase_name=phase_name,
                    total_tokens=usage["total_tokens"],
                    request_count=requests,
                    avg_tokens_per_request=usage["total_tokens"] / max(1, requests),
                    primary_model=primary_model,
                    models_used=list(models_in_phase.keys()),
                )
            )

        return efficiencies

    def suggest_downgrades(self) -> List[ModelSuggestion]:
        """Suggest lighter models for phases that don't need heavy ones."""
        suggestions = []
        efficiencies = self.get_phase_efficiencies()

        for pe in efficiencies:
            # Skip phases that need heavy models
            if pe.phase_name in HEAVYWEIGHT_PHASES:
                continue

            current_cost = MODEL_COST_TIERS.get(pe.primary_model, 0.5)

            # If using a costly model for a lightweight phase, suggest downgrade
            if pe.phase_name in LIGHTWEIGHT_PHASES and current_cost > 0.2:
                suggestions.append(
                    ModelSuggestion(
                        current_model=pe.primary_model,
                        suggested_model="ministral-3:8b",
                        phase=pe.phase_name,
                        estimated_savings_pct=round((1 - 0.1 / current_cost) * 100, 1),
                        reason=f"{pe.phase_name} is a lightweight phase that doesn't require a high-capability model.",
                    )
                )
            # If avg tokens per request is very low, model might be overkill
            elif pe.avg_tokens_per_request < 500 and current_cost > 0.3:
                suggestions.append(
                    ModelSuggestion(
                        current_model=pe.primary_model,
                        suggested_model="mistral:latest",
                        phase=pe.phase_name,
                        estimated_savings_pct=round((1 - 0.3 / current_cost) * 100, 1),
                        reason=f"Low token usage ({pe.avg_tokens_per_request:.0f} avg) "
                        f"suggests a lighter model would suffice.",
                    )
                )

        return suggestions

    def get_report(self) -> CostReport:
        """Generate a complete cost analysis report."""
        by_model = self.get_usage_by_model()
        by_phase = self.get_usage_by_phase()
        efficiencies = self.get_phase_efficiencies()
        suggestions = self.suggest_downgrades()

        total_prompt = sum(r.prompt_tokens for r in self._records)
        total_completion = sum(r.completion_tokens for r in self._records)

        report = CostReport(
            total_tokens=total_prompt + total_completion,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_requests=len(self._records),
            usage_by_model=by_model,
            usage_by_phase=by_phase,
            phase_efficiencies=efficiencies,
            suggestions=suggestions,
        )

        self.logger.info(
            f"Cost report: {report.total_tokens:,} tokens across "
            f"{report.total_requests} requests, {len(suggestions)} optimization suggestions"
        )
        return report

    def reset(self) -> None:
        """Clear all usage records."""
        self._records.clear()
