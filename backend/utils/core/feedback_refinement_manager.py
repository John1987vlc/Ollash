"""
Phase 4: Feedback Refinement Manager
Handles paragraph-level critique, refinement, and validation cycles
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import re


@dataclass
class ParagraphContext:
    """Represents a text paragraph with metadata"""
    index: int
    text: str
    original_text: str
    source_id: str
    word_count: int = 0
    readability_score: float = 0.0
    refinement_history: List['RefinementRecord'] = field(default_factory=list)

    def __post_init__(self):
        self.word_count = len(self.text.split())
        self.readability_score = self._calculate_readability()

    def _calculate_readability(self) -> float:
        """Simple readability score (0-100)"""
        words = self.text.split()
        if not words:
            return 0.0

        avg_word_length = sum(len(w) for w in words) / len(words)
        avg_sentence_length = len(words) / max(len(self.text.split('.')), 1)

        # Flesch-Kincaid simplified: lower is better (more readable)
        score = min(100, max(0, 100 - (avg_word_length * 4 + avg_sentence_length * 1.5)))
        return score


@dataclass
class RefinementRecord:
    """Records a single refinement action"""
    timestamp: str
    action_type: str  # 'critique', 'refine', 'validate', 'rollback'
    original: str
    refined: str
    critique: Optional[str] = None
    feedback_score: float = 0.0
    applied: bool = False
    validator_status: str = "pending"  # pending, passed, failed, manual_review

    def to_dict(self):
        return asdict(self)


@dataclass
class RefinementMetrics:
    """Tracks refinement performance"""
    total_paragraphs: int = 0
    refined_count: int = 0
    validation_passed: int = 0
    validation_failed: int = 0
    avg_readability_improvement: float = 0.0
    total_iterations: int = 0

    def to_dict(self):
        return asdict(self)


class FeedbackRefinementManager:
    """
    Manages iterative refinement of text through feedback cycles

    Workflow:
    1. Load document → extract paragraphs
    2. Select paragraphs for refinement
    3. Generate critique using LLM
    4. Apply refinements
    5. Validate against sources
    6. Track metrics and history
    """

    def __init__(self, workspace_path: str = "knowledge_workspace"):
        self.workspace = Path(workspace_path)
        self.refinement_dir = self.workspace / "refinements"
        self.refinement_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_file = self.refinement_dir / "refinement_metrics.json"
        self.history_file = self.refinement_dir / "refinement_history.json"
        self.metrics = self._load_metrics()
        self.history = self._load_history()

    def _load_metrics(self) -> Dict:
        """Load or initialize metrics"""
        if self.metrics_file.exists():
            with open(self.metrics_file) as f:
                return json.load(f)
        return {
            "total_paragraphs": 0,
            "refined_count": 0,
            "validation_passed": 0,
            "validation_failed": 0,
            "avg_readability_improvement": 0.0,
            "total_iterations": 0
        }

    def _load_history(self) -> List:
        """Load or initialize history"""
        if self.history_file.exists():
            with open(self.history_file) as f:
                return json.load(f)
        return []

    def _save_metrics(self):
        """Persist metrics"""
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)

    def _save_history(self):
        """Persist history"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def extract_paragraphs(self, text: str, source_id: str) -> List[ParagraphContext]:
        """
        Extract paragraphs from text

        Args:
            text: Full text to extract from
            source_id: Identifier for source document

        Returns:
            List of ParagraphContext objects
        """
        # Split by double newlines or paragraph markers
        paragraphs = re.split(r'\n\n+', text.strip())

        contexts = []
        for idx, para in enumerate(paragraphs):
            if para.strip():  # Skip empty
                context = ParagraphContext(
                    index=idx,
                    text=para.strip(),
                    original_text=para.strip(),
                    source_id=source_id
                )
                contexts.append(context)

        self.metrics["total_paragraphs"] = len(contexts)
        self._save_metrics()

        return contexts

    def select_paragraphs_for_refinement(
        self,
        paragraphs: List[ParagraphContext],
        criteria: Dict
    ) -> List[ParagraphContext]:
        """
        Select paragraphs matching refinement criteria

        Args:
            paragraphs: List of paragraph contexts
            criteria: Dict with keys:
                - min_readability: minimum readability score (default: 30)
                - word_count_range: (min, max) tuple
                - contains_keywords: list of keywords to match

        Returns:
            Filtered list of paragraphs
        """
        min_readability = criteria.get("min_readability", 30)
        word_range = criteria.get("word_count_range", (0, 1000))
        keywords = criteria.get("contains_keywords", [])

        selected = []
        for para in paragraphs:
            # Check readability
            if para.readability_score < min_readability:
                selected.append(para)
                continue

            # Check word count
            if not (word_range[0] <= para.word_count <= word_range[1]):
                continue

            # Check keywords
            if keywords and any(kw.lower() in para.text.lower() for kw in keywords):
                selected.append(para)

        return selected

    def generate_critique(
        self,
        paragraph: ParagraphContext,
        critique_type: str = "clarity"
    ) -> str:
        """
        Generate critique for a paragraph

        Args:
            paragraph: Paragraph to critique
            critique_type: Type of critique (clarity, conciseness, accuracy, structure)

        Returns:
            Critique text
        """
        critiques = {
            "clarity": self._critique_clarity,
            "conciseness": self._critique_conciseness,
            "accuracy": self._critique_accuracy,
            "structure": self._critique_structure
        }

        critique_fn = critiques.get(critique_type, self._critique_clarity)
        return critique_fn(paragraph)

    def _critique_clarity(self, para: ParagraphContext) -> str:
        """Analyze clarity of paragraph"""
        text = para.text
        issues = []

        # Check for overly long sentences
        sentences = re.split(r'[.!?]+', text)
        long_sentences = [s for s in sentences if len(s.split()) > 25]
        if long_sentences:
            issues.append(f"Found {len(long_sentences)} sentences over 25 words (clarity issue)")

        # Check for passive voice
        passive_patterns = [r'\bis\b.*\bed\b', r'\bwas\b.*\bed\b', r'\bwere\b.*\bed\b']
        passive_count = sum(len(re.findall(p, text)) for p in passive_patterns)
        if passive_count > 2:
            issues.append(f"Excessive passive voice ({passive_count} instances)")

        # Check for jargon/complex terms
        complex_words = [w for w in text.split() if len(w) > 12]
        if len(complex_words) > len(text.split()) * 0.15:
            issues.append(f"High density of complex words ({len(complex_words)})")

        if not issues:
            return "Paragraph is clear and well-structured."

        return "Clarity issues found: " + "; ".join(issues)

    def _critique_conciseness(self, para: ParagraphContext) -> str:
        """Analyze conciseness of paragraph"""
        text = para.text
        redundancies = []

        # Check for repeated words
        words = text.lower().split()
        word_freq = {}
        for w in words:
            word_freq[w] = word_freq.get(w, 0) + 1

        repeated = {w: c for w, c in word_freq.items() if c > 3 and len(w) > 4}
        if repeated:
            redundancies.append(f"Repeated words: {list(repeated.keys())}")

        # Check for filler words
        fillers = ['very', 'really', 'actually', 'basically', 'basically', 'literally']
        filler_count = len([w for w in words if w in fillers])
        if filler_count > 0:
            redundancies.append(f"Found {filler_count} filler words")

        if not redundancies:
            return "Paragraph is concise and well-written."

        return "Conciseness issues: " + "; ".join(redundancies)

    def _critique_accuracy(self, para: ParagraphContext) -> str:
        """Analyze accuracy requirements (note: requires source comparison)"""
        return "Accuracy assessment requires source document comparison (see SourceValidator)"

    def _critique_structure(self, para: ParagraphContext) -> str:
        """Analyze paragraph structure"""
        issues = []

        sentences = re.split(r'[.!?]+', para.text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) < 2:
            issues.append("Paragraph is a single sentence (consider breaking up)")

        if len(sentences) > 8:
            issues.append(f"Paragraph has {len(sentences)} sentences (too many)")

        # Check topic sentence
        first_sent_len = len(sentences[0].split()) if sentences else 0
        if first_sent_len > 25:
            issues.append("Topic sentence is too long (should be clear and concise)")

        if not issues:
            return "Paragraph structure is good."

        return "Structure issues: " + "; ".join(issues)

    def apply_refinement(
        self,
        paragraph: ParagraphContext,
        refinement: str,
        critique: str
    ) -> RefinementRecord:
        """
        Record and apply a refinement to a paragraph

        Args:
            paragraph: Paragraph being refined
            refinement: The refined/improved text
            critique: The critique that led to this refinement

        Returns:
            RefinementRecord
        """
        record = RefinementRecord(
            timestamp=datetime.now().isoformat(),
            action_type="refine",
            original=paragraph.text,
            refined=refinement,
            critique=critique,
            applied=True
        )

        # Calculate readability improvement
        old_score = paragraph.readability_score
        paragraph.text = refinement
        new_score = paragraph.readability_score

        self.metrics["refined_count"] += 1
        self.metrics["avg_readability_improvement"] = (
            (self.metrics["avg_readability_improvement"] * (self.metrics["refined_count"] - 1) + (new_score - old_score))
            / self.metrics["refined_count"]
        )
        self.metrics["total_iterations"] += 1

        paragraph.refinement_history.append(record)
        self._save_metrics()

        return record

    def get_refinement_history(self, paragraph_index: int) -> List[Dict]:
        """Get refinement history for a specific paragraph"""
        result = []
        if paragraph_index < len(self.history):
            para_history = self.history[paragraph_index]
            return para_history
        return result

    def rollback_refinement(self, paragraph: ParagraphContext) -> bool:
        """
        Rollback to previous version of paragraph

        Returns:
            True if rollback successful, False if no history
        """
        if not paragraph.refinement_history:
            return False

        # Rollback to original
        paragraph.text = paragraph.original_text
        paragraph.refinement_history[-1].applied = False
        paragraph.refinement_history[-1].action_type = "rollback"

        self._save_metrics()
        return True

    def get_refinement_summary(self) -> Dict:
        """Get summary of refinements performed"""
        return {
            "total_paragraphs": self.metrics["total_paragraphs"],
            "refined": self.metrics["refined_count"],
            "refinement_rate": (
                self.metrics["refined_count"] / max(self.metrics["total_paragraphs"], 1) * 100
            ),
            "avg_readability_improvement": round(self.metrics["avg_readability_improvement"], 2),
            "validation_passed": self.metrics["validation_passed"],
            "validation_failed": self.metrics["validation_failed"],
            "total_iterations": self.metrics["total_iterations"]
        }
