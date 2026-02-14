"""
Error Knowledge Base for Long-term Learning

Stores and retrieves learned patterns from code generation failures
to prevent repeating the same mistakes across projects.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from backend.utils.core.agent_logger import AgentLogger


@dataclass
class ErrorPattern:
    """Represents a learned error pattern."""
    pattern_id: str
    error_type: str  # syntax, logic, compatibility, semantic, etc.
    affected_file_type: str  # .py, .js, .go, etc.
    description: str
    example_error: str
    prevention_tip: str
    solution_template: str
    language: str
    frequency: int = 1  # How many times this error was encountered
    severity: str = "medium"  # low, medium, critical
    last_encountered: str = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.last_encountered is None:
            self.last_encountered = datetime.now().isoformat()
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pattern_id": self.pattern_id,
            "error_type": self.error_type,
            "affected_file_type": self.affected_file_type,
            "description": self.description,
            "example_error": self.example_error,
            "prevention_tip": self.prevention_tip,
            "solution_template": self.solution_template,
            "language": self.language,
            "frequency": self.frequency,
            "severity": self.severity,
            "last_encountered": self.last_encountered,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ErrorPattern":
        """Create from dictionary."""
        return cls(**data)


class ErrorKnowledgeBase:
    """
    Manages a persistent knowledge base of error patterns.
    
    Used to:
    - Prevent recurring errors during code generation
    - Provide prevention tips to the LLM before generating files
    - Track error trends and patterns
    - Build immunity to common mistakes
    """
    
    def __init__(
        self,
        knowledge_dir: Path,
        logger: AgentLogger,
        enable_persistence: bool = True
    ):
        """
        Initialize error knowledge base.
        
        Args:
            knowledge_dir: Directory to store knowledge files
            logger: Logger instance
            enable_persistence: If True, persist to disk
        """
        self.knowledge_dir = Path(knowledge_dir)
        self.logger = logger
        self.enable_persistence = enable_persistence
        
        # In-memory storage
        self.patterns: Dict[str, ErrorPattern] = {}
        self.kb_file = self.knowledge_dir / ".error_patterns.json"
        
        if self.enable_persistence:
            self.knowledge_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()
    
    def record_error(
        self,
        file_path: str,
        error_type: str,
        error_message: str,
        file_content: str,
        context: str = "",
        solution: Optional[str] = None,
    ) -> str:
        """
        Record an error for learning.
        
        Args:
            file_path: Path to file that had error
            error_type: Type of error (syntax, logic, etc.)
            error_message: The error message
            file_content: Content of the file that failed
            context: Additional context
            solution: Solution applied (if any)
        
        Returns:
            Pattern ID of the recorded error
        """
        pattern_id = self._generate_pattern_id(error_message, file_content)
        
        # Check if pattern already exists
        if pattern_id in self.patterns:
            self.patterns[pattern_id].frequency += 1
            self.patterns[pattern_id].last_encountered = datetime.now().isoformat()
            self.logger.debug(f"Updated error pattern {pattern_id} (frequency: {self.patterns[pattern_id].frequency})")
        else:
            # Create new pattern
            language = self._detect_language(file_path)
            file_type = Path(file_path).suffix
            
            pattern = ErrorPattern(
                pattern_id=pattern_id,
                error_type=error_type,
                affected_file_type=file_type,
                description=f"Error in {file_path}: {error_message[:200]}",
                example_error=error_message[:500],
                prevention_tip=self._generate_prevention_tip(error_type, error_message),
                solution_template=solution or "Review error message and fix code",
                language=language,
                tags=self._generate_tags(error_type, error_message),
            )
            
            self.patterns[pattern_id] = pattern
            self.logger.info(f"Recorded new error pattern: {pattern_id}")
        
        if self.enable_persistence:
            self._save_to_disk()
        
        return pattern_id
    
    def query_similar_errors(
        self,
        file_path: str,
        language: str,
        error_type: Optional[str] = None,
        max_results: int = 5
    ) -> List[ErrorPattern]:
        """
        Find similar error patterns for prevention.
        
        Args:
            file_path: File being generated
            language: Programming language
            error_type: Optional error type filter
            max_results: Max patterns to return
        
        Returns:
            List of relevant ErrorPatterns
        """
        candidates = []
        
        for pattern in self.patterns.values():
            # Filter by language and file type
            if pattern.language != language:
                continue
            
            if error_type and pattern.error_type != error_type:
                continue
            
            # Score based on relevance and frequency
            score = pattern.frequency * (1 + len(pattern.tags) * 0.1)
            candidates.append((score, pattern))
        
        # Sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        return [p for _, p in candidates[:max_results]]
    
    def get_prevention_warnings(
        self,
        file_path: str,
        project_type: str,
        language: str,
    ) -> str:
        """
        Get prevention warnings to include in LLM prompt.
        
        Returns a formatted string with common error patterns to avoid.
        """
        similar = self.query_similar_errors(file_path, language, max_results=3)
        
        if not similar:
            return ""
        
        warnings = [
            "Based on past issues, be careful to avoid:",
            ""
        ]
        
        for i, pattern in enumerate(similar, 1):
            warnings.append(f"{i}. [{pattern.severity.upper()}] {pattern.description}")
            warnings.append(f"   Prevention: {pattern.prevention_tip}")
            warnings.append("")
        
        return "\n".join(warnings)
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get statistics about recorded errors."""
        if not self.patterns:
            return {"total": 0, "by_type": {}, "by_language": {}, "by_severity": {}}
        
        by_type = {}
        by_language = {}
        by_severity = {}
        
        for pattern in self.patterns.values():
            # By error type
            by_type[pattern.error_type] = by_type.get(pattern.error_type, 0) + pattern.frequency
            
            # By language
            by_language[pattern.language] = by_language.get(pattern.language, 0) + pattern.frequency
            
            # By severity
            by_severity[pattern.severity] = by_severity.get(pattern.severity, 0) + pattern.frequency
        
        total_errors = sum(p.frequency for p in self.patterns.values())
        
        return {
            "total_patterns": len(self.patterns),
            "total_errors": total_errors,
            "by_type": by_type,
            "by_language": by_language,
            "by_severity": by_severity,
        }
    
    def export_knowledge(self, output_file: Path) -> None:
        """Export knowledge base for inspection/backup."""
        data = {
            "exported_at": datetime.now().isoformat(),
            "total_patterns": len(self.patterns),
            "patterns": [p.to_dict() for p in self.patterns.values()],
        }
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        self.logger.info(f"Knowledge base exported to {output_file}")
    
    def _generate_pattern_id(self, error_msg: str, file_content: str) -> str:
        """Generate unique ID for error pattern."""
        combined = f"{error_msg[:100]}{file_content[:100]}"
        return hashlib.md5(combined.encode()).hexdigest()[:12]
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".cpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
        }
        return lang_map.get(ext, "unknown")
    
    def _generate_prevention_tip(self, error_type: str, error_msg: str) -> str:
        """Generate prevention tip based on error type."""
        tips = {
            "syntax": "Check code syntax carefully, especially parentheses, quotes, and indentation",
            "import": "Ensure all imported modules are available and paths are correct",
            "logic": "Validate algorithm logic, edge cases, and variable scope",
            "type": "Ensure type compatibility between variables and operations",
            "compatibility": "Check API version compatibility and deprecated features",
            "semantic": "Ensure code semantics match the intended behavior",
            "circular": "Avoid circular imports/dependencies - import carefully",
            "undefined": "Ensure all variables and functions are defined before use",
        }
        return tips.get(error_type, "Review error carefully and test thoroughly")
    
    def _generate_tags(self, error_type: str, error_msg: str) -> List[str]:
        """Generate tags for error pattern."""
        tags = [error_type]
        
        # Add contextual tags
        error_lower = error_msg.lower()
        
        if "import" in error_lower:
            tags.append("import")
        if "undefined" in error_lower or "not defined" in error_lower:
            tags.append("undefined")
        if "syntax" in error_lower:
            tags.append("syntax")
        if "type" in error_lower:
            tags.append("type")
        if "circular" in error_lower:
            tags.append("circular")
        if "async" in error_lower or "await" in error_lower:
            tags.append("async")
        
        return tags
    
    def _save_to_disk(self) -> None:
        """Persist knowledge base to disk."""
        if not self.enable_persistence:
            return
        
        try:
            data = {
                "saved_at": datetime.now().isoformat(),
                "patterns": {k: v.to_dict() for k, v in self.patterns.items()}
            }
            
            with open(self.kb_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            self.logger.warning(f"Failed to save error knowledge base: {e}")
    
    def _load_from_disk(self) -> None:
        """Load knowledge base from disk."""
        if not self.kb_file.exists():
            return
        
        try:
            with open(self.kb_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for pattern_id, pattern_data in data.get("patterns", {}).items():
                self.patterns[pattern_id] = ErrorPattern.from_dict(pattern_data)
            
            self.logger.info(f"Loaded {len(self.patterns)} error patterns from disk")
        except Exception as e:
            self.logger.warning(f"Failed to load error knowledge base: {e}")
            self.patterns = {}


from dataclasses import dataclass
