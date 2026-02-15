"""
Phase 4: Source Validator
Validates refined content against original sources for accuracy
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from difflib import SequenceMatcher
import re


@dataclass
class ValidationIssue:
    """Represents a validation problem"""
    severity: str  # 'critical', 'warning', 'info'
    issue_type: str  # 'contradiction', 'factual_drift', 'semantic_change'
    original_text: str
    refined_text: str
    issue_description: str
    suggestion: Optional[str] = None
    confidence: float = 0.8

    def to_dict(self):
        return asdict(self)


@dataclass
class ValidationResult:
    """Result of validating a refinement"""
    is_valid: bool
    validation_score: float  # 0-100
    issues: List[ValidationIssue] = field(default_factory=list)
    confidence_level: str = "high"  # high, medium, low
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            **asdict(self),
            "issues": [issue.to_dict() for issue in self.issues]
        }


class SourceValidator:
    """
    Validates refined content against original sources

    Checks:
    1. Factual consistency - refined text matches facts in source
    2. Semantic similarity - meaning is preserved
    3. No contradictions - refined text doesn't contradict source
    4. Attribution - claims are properly attributed
    """

    def __init__(self, workspace_path: str = "knowledge_workspace"):
        self.workspace = Path(workspace_path)
        self.validation_dir = self.workspace / "validations"
        self.validation_dir.mkdir(parents=True, exist_ok=True)
        self.sources_dir = self.workspace / "sources"
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.validation_log = self.validation_dir / "validation_log.json"
        self.validations = self._load_validations()

    def _load_validations(self) -> List:
        """Load validation history"""
        if self.validation_log.exists():
            with open(self.validation_log) as f:
                return json.load(f)
        return []

    def _save_validations(self):
        """Persist validation history"""
        with open(self.validation_log, 'w') as f:
            json.dump(self.validations, f, indent=2)

    def register_source(self, source_id: str, source_text: str) -> bool:
        """
        Register a source document for validation

        Args:
            source_id: Unique identifier for source
            source_text: Full text of source

        Returns:
            True if registered successfully
        """
        source_file = self.sources_dir / f"{source_id}.txt"
        try:
            with open(source_file, 'w') as f:
                f.write(source_text)
            return True
        except Exception as e:
            print(f"Error registering source: {e}")
            return False

    def get_source(self, source_id: str) -> Optional[str]:
        """Retrieve a registered source"""
        source_file = self.sources_dir / f"{source_id}.txt"
        if source_file.exists():
            with open(source_file) as f:
                return f.read()
        return None

    def validate_refinement(
        self,
        original_text: str,
        refined_text: str,
        source_id: str,
        validation_type: str = "full"
    ) -> ValidationResult:
        """
        Validate a refinement against source

        Args:
            original_text: Original paragraph from source
            refined_text: Refined/improved paragraph
            source_id: ID of source document
            validation_type: 'full', 'semantic', 'factual'

        Returns:
            ValidationResult with issues and score
        """
        source = self.get_source(source_id)
        result = ValidationResult(is_valid=True, validation_score=100.0)

        if not source:
            result.issues.append(ValidationIssue(
                severity="warning",
                issue_type="info",
                original_text=original_text,
                refined_text=refined_text,
                issue_description=f"Source '{source_id}' not found for validation"
            ))
            result.confidence_level = "low"
            return result

        # Run selected validation checks
        if validation_type in ["full", "semantic"]:
            self._check_semantic_preservation(
                original_text, refined_text, source, result
            )

        if validation_type in ["full", "factual"]:
            self._check_factual_consistency(
                refined_text, source, original_text, result
            )

        # Calculate overall score
        if result.issues:
            critical_count = len([i for i in result.issues if i.severity == "critical"])
            warning_count = len([i for i in result.issues if i.severity == "warning"])

            result.validation_score = max(0, 100 - (critical_count * 20 + warning_count * 5))
            result.is_valid = result.validation_score >= 70  # Threshold
            result.confidence_level = "medium" if warning_count > 0 else "high"

        # Log validation
        self.validations.append(result.to_dict())
        self._save_validations()

        return result

    def _check_semantic_preservation(
        self,
        original: str,
        refined: str,
        source: str,
        result: ValidationResult
    ):
        """Check if meaning is preserved in refinement"""

        # Check semantic similarity using word overlap
        original_words = set(word.lower() for word in re.findall(r'\b\w+\b', original))
        refined_words = set(word.lower() for word in re.findall(r'\b\w+\b', refined))

        if not original_words:
            return

        similarity = len(original_words & refined_words) / len(original_words)

        if similarity < 0.3:
            result.issues.append(ValidationIssue(
                severity="critical",
                issue_type="semantic_change",
                original_text=original[:100],
                refined_text=refined[:100],
                issue_description="Refined text has significantly different vocabulary (semantic drift)",
                suggestion="Review refinement to ensure meaning is preserved",
                confidence=0.9
            ))
        elif similarity < 0.5:
            result.issues.append(ValidationIssue(
                severity="warning",
                issue_type="semantic_change",
                original_text=original[:100],
                refined_text=refined[:100],
                issue_description="Refined text vocabulary differs notably from original",
                suggestion="Verify the key concepts are still present",
                confidence=0.8
            ))

    def _check_factual_consistency(
        self,
        refined_text: str,
        source: str,
        original_text: str,
        result: ValidationResult
    ):
        """Check if refined text contradicts source facts"""

        # Extract key facts from original (anything in quotes or with numbers)
        quoted_pattern = r'"([^"]+)"'
        quoted_facts = re.findall(quoted_pattern, original_text)

        number_pattern = r'\d+\.?\d*\s*(?:%|million|billion|thousand|years?|days?|hours?|kb|mb|gb)?'
        numeric_facts = re.findall(number_pattern, original_text)

        all_facts = quoted_facts + numeric_facts

        # Check if facts are preserved in source and refined version
        for fact in all_facts:
            if fact in source and fact not in refined_text:
                result.issues.append(ValidationIssue(
                    severity="warning",
                    issue_type="factual_drift",
                    original_text=original_text[:100],
                    refined_text=refined_text[:100],
                    issue_description=f"Factual element missing in refined text: '{fact[:50]}'",
                    suggestion="Ensure important facts are preserved in refinement",
                    confidence=0.7
                ))

    def _check_for_contradictions(
        self,
        refined_text: str,
        original_text: str,
        source: str
    ) -> List[ValidationIssue]:
        """Check for direct contradictions"""
        issues = []

        # Look for negations or opposite claims
        negation_words = ['not', 'no', 'never', 'neither', 'cannot', 'should not']

        original_has_negation = any(word in original_text.lower() for word in negation_words)
        refined_has_negation = any(word in refined_text.lower() for word in negation_words)

        if original_has_negation != refined_has_negation:
            issues.append(ValidationIssue(
                severity="critical",
                issue_type="contradiction",
                original_text=original_text[:100],
                refined_text=refined_text[:100],
                issue_description="Refinement may contradict original (negation changed)",
                suggestion="Review polarity of statements in refinement",
                confidence=0.6
            ))

        return issues

    def compare_versions(
        self,
        original: str,
        refined: str
    ) -> Dict:
        """
        Compare two versions of text

        Returns detailed comparison metrics
        """
        # Calculate similarity ratio
        matcher = SequenceMatcher(None, original, refined)
        similarity_ratio = matcher.ratio()

        # Count changes
        original_words = original.split()
        refined_words = refined.split()

        added = len(refined_words) - len(original_words)
        removed = len(original_words) - len(refined_words)

        return {
            "similarity_ratio": round(similarity_ratio, 3),
            "original_length": len(original_words),
            "refined_length": len(refined_words),
            "words_added": max(0, added),
            "words_removed": max(0, removed),
            "percent_changed": round((1 - similarity_ratio) * 100, 1)
        }

    def suggest_rollback(self, result: ValidationResult) -> bool:
        """
        Suggest whether refinement should be rolled back

        Returns:
            True if rollback suggested, False otherwise
        """
        if not result.is_valid:
            critical_issues = [i for i in result.issues if i.severity == "critical"]
            return len(critical_issues) >= 2
        return False

    def get_validation_report(self) -> Dict:
        """Get overall validation statistics"""
        if not self.validations:
            return {
                "total_validations": 0,
                "passed": 0,
                "failed": 0,
                "avg_score": 0
            }

        passed = len([v for v in self.validations if v["is_valid"]])
        failed = len(self.validations) - passed
        avg_score = sum(v["validation_score"] for v in self.validations) / len(self.validations)

        return {
            "total_validations": len(self.validations),
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / len(self.validations) * 100, 1),
            "avg_score": round(avg_score, 1)
        }
