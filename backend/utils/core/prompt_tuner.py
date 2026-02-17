"""
Reinforcement Learning from Feedback - Prompt Tuner

Adjusts prompt templates based on user corrections to generated code.
Tracks feedback, extracts few-shot examples, and tunes temperature.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.agent_logger import AgentLogger


@dataclass
class FeedbackEntry:
    """A single user feedback record."""

    prompt_id: str
    original_output: str
    user_correction: str
    rating: float  # 0.0 (bad) to 1.0 (good)
    phase_name: str = ""
    file_path: str = ""
    language: str = ""
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class FeedbackStore:
    """Persistent storage for user feedback on generated outputs."""

    def __init__(self, store_dir: Path):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._entries: List[FeedbackEntry] = []
        self._load()

    def _load(self):
        feedback_file = self.store_dir / "feedback.json"
        if feedback_file.exists():
            data = json.loads(feedback_file.read_text(encoding="utf-8"))
            self._entries = [FeedbackEntry.from_dict(d) for d in data]

    def _persist(self):
        feedback_file = self.store_dir / "feedback.json"
        feedback_file.write_text(
            json.dumps([e.to_dict() for e in self._entries], indent=2),
            encoding="utf-8",
        )

    def save(self, entry: FeedbackEntry) -> None:
        """Save a new feedback entry."""
        self._entries.append(entry)
        self._persist()

    def query(
        self,
        prompt_id: Optional[str] = None,
        min_rating: float = 0.0,
        phase_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[FeedbackEntry]:
        """Query feedback entries with optional filters."""
        results = self._entries

        if prompt_id:
            results = [e for e in results if e.prompt_id == prompt_id]
        if min_rating > 0:
            results = [e for e in results if e.rating >= min_rating]
        if phase_name:
            results = [e for e in results if e.phase_name == phase_name]

        # Most recent first
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def get_avg_rating(self, prompt_id: str) -> float:
        """Get average rating for a prompt."""
        entries = [e for e in self._entries if e.prompt_id == prompt_id]
        if not entries:
            return 0.5
        return sum(e.rating for e in entries) / len(entries)


class PromptTuner:
    """Adjusts prompt templates based on accumulated user feedback.

    Features:
    - Injects successful corrections as few-shot examples
    - Adjusts temperature based on feedback ratings
    - Provides context-aware prompt modifications
    """

    def __init__(self, feedback_store: FeedbackStore, logger: AgentLogger):
        self.feedback_store = feedback_store
        self.logger = logger

    def record_feedback(
        self,
        prompt_id: str,
        output: str,
        correction: str,
        rating: float,
        phase_name: str = "",
        file_path: str = "",
        language: str = "",
    ) -> None:
        """Record user feedback on a generated output."""
        entry = FeedbackEntry(
            prompt_id=prompt_id,
            original_output=output,
            user_correction=correction,
            rating=rating,
            phase_name=phase_name,
            file_path=file_path,
            language=language,
        )
        self.feedback_store.save(entry)
        self.logger.info(f"Recorded feedback for prompt '{prompt_id}': rating={rating:.1f}")

    def get_few_shot_examples(self, prompt_id: str, max_examples: int = 3) -> List[Dict[str, str]]:
        """Get high-quality correction examples as few-shot demonstrations.

        Returns examples where the user made corrections (rating < 0.7)
        that can be used to improve future generation.
        """
        entries = self.feedback_store.query(prompt_id=prompt_id, limit=20)

        # Filter for corrections (not perfect outputs) with meaningful corrections
        corrections = [
            e for e in entries if e.rating < 0.7 and e.user_correction and e.user_correction != e.original_output
        ]

        # Sort by most recent and take top examples
        examples = []
        for entry in corrections[:max_examples]:
            examples.append(
                {
                    "original": entry.original_output[:500],
                    "corrected": entry.user_correction[:500],
                    "context": entry.file_path or entry.phase_name,
                }
            )

        return examples

    def get_adjusted_prompt(self, base_prompt: str, prompt_id: str, context: Optional[Dict] = None) -> str:
        """Get a prompt adjusted with few-shot examples from feedback.

        If there are relevant corrections in the feedback store,
        they're injected as examples to guide the model.
        """
        examples = self.get_few_shot_examples(prompt_id)

        if not examples:
            return base_prompt

        examples_text = "\n\n--- Previous corrections to learn from ---\n"
        for i, ex in enumerate(examples, 1):
            examples_text += f"\nCorrection {i}:\n"
            examples_text += f"  Original: {ex['original'][:200]}...\n"
            examples_text += f"  Corrected: {ex['corrected'][:200]}...\n"
            if ex["context"]:
                examples_text += f"  Context: {ex['context']}\n"

        examples_text += "\n--- Apply these patterns in your generation ---\n"

        return base_prompt + examples_text

    def adjust_temperature(self, prompt_id: str, base_temperature: float = 0.5) -> float:
        """Adjust generation temperature based on feedback ratings.

        Lower ratings suggest the model needs to be more conservative (lower temp).
        Higher ratings allow more creativity (higher temp).
        """
        avg_rating = self.feedback_store.get_avg_rating(prompt_id)

        if avg_rating < 0.3:
            # Many corrections needed - be more conservative
            adjusted = max(0.1, base_temperature - 0.2)
        elif avg_rating < 0.5:
            adjusted = max(0.2, base_temperature - 0.1)
        elif avg_rating > 0.8:
            # Good performance - allow more creativity
            adjusted = min(0.9, base_temperature + 0.1)
        else:
            adjusted = base_temperature

        return round(adjusted, 2)

    def auto_evaluate(
        self,
        prompt_id: str,
        output: str,
        expected_criteria: Dict[str, Any],
    ) -> float:
        """Automatically evaluate output quality against expected criteria.

        Scores output on a 0.0-1.0 scale based on simple heuristic checks.
        Does not require an LLM call - uses pattern matching.

        Args:
            prompt_id: Identifier for the prompt that generated the output.
            output: The generated output to evaluate.
            expected_criteria: Dict with keys like:
                - "min_length": Minimum expected character count
                - "max_length": Maximum expected character count
                - "required_keywords": List of keywords that should appear
                - "forbidden_patterns": List of patterns that should NOT appear
                - "expected_format": "json", "markdown", "code", etc.

        Returns:
            Quality score from 0.0 to 1.0.
        """
        if not output or not output.strip():
            return 0.0

        score = 1.0
        penalties = 0.0

        # Length checks
        min_len = expected_criteria.get("min_length", 0)
        max_len = expected_criteria.get("max_length", 0)
        if min_len and len(output) < min_len:
            penalties += 0.3
        if max_len and len(output) > max_len:
            penalties += 0.1

        # Required keywords
        required = expected_criteria.get("required_keywords", [])
        if required:
            output_lower = output.lower()
            found = sum(1 for kw in required if kw.lower() in output_lower)
            if required:
                keyword_ratio = found / len(required)
                penalties += (1.0 - keyword_ratio) * 0.3

        # Forbidden patterns
        forbidden = expected_criteria.get("forbidden_patterns", [])
        for pattern in forbidden:
            if pattern.lower() in output.lower():
                penalties += 0.15

        # Format checks
        expected_format = expected_criteria.get("expected_format", "")
        if expected_format == "json":
            try:
                json.loads(output)
            except (json.JSONDecodeError, ValueError):
                penalties += 0.4
        elif expected_format == "markdown":
            if not any(marker in output for marker in ["#", "```", "- ", "* "]):
                penalties += 0.2

        final_score = max(0.0, score - penalties)

        # Auto-record as feedback
        self.record_feedback(
            prompt_id=prompt_id,
            output=output[:500],
            correction="",
            rating=final_score,
        )

        return round(final_score, 2)

    def suggest_prompt_rewrite(self, prompt_id: str) -> Optional[str]:
        """Suggest improvements to a prompt based on accumulated feedback.

        Analyzes correction patterns and generates textual suggestions.
        Returns None if insufficient feedback data.
        """
        entries = self.feedback_store.query(prompt_id=prompt_id, limit=20)
        if len(entries) < 3:
            return None

        avg_rating = self.feedback_store.get_avg_rating(prompt_id)
        if avg_rating >= 0.8:
            return None  # Prompt is performing well

        # Analyze common correction patterns
        corrections = [e for e in entries if e.rating < 0.7 and e.user_correction]
        if not corrections:
            return None

        suggestions = []
        suggestions.append(f"Prompt '{prompt_id}' has avg rating {avg_rating:.2f} ({len(entries)} samples).")
        suggestions.append(f"Found {len(corrections)} corrections to learn from.")

        # Extract recurring themes from corrections
        correction_texts = [c.user_correction for c in corrections[:5]]
        if correction_texts:
            suggestions.append("Recent correction patterns:")
            for i, ct in enumerate(correction_texts, 1):
                suggestions.append(f"  {i}. {ct[:200]}")

        suggestions.append("Consider adjusting the prompt to address these recurring issues.")

        return "\n".join(suggestions)

    def apply_rewrite(self, prompt_id: str, new_prompt_content: str, prompt_file: Path) -> bool:
        """Apply a prompt rewrite to the prompt JSON file.

        Updates the 'content' field of the prompt while preserving other fields.

        Args:
            prompt_id: Identifier for tracking.
            new_prompt_content: The new prompt text.
            prompt_file: Path to the prompt JSON file.

        Returns:
            True if successfully written, False otherwise.
        """
        try:
            if not prompt_file.exists():
                self.logger.warning(f"Prompt file not found: {prompt_file}")
                return False

            data = json.loads(prompt_file.read_text(encoding="utf-8"))
            data["content"] = new_prompt_content
            data["_tuned_at"] = datetime.now().isoformat()
            data["_tuned_from"] = prompt_id

            prompt_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            self.logger.info(f"Prompt rewritten: {prompt_file}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to apply prompt rewrite: {e}")
            return False

    def get_feedback_summary(self, prompt_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a summary of feedback statistics."""
        entries = self.feedback_store.query(prompt_id=prompt_id)
        if not entries:
            return {"total": 0, "avg_rating": 0.0}

        return {
            "total": len(entries),
            "avg_rating": sum(e.rating for e in entries) / len(entries),
            "corrections_count": sum(1 for e in entries if e.rating < 0.7),
            "good_outputs": sum(1 for e in entries if e.rating >= 0.7),
        }
