"""Post-mortem analysis and automatic learning from successful corrections.

After the Senior Review phase (phase 8) of Auto Agent, this module extracts
successful correction patterns and indexes them in ChromaDB for future reuse.

Design: Automatic knowledge capture from each project's failure→success cycles.
Benefit: Agent learns from its own corrections in real-time.
"""

import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import hashlib
from dataclasses import dataclass

try:
    import chromadb
except ImportError:
    chromadb = None

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.chroma_manager import ChromaClientManager


@dataclass
class CorrectionPattern:
    """Captures a successful correction pattern for learning."""

    error_signature: str  # Hash of error message
    error_message: str
    error_type: str  # SyntaxError, IndentationError, etc.
    file_path: str
    language: str
    initial_code: str
    corrected_code: str
    correction_steps: List[str]  # Description of what was fixed
    success_metrics: Dict  # Quality score, syntax validation, etc.
    timestamp: str
    project_name: str
    phase: str  # Which auto_agent phase this occurred in


class PostMortemAnalyzer:
    """Analyzes failed→succeeded cycles to extract learnable patterns."""

    def __init__(self, logger: AgentLogger, project_root: Path):
        self.logger = logger
        self.project_root = project_root
        self.postmortem_dir = project_root / ".ollash" / "postmortems"
        self.postmortem_dir.mkdir(parents=True, exist_ok=True)

    def analyze_correction(
        self,
        error_message: str,
        error_type: str,
        file_path: str,
        language: str,
        initial_code: str,
        corrected_code: str,
        correction_steps: List[str],
        success_metrics: Dict,
        phase: str,
        project_name: str,
    ) -> CorrectionPattern:
        """Create a correction pattern from a successful fix.
        
        Args:
            error_message: Original error message
            error_type: Type of error (SyntaxError, etc.)
            file_path: Path to file that had error
            language: Programming language
            initial_code: Code before correction
            corrected_code: Code after successful correction
            correction_steps: Human-readable steps taken
            success_metrics: Validation results
            phase: Which auto_agent phase
            project_name: Project this occurred in
            
        Returns:
            CorrectionPattern object
        """
        # Create error signature (truncated hash of error message)
        error_hash = hashlib.sha256(error_message.encode()).hexdigest()[:12]

        pattern = CorrectionPattern(
            error_signature=error_hash,
            error_message=error_message,
            error_type=error_type,
            file_path=file_path,
            language=language,
            initial_code=initial_code,
            corrected_code=corrected_code,
            correction_steps=correction_steps,
            success_metrics=success_metrics,
            timestamp=datetime.now().isoformat(),
            project_name=project_name,
            phase=phase,
        )

        self.logger.info(
            f"📝 Captured correction pattern: {error_type} in {file_path} "
            f"(signature: {error_hash})"
        )

        return pattern

    def save_pattern(self, pattern: CorrectionPattern) -> Path:
        """Save a correction pattern to disk."""
        filename = (
            f"{pattern.error_signature}_{pattern.project_name}_{pattern.timestamp}"
            .replace(":", "-")
        )
        file_path = self.postmortem_dir / f"{filename}.json"

        with open(file_path, "w") as f:
            json.dump(
                {
                    "error_signature": pattern.error_signature,
                    "error_message": pattern.error_message,
                    "error_type": pattern.error_type,
                    "file_path": pattern.file_path,
                    "language": pattern.language,
                    "initial_code": pattern.initial_code,
                    "corrected_code": pattern.corrected_code,
                    "correction_steps": pattern.correction_steps,
                    "success_metrics": pattern.success_metrics,
                    "timestamp": pattern.timestamp,
                    "project_name": pattern.project_name,
                    "phase": pattern.phase,
                },
                f,
                indent=2,
            )

        self.logger.info(f"  💾 Saved correction pattern to {file_path}")
        return file_path


class LearningIndexer:
    """Indexes correction patterns in ChromaDB for semantic retrieval."""

    def __init__(self, logger: AgentLogger, project_root: Path, settings_manager: dict = None):
        self.logger = logger
        self.project_root = project_root
        
        if chromadb is None:
            self.logger.warning("ChromaDB not available for learning indexing")
            self.client = None
            self.collection = None
            return

        try:
            self.client = ChromaClientManager.get_client(settings_manager or {}, project_root)
            self.collection = self.client.get_or_create_collection(
                name="correction_patterns",
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            self.logger.warning(f"Could not initialize ChromaDB for learning: {e}")
            self.client = None
            self.collection = None

    def index_pattern(self, pattern: CorrectionPattern):
        """Index a correction pattern for semantic search."""
        if self.collection is None:
            return

        # Create searchable text from pattern
        searchable = f"""
Error: {pattern.error_message}
Type: {pattern.error_type}
Language: {pattern.language}
File: {pattern.file_path}
Phase: {pattern.phase}
Steps: {' '.join(pattern.correction_steps)}

Original Code:
{pattern.initial_code}

Corrected Code:
{pattern.corrected_code}
"""

        doc_id = f"pattern_{pattern.error_signature}_{pattern.timestamp}".replace(
            ":", "-"
        )

        self.collection.add(
            ids=[doc_id],
            documents=[searchable],
            metadatas=[
                {
                    "error_signature": pattern.error_signature,
                    "error_type": pattern.error_type,
                    "language": pattern.language,
                    "file_path": pattern.file_path,
                    "phase": pattern.phase,
                    "project": pattern.project_name,
                    "timestamp": pattern.timestamp,
                }
            ],
        )

        self.logger.info(f"  🔍 Indexed pattern in learning database (id: {doc_id})")

    def find_similar_patterns(
        self,
        error_message: str,
        language: str = "",
        limit: int = 3,
    ) -> List[Dict]:
        """Find patterns similar to a current error."""
        if self.collection is None:
            return []

        query = f"Error: {error_message}"
        if language:
            query += f" Language: {language}"

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
            )

            patterns = []
            for i, doc_id in enumerate(results["ids"][0] if results["ids"] else []):
                patterns.append(
                    {
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "relevance": results["distances"][0][i]
                        if results.get("distances")
                        else 0,
                    }
                )

            return patterns
        except Exception as e:
            self.logger.warning(f"Error querying patterns: {e}")
            return []


class AutomaticLearningSystem:
    """Orchestrates post-mortem analysis and learning."""

    def __init__(self, logger: AgentLogger, project_root: Path, settings_manager: dict = None):
        self.logger = logger
        self.project_root = project_root
        self.analyzer = PostMortemAnalyzer(logger, project_root)
        self.indexer = LearningIndexer(logger, project_root, settings_manager or {})

    def process_correction(
        self,
        error_message: str,
        error_type: str,
        file_path: str,
        language: str,
        initial_code: str,
        corrected_code: str,
        correction_steps: List[str],
        success_metrics: Dict,
        phase: str,
        project_name: str,
    ) -> bool:
        """Process a successful correction and learn from it.
        
        Returns:
            True if successfully indexed, False otherwise
        """
        try:
            # Analyze
            pattern = self.analyzer.analyze_correction(
                error_message=error_message,
                error_type=error_type,
                file_path=file_path,
                language=language,
                initial_code=initial_code,
                corrected_code=corrected_code,
                correction_steps=correction_steps,
                success_metrics=success_metrics,
                phase=phase,
                project_name=project_name,
            )

            # Save
            self.analyzer.save_pattern(pattern)

            # Index
            self.indexer.index_pattern(pattern)

            self.logger.info(
                "✅ Successfully processed and indexed correction pattern"
            )
            return True

        except Exception as e:
            self.logger.error(f"Failed to process correction: {e}")
            return False

    def get_suggestions_for_error(
        self,
        error_message: str,
        language: str = "",
    ) -> List[Dict]:
        """Get past correction suggestions for a current error.
        
        Returns:
            List of similar patterns with suggestions
        """
        patterns = self.indexer.find_similar_patterns(
            error_message=error_message,
            language=language,
            limit=5,
        )

        if not patterns:
            self.logger.info("No similar past corrections found")
            return []

        self.logger.info(
            f"💡 Found {len(patterns)} similar correction patterns from past projects"
        )

        suggestions = []
        for pattern in patterns:
            suggestion = {
                "error_type": pattern["metadata"].get("error_type"),
                "similar_language": pattern["metadata"].get("language"),
                "previous_project": pattern["metadata"].get("project"),
                "correction_snippet": pattern["document"][:500],  # First 500 chars
                "relevance_score": pattern.get("relevance", 0),
            }
            suggestions.append(suggestion)

        return suggestions

    def generate_learning_report(self) -> Dict:
        """Generate a report of learning patterns accumulated."""
        postmortem_files = list(self.analyzer.postmortem_dir.glob("*.json"))

        error_type_count = {}
        language_count = {}
        phase_distribution = {}

        for file_path in postmortem_files:
            try:
                with open(file_path) as f:
                    pattern = json.load(f)

                error_type = pattern["error_type"]
                language = pattern["language"]
                phase = pattern["phase"]

                error_type_count[error_type] = error_type_count.get(error_type, 0) + 1
                language_count[language] = language_count.get(language, 0) + 1
                phase_distribution[phase] = phase_distribution.get(phase, 0) + 1

            except Exception as e:
                self.logger.warning(f"Failed to read pattern {file_path}: {e}")

        report = {
            "total_patterns": len(postmortem_files),
            "indexed_timestamp": datetime.now().isoformat(),
            "error_type_distribution": error_type_count,
            "language_distribution": language_count,
            "phase_distribution": phase_distribution,
            "most_common_error": max(error_type_count, key=error_type_count.get)
            if error_type_count
            else None,
        }

        self.logger.info(f"📊 Learning Report: {report['total_patterns']} patterns indexed")

        return report
