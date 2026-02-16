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
