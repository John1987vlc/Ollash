"""
Memory of Decisions - Enhanced decision context with learning capabilities.

Extends DecisionContextManager to:
- Remember decisions and their outcomes
- Extract user preferences from decision patterns
- Suggest similar past decisions when relevant context appears
- Track success metrics for different decision types
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DecisionOutcome(Enum):
    """Outcomes of decisions."""

    SUCCESSFUL = "successful"
    PARTIALLY_SUCCESSFUL = "partial"
    UNSUCCESSFUL = "unsuccessful"
    PENDING = "pending"
    BYPASSED = "bypassed"


class DecisionDomain(Enum):
    """Domains of decision making."""

    ARCHITECTURE = "architecture"
    SECURITY = "security"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    DESIGN = "design"
    TROUBLESHOOTING = "troubleshooting"
    OPTIMIZATION = "optimization"
    CONFIGURATION = "configuration"


@dataclass
class PreferencePattern:
    """Learned preference pattern from decision history."""

    pattern_id: str
    domain: DecisionDomain
    pattern_type: str  # e.g., "prefers_minimal_config", "avoids_complex_solutions"
    confidence: float  # 0-100
    frequency: int  # How many times this pattern was observed
    last_observed: str  # ISO timestamp
    examples: List[str] = field(default_factory=list)
    counter_examples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionSuggestion:
    """Suggestion based on similar past decisions."""

    suggestion_id: str
    base_decision_id: str  # The similar decision this is based on
    similarity_score: float  # 0-100
    suggested_action: str
    reasoning: str
    success_rate: float  # Based on outcomes of similar decisions
    confidence: float  # Overall confidence in suggestion
    relevant_context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MemoryOfDecisions:
    """
    Enhanced decision memory with learning and pattern recognition.

    Key features:
    - Stores decisions with outcomes
    - Identifies preference patterns
    - Suggests decisions based on similar past scenarios
    - Tracks success metrics for decision types
    - Learns user preferences over time
    """

    def __init__(self, project_root: Path, config: Optional[Dict] = None):
        """
        Initialize memory of decisions.

        Args:
            project_root: Root path for storing decision memory
            config: Optional configuration
        """
        self.project_root = project_root
        self.config = config or {}

        # Storage
        self.decisions_file = project_root / ".decision_memory.json"
        self.preferences_file = project_root / ".learned_preferences.json"
        self.suggestions_file = project_root / ".decision_suggestions.json"

        # In-memory caches
        self.decisions: Dict[str, Dict[str, Any]] = {}
        self.preferences: Dict[str, PreferencePattern] = {}
        self.suggestions_cache: List[DecisionSuggestion] = []

        # Statistics
        self.domain_stats: Dict[str, Dict[str, Any]] = {}

        self._load_memory()
        logger.info("MemoryOfDecisions initialized")

    def record_decision(
        self,
        decision_id: str,
        domain: DecisionDomain,
        decision_text: str,
        reasoning: str,
        context: Dict[str, Any],
        chosen_option: str,
        alternatives: Optional[List[str]] = None,
    ) -> bool:
        """
        Record a decision in memory.

        Args:
            decision_id: Unique ID for this decision
            domain: Domain of the decision
            decision_text: Description of the decision
            reasoning: Why this decision was made
            context: Context in which decision was made
            chosen_option: The option that was chosen
            alternatives: Other options that were considered

        Returns:
            bool: True if recorded successfully
        """
        try:
            decision_record = {
                "id": decision_id,
                "timestamp": datetime.now().isoformat(),
                "domain": domain.value,
                "decision": decision_text,
                "reasoning": reasoning,
                "context": context,
                "chosen_option": chosen_option,
                "alternatives": alternatives or [],
                "outcome": DecisionOutcome.PENDING.value,
                "outcome_details": None,
                "satisfaction_score": None,
                "lessons_learned": None,
            }

            self.decisions[decision_id] = decision_record

            # Update domain statistics
            self._update_domain_stats(domain)

            logger.info(f"Decision recorded: {decision_id} in {domain.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to record decision: {e}")
            return False

    def record_decision_outcome(
        self,
        decision_id: str,
        outcome: DecisionOutcome,
        details: Optional[str] = None,
        satisfaction_score: Optional[float] = None,
        lessons: Optional[List[str]] = None,
    ) -> bool:
        """
        Record the outcome of a previous decision.

        Args:
            decision_id: ID of the decision
            outcome: How the decision turned out
            details: Details about the outcome
            satisfaction_score: User satisfaction (0-100)
            lessons: Lessons learned from the outcome

        Returns:
            bool: Success status
        """
        try:
            if decision_id not in self.decisions:
                logger.warning(f"Decision not found: {decision_id}")
                return False

            decision = self.decisions[decision_id]
            decision["outcome"] = outcome.value
            decision["outcome_details"] = details
            decision["satisfaction_score"] = satisfaction_score
            decision["lessons_learned"] = lessons or []
            decision["outcome_timestamp"] = datetime.now().isoformat()

            # Extract preferences if satisfaction is high
            if satisfaction_score and satisfaction_score >= 80:
                self._extract_preferences_from_decision(decision)

            # Update statistics
            domain = DecisionDomain(decision["domain"])
            self._update_decision_stats(domain, outcome, satisfaction_score)

            logger.info(
                f"Decision outcome recorded: {decision_id} = {outcome.value} "
                f"(satisfaction: {satisfaction_score})"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to record decision outcome: {e}")
            return False

    def get_decision_suggestions(
        self,
        current_context: Dict[str, Any],
        domain: Optional[DecisionDomain] = None,
        limit: int = 5,
    ) -> List[DecisionSuggestion]:
        """
        Get suggestions based on similar past decisions.

        Args:
            current_context: Current context requiring a decision
            domain: Filter by domain (optional)
            limit: Maximum number of suggestions

        Returns:
            List: DecisionSuggestion objects, ranked by relevance
        """
        try:
            suggestions = []

            # Find similar decisions in history
            similar_decisions = self._find_similar_decisions(current_context, domain)

            for similar_decision, similarity_score in similar_decisions:
                # Calculate success rate for this type of decision
                success_rate = self._calculate_success_rate(
                    similar_decision["domain"], similar_decision["chosen_option"]
                )

                # Create suggestion
                suggestion = DecisionSuggestion(
                    suggestion_id=f"suggest_{datetime.now().timestamp()}",
                    base_decision_id=similar_decision["id"],
                    similarity_score=similarity_score,
                    suggested_action=similar_decision["chosen_option"],
                    reasoning=similar_decision["reasoning"],
                    success_rate=success_rate,
                    confidence=min(similarity_score * 0.6 + success_rate * 0.4, 100),
                    relevant_context=self._extract_relevant_context(
                        current_context, similar_decision["context"]
                    ),
                )

                suggestions.append(suggestion)

            # Sort by confidence
            suggestions.sort(key=lambda s: s.confidence, reverse=True)

            logger.info(
                f"Generated {len(suggestions)} decision suggestions for {domain or 'any'} domain"
            )

            return suggestions[:limit]

        except Exception as e:
            logger.error(f"Failed to get decision suggestions: {e}")
            return []

    def get_learned_preferences(
        self, domain: Optional[DecisionDomain] = None
    ) -> List[PreferencePattern]:
        """
        Get preferences learned from decision history.

        Args:
            domain: Filter by domain (optional)

        Returns:
            List: PreferencePattern objects
        """
        try:
            prefs = list(self.preferences.values())

            if domain:
                prefs = [p for p in prefs if p.domain == domain]

            # Sort by confidence and frequency
            prefs.sort(key=lambda p: (p.confidence, p.frequency), reverse=True)

            return prefs

        except Exception as e:
            logger.error(f"Failed to get learned preferences: {e}")
            return []

    def suggest_preference_change(
        self, preference_type: str, domain: DecisionDomain, reasoning: str
    ) -> bool:
        """
        Suggest a preference change based on recent decisions.

        Args:
            preference_type: Type of preference to modify
            domain: Domain affected
            reasoning: Why this change is suggested

        Returns:
            bool: Success status
        """
        try:
            # Analyze recent decisions
            recent_decisions = self._get_recent_decisions(domain, days=7)

            if not recent_decisions:
                return False

            # Calculate pattern change
            pattern_key = f"{domain.value}_{preference_type}"

            pattern = PreferencePattern(
                pattern_id=pattern_key,
                domain=domain,
                pattern_type=preference_type,
                confidence=self._calculate_pattern_confidence(recent_decisions),
                frequency=len(recent_decisions),
                last_observed=datetime.now().isoformat(),
                examples=[d["id"] for d in recent_decisions[:3]],
            )

            self.preferences[pattern_key] = pattern
            logger.info(f"Preference pattern updated: {pattern_key}")

            return True

        except Exception as e:
            logger.error(f"Failed to suggest preference change: {e}")
            return False

    def get_decision_analytics(
        self, domain: Optional[DecisionDomain] = None
    ) -> Dict[str, Any]:
        """
        Get analytics about decisions made.

        Args:
            domain: Filter by domain (optional)

        Returns:
            Dict: Analytics data
        """
        try:
            decisions_to_analyze = list(self.decisions.values())

            if domain:
                decisions_to_analyze = [
                    d for d in decisions_to_analyze if d["domain"] == domain.value
                ]

            if not decisions_to_analyze:
                return {
                    "total_decisions": 0,
                    "success_rate": 0.0,
                    "average_satisfaction": 0.0,
                    "domains": {},
                    "trends": {},
                }

            # Calculate metrics
            completed = [
                d
                for d in decisions_to_analyze
                if d["outcome"] != DecisionOutcome.PENDING.value
            ]
            successful = [
                d for d in completed if d["outcome"] == DecisionOutcome.SUCCESSFUL.value
            ]

            satisfaction_scores = [
                d["satisfaction_score"]
                for d in completed
                if d["satisfaction_score"] is not None
            ]

            analytics = {
                "total_decisions": len(decisions_to_analyze),
                "completed_decisions": len(completed),
                "pending_decisions": len(decisions_to_analyze) - len(completed),
                "success_rate": (len(successful) / len(completed) * 100)
                if completed
                else 0.0,
                "average_satisfaction": (
                    sum(satisfaction_scores) / len(satisfaction_scores)
                    if satisfaction_scores
                    else None
                ),
                "domains": self.domain_stats,
                "most_common_decision": self._get_most_common_decision(
                    decisions_to_analyze
                ),
                "highest_satisfaction_decision": self._get_highest_satisfaction_decision(
                    decisions_to_analyze
                ),
                "learned_preferences": [
                    p.to_dict() for p in self.get_learned_preferences(domain)
                ],
            }

            return analytics

        except Exception as e:
            logger.error(f"Failed to get decision analytics: {e}")
            return {}

    # ==================== Private Helpers ====================

    def _find_similar_decisions(
        self, context: Dict[str, Any], domain: Optional[DecisionDomain] = None
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Find similar decisions from history."""
        similar = []

        for decision in self.decisions.values():
            # Skip pending decisions
            if decision["outcome"] == DecisionOutcome.PENDING.value:
                continue

            # Filter by domain if specified
            if domain and decision["domain"] != domain.value:
                continue

            # Calculate similarity score
            similarity = self._calculate_context_similarity(
                context, decision["context"]
            )

            if similarity > 30:  # Minimum 30% similarity
                similar.append((decision, similarity))

        # Sort by similarity
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar[:10]  # Return top 10

    def _calculate_context_similarity(
        self, context1: Dict[str, Any], context2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between two contexts."""
        if not context1 or not context2:
            return 0.0

        # Simple keyword overlap method
        keys1 = set(str(context1).lower().split())
        keys2 = set(str(context2).lower().split())

        if not keys1 or not keys2:
            return 0.0

        intersection = len(keys1.intersection(keys2))
        union = len(keys1.union(keys2))

        return (intersection / union) * 100 if union > 0 else 0.0

    def _calculate_success_rate(self, domain: str, option: str) -> float:
        """Calculate success rate for a domain and option combination."""
        matching_decisions = [
            d
            for d in self.decisions.values()
            if d["domain"] == domain and d["chosen_option"] == option
        ]

        if not matching_decisions:
            return 50.0  # Default

        successful = [
            d
            for d in matching_decisions
            if d["outcome"] == DecisionOutcome.SUCCESSFUL.value
        ]

        return (len(successful) / len(matching_decisions)) * 100

    def _extract_preferences_from_decision(self, decision: Dict[str, Any]) -> None:
        """Extract preference patterns from a successful decision."""
        domain = DecisionDomain(decision["domain"])

        # Pattern: Preferred option type
        pattern_key = f"{domain.value}_prefers_{decision['chosen_option']}"

        if pattern_key in self.preferences:
            self.preferences[pattern_key].frequency += 1
            self.preferences[pattern_key].last_observed = datetime.now().isoformat()
        else:
            self.preferences[pattern_key] = PreferencePattern(
                pattern_id=pattern_key,
                domain=domain,
                pattern_type=f"prefers_{decision['chosen_option']}",
                confidence=80.0,
                frequency=1,
                last_observed=datetime.now().isoformat(),
                examples=[decision["id"]],
            )

    def _update_domain_stats(self, domain: DecisionDomain) -> None:
        """Update statistics for a domain."""
        if domain.value not in self.domain_stats:
            self.domain_stats[domain.value] = {
                "count": 0,
                "successful": 0,
                "unsuccessful": 0,
                "avg_satisfaction": 0.0,
            }

        self.domain_stats[domain.value]["count"] += 1

    def _update_decision_stats(
        self,
        domain: DecisionDomain,
        outcome: DecisionOutcome,
        satisfaction: Optional[float],
    ) -> None:
        """Update decision statistics."""
        stats = self.domain_stats.get(domain.value, {})

        if outcome == DecisionOutcome.SUCCESSFUL:
            stats["successful"] = stats.get("successful", 0) + 1
        elif outcome == DecisionOutcome.UNSUCCESSFUL:
            stats["unsuccessful"] = stats.get("unsuccessful", 0) + 1

    def _get_recent_decisions(
        self, domain: Optional[DecisionDomain] = None, days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get decisions from the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        recent = []

        for decision in self.decisions.values():
            ts = datetime.fromisoformat(decision["timestamp"])
            if ts >= cutoff:
                if domain is None or decision["domain"] == domain.value:
                    recent.append(decision)

        return recent

    def _extract_relevant_context(
        self, current: Dict[str, Any], similar: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract overlapping context keys."""
        return {k: current[k] for k in current.keys() if k in similar}

    def _calculate_pattern_confidence(self, decisions: List[Dict[str, Any]]) -> float:
        """Calculate confidence of a pattern from decisions."""
        if not decisions:
            return 0.0

        satisfaction_scores = [
            d.get("satisfaction_score", 50)
            for d in decisions
            if d.get("satisfaction_score") is not None
        ]

        if satisfaction_scores:
            return sum(satisfaction_scores) / len(satisfaction_scores)

        return 50.0

    def _get_most_common_decision(
        self, decisions: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Get the most frequently made decision."""
        if not decisions:
            return None

        options = {}
        for d in decisions:
            opt = d.get("chosen_option")
            if opt:
                options[opt] = options.get(opt, 0) + 1

        return max(options.items(), key=lambda x: x[1])[0] if options else None

    def _get_highest_satisfaction_decision(
        self, decisions: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Get decision with highest satisfaction."""
        best = None
        best_score = -1

        for d in decisions:
            score = d.get("satisfaction_score", -1)
            if score > best_score:
                best_score = score
                best = d.get("id")

        return best

    def _load_memory(self) -> None:
        """Load memory from persistent storage."""
        try:
            if self.decisions_file.exists():
                with open(self.decisions_file) as f:
                    self.decisions = json.load(f)

            if self.preferences_file.exists():
                with open(self.preferences_file) as f:
                    prefs_data = json.load(f)
                    for key, data in prefs_data.items():
                        self.preferences[key] = PreferencePattern(**data)

            logger.info("Decision memory loaded from disk")

        except Exception as e:
            logger.warning(f"Failed to load decision memory: {e}")

    def save(self) -> bool:
        """Save memory to persistent storage."""
        try:
            with open(self.decisions_file, "w") as f:
                json.dump(self.decisions, f, indent=2)

            prefs_data = {k: v.to_dict() for k, v in self.preferences.items()}
            with open(self.preferences_file, "w") as f:
                json.dump(prefs_data, f, indent=2)

            logger.info("Decision memory saved to disk")
            return True

        except Exception as e:
            logger.error(f"Failed to save decision memory: {e}")
            return False
