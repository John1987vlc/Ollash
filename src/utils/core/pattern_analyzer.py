"""
Pattern Analyzer for Phase 3: Learning System

Analyzes feedback patterns, user behavior, and system performance
to identify trends and suggest improvements.

Key Features:
- Analyze feedback quality and sentiment
- Detect behavioral patterns
- Identify successful approaches
- Track performance metrics
- Generate improvement suggestions
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import statistics


logger = logging.getLogger(__name__)


class SentimentType:
    """Sentiment classification."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class FeedbackEntry:
    """Single feedback entry."""
    timestamp: str
    user_id: str
    task_type: str  # "analysis", "artifact_creation", "decision_recording"
    sentiment: str  # positive, neutral, negative
    score: float  # 1-5
    comment: str = ""
    keywords: List[str] = field(default_factory=list)
    affected_component: str = ""  # Which component improvement needed
    resolution_time: float = 0.0  # Time to resolve in seconds


@dataclass
class Pattern:
    """Identified pattern."""
    pattern_id: str
    pattern_type: str  # "success", "failure", "inefficiency"
    frequency: int
    confidence: float  # 0-1
    description: str
    affected_components: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    first_seen: str = field(default_factory=lambda: datetime.now().isoformat())
    last_seen: str = field(default_factory=lambda: datetime.now().isoformat())


class PatternAnalyzer:
    """
    Analyzes patterns in user feedback and system behavior.
    
    Responsibilities:
    - Collect and categorize feedback
    - Detect patterns in user interactions
    - Identify success/failure trends
    - Generate recommendations
    - Track component performance
    """
    
    def __init__(self, workspace_root: Path = None):
        """
        Initialize pattern analyzer.
        
        Args:
            workspace_root: Root path for data storage
        """
        self.workspace_root = workspace_root or Path.cwd()
        self.data_dir = self.workspace_root / "knowledge_workspace" / "patterns"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.feedback_file = self.data_dir / "feedback_entries.json"
        self.patterns_file = self.data_dir / "detected_patterns.json"
        self.metrics_file = self.data_dir / "performance_metrics.json"
        
        self._feedback_entries: List[FeedbackEntry] = []
        self._patterns: Dict[str, Pattern] = {}
        self._metrics: Dict[str, Any] = defaultdict(list)
        
        self._load_data()
    
    def _load_data(self):
        """Load stored data from disk."""
        try:
            if self.feedback_file.exists():
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._feedback_entries = [
                        FeedbackEntry(**entry) for entry in data.get("entries", [])
                    ]
            
            if self.patterns_file.exists():
                with open(self.patterns_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._patterns = {
                        pid: Pattern(**p) for pid, p in data.get("patterns", {}).items()
                    }
            
            if self.metrics_file.exists():
                with open(self.metrics_file, 'r', encoding='utf-8') as f:
                    self._metrics = json.load(f)
        except Exception as e:
            logger.error(f"Error loading pattern data: {e}")
    
    def _save_data(self):
        """Save data to disk."""
        try:
            # Save feedback
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(
                    {"entries": [asdict(e) for e in self._feedback_entries]},
                    f, indent=2, ensure_ascii=False
                )
            
            # Save patterns
            with open(self.patterns_file, 'w', encoding='utf-8') as f:
                json.dump(
                    {"patterns": {pid: asdict(p) for pid, p in self._patterns.items()}},
                    f, indent=2, ensure_ascii=False
                )
            
            # Save metrics
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(dict(self._metrics), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving pattern data: {e}")
    
    def record_feedback(
        self,
        user_id: str,
        task_type: str,
        sentiment: str,
        score: float,
        comment: str = "",
        keywords: List[str] = None,
        affected_component: str = "",
        resolution_time: float = 0.0
    ) -> FeedbackEntry:
        """
        Record user feedback.
        
        Args:
            user_id: User identifier
            task_type: Type of task (analysis, artifact_creation, etc.)
            sentiment: positive, neutral, negative
            score: 1-5 score
            comment: Optional feedback comment
            keywords: Associated keywords
            affected_component: Which component needs improvement
            resolution_time: Time to resolve in seconds
            
        Returns:
            Recorded feedback entry
        """
        entry = FeedbackEntry(
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
            task_type=task_type,
            sentiment=sentiment,
            score=score,
            comment=comment,
            keywords=keywords or [],
            affected_component=affected_component,
            resolution_time=resolution_time
        )
        
        self._feedback_entries.append(entry)
        self._analyze_patterns()
        self._save_data()
        
        logger.info(f"Recorded feedback: {sentiment} score={score}")
        return entry
    
    def _analyze_patterns(self):
        """Analyze all feedback for patterns."""
        if len(self._feedback_entries) < 5:
            return  # Need minimum data
        
        # Analyze by component
        self._analyze_component_patterns()
        
        # Analyze by task type
        self._analyze_task_patterns()
        
        # Analyze sentiment trends
        self._analyze_sentiment_trends()
        
        # Analyze performance patterns
        self._analyze_performance_patterns()
    
    def _analyze_component_patterns(self):
        """Analyze patterns per component."""
        components = defaultdict(list)
        
        for entry in self._feedback_entries:
            if entry.affected_component:
                components[entry.affected_component].append(entry)
        
        for component, entries in components.items():
            if len(entries) >= 3:
                scores = [e.score for e in entries]
                avg_score = statistics.mean(scores)
                
                # Create pattern
                if avg_score < 2.5:
                    pattern_type = "failure"
                    severity = "critical"
                elif avg_score < 3.5:
                    pattern_type = "inefficiency"
                    severity = "warning"
                else:
                    pattern_type = "success"
                    severity = "info"
                
                pattern_id = f"comp_{component}_{datetime.now().timestamp()}"
                pattern = Pattern(
                    pattern_id=pattern_id,
                    pattern_type=pattern_type,
                    frequency=len(entries),
                    confidence=min(1.0, len(entries) / 10),
                    description=f"{component} component: {severity} - Avg score: {avg_score:.2f}",
                    affected_components=[component],
                    recommendations=self._suggest_improvements(component, entries)
                )
                
                self._patterns[pattern_id] = pattern
    
    def _analyze_task_patterns(self):
        """Analyze patterns per task type."""
        tasks = defaultdict(list)
        
        for entry in self._feedback_entries:
            tasks[entry.task_type].append(entry)
        
        for task_type, entries in tasks.items():
            if len(entries) >= 3:
                scores = [e.score for e in entries]
                avg_score = statistics.mean(scores)
                
                positive_count = sum(1 for e in entries if e.sentiment == SentimentType.POSITIVE)
                success_rate = positive_count / len(entries)
                
                pattern_id = f"task_{task_type}_{datetime.now().timestamp()}"
                pattern = Pattern(
                    pattern_id=pattern_id,
                    pattern_type="success" if success_rate > 0.7 else "inefficiency",
                    frequency=len(entries),
                    confidence=success_rate,
                    description=f"Task type '{task_type}': {success_rate*100:.0f}% success rate",
                    recommendations=self._suggest_task_improvements(task_type, entries)
                )
                
                self._patterns[pattern_id] = pattern
    
    def _analyze_sentiment_trends(self):
        """Analyze sentiment over time."""
        if not self._feedback_entries:
            return
        
        # Get last 20 entries
        recent = self._feedback_entries[-20:]
        sentiments = [e.sentiment for e in recent]
        sentiment_counts = Counter(sentiments)
        
        # Check if there's a negative trend
        recent_negative = sum(1 for e in recent[-5:] if e.sentiment == SentimentType.NEGATIVE)
        
        if recent_negative >= 3:  # 3 or more negative in last 5
            pattern = Pattern(
                pattern_id=f"trend_negative_{datetime.now().timestamp()}",
                pattern_type="failure",
                frequency=recent_negative,
                confidence=0.8,
                description="Recent negative feedback trend detected",
                recommendations=["Review recent changes", "Increase testing", "Gather more feedback"]
            )
            self._patterns[pattern.pattern_id] = pattern
    
    def _analyze_performance_patterns(self):
        """Analyze performance metric patterns."""
        resolution_times = [
            e.resolution_time for e in self._feedback_entries
            if e.resolution_time > 0
        ]
        
        if len(resolution_times) >= 3:
            avg_time = statistics.mean(resolution_times)
            max_time = max(resolution_times)
            
            if avg_time > 10.0:  # More than 10 seconds average
                pattern = Pattern(
                    pattern_id=f"perf_slowness_{datetime.now().timestamp()}",
                    pattern_type="inefficiency",
                    frequency=len(resolution_times),
                    confidence=0.7,
                    description=f"Slow resolution times: avg {avg_time:.2f}s, max {max_time:.2f}s",
                    recommendations=["Optimize queries", "Add caching", "Profile bottlenecks"]
                )
                self._patterns[pattern.pattern_id] = pattern
    
    def _suggest_improvements(self, component: str, entries: List[FeedbackEntry]) -> List[str]:
        """Suggest improvements for component."""
        suggestions = []
        
        # Analyze keywords
        all_keywords = []
        for entry in entries:
            all_keywords.extend(entry.keywords)
        keyword_counts = Counter(all_keywords)
        
        # Common issues
        issue_keywords = {}
        for kw, count in keyword_counts.most_common(3):
            if count >= 2:
                issue_keywords[kw] = count
        
        # Base suggestions
        suggestion_map = {
            "performance": "Optimize component performance",
            "clarity": "Improve output clarity and readability",
            "accuracy": "Increase accuracy of results",
            "speed": "Reduce processing time",
            "usability": "Improve user experience",
            "error": "Better error handling and messages"
        }
        
        for keyword, count in issue_keywords.items():
            if keyword in suggestion_map:
                suggestions.append(suggestion_map[keyword])
        
        if not suggestions:
            suggestions.append(f"Review and refactor {component}")
        
        return suggestions[:3]  # Top 3 suggestions
    
    def _suggest_task_improvements(self, task_type: str, entries: List[FeedbackEntry]) -> List[str]:
        """Suggest improvements for task type."""
        suggestions = []
        
        failures = [e for e in entries if e.sentiment == SentimentType.NEGATIVE]
        if failures:
            if len(failures) >= len(entries) * 0.5:  # More than 50% failures
                suggestions.append(f"Redesign {task_type} workflow")
            
            # Analyze error comments
            for failure in failures[:2]:
                if failure.comment:
                    suggestions.append(f"Address: {failure.comment[:50]}")
        
        return suggestions[:3]
    
    def get_patterns(
        self,
        pattern_type: str = None,
        min_confidence: float = 0.5,
        limit: int = 10
    ) -> List[Pattern]:
        """
        Get detected patterns.
        
        Args:
            pattern_type: Filter by type (success, failure, inefficiency)
            min_confidence: Minimum confidence threshold
            limit: Maximum results
            
        Returns:
            List of patterns
        """
        patterns = list(self._patterns.values())
        
        # Filter
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        
        patterns = [p for p in patterns if p.confidence >= min_confidence]
        
        # Sort by confidence and frequency
        patterns.sort(key=lambda p: (p.confidence, p.frequency), reverse=True)
        
        return patterns[:limit]
    
    def get_insights(self) -> Dict[str, Any]:
        """
        Generate overall insights.
        
        Returns:
            Dictionary of insights
        """
        if not self._feedback_entries:
            return {"message": "No feedback data available"}
        
        recent = self._feedback_entries[-20:]
        
        # Calculate statistics
        scores = [e.score for e in recent]
        avg_score = statistics.mean(scores)
        
        sentiments = Counter(e.sentiment for e in recent)
        positive_pct = (sentiments[SentimentType.POSITIVE] / len(recent)) * 100
        
        # Components with issues
        failing_components = defaultdict(list)
        for entry in recent:
            if entry.sentiment == SentimentType.NEGATIVE and entry.affected_component:
                failing_components[entry.affected_component].append(entry)
        
        # Top keywords
        all_keywords = []
        for entry in recent:
            all_keywords.extend(entry.keywords)
        top_keywords = Counter(all_keywords).most_common(5)
        
        return {
            "total_feedback_entries": len(self._feedback_entries),
            "average_score": round(avg_score, 2),
            "positive_feedback_percentage": round(positive_pct, 1),
            "sentiment_distribution": dict(sentiments),
            "failing_components": {
                comp: len(entries) for comp, entries in failing_components.items()
            },
            "top_keywords": [kw for kw, count in top_keywords],
            "detected_patterns": len(self._patterns),
            "critical_patterns": len(self.get_patterns("failure", min_confidence=0.7)),
            "recommendations": [
                p.description for p in self.get_patterns(limit=3)
            ]
        }
    
    def get_component_health(self, component: str) -> Dict[str, Any]:
        """
        Get health status of specific component.
        
        Args:
            component: Component name
            
        Returns:
            Health metrics
        """
        entries = [
            e for e in self._feedback_entries
            if e.affected_component == component
        ]
        
        if not entries:
            return {"status": "unknown", "entries": 0}
        
        scores = [e.score for e in entries]
        avg_score = statistics.mean(scores)
        
        # Status interpretation
        if avg_score >= 4.0:
            status = "healthy"
        elif avg_score >= 3.0:
            status = "acceptable"
        else:
            status = "degraded"
        
        return {
            "component": component,
            "status": status,
            "average_score": round(avg_score, 2),
            "entries": len(entries),
            "positive_feedback": sum(1 for e in entries if e.sentiment == SentimentType.POSITIVE),
            "negative_feedback": sum(1 for e in entries if e.sentiment == SentimentType.NEGATIVE)
        }
    
    def export_report(self, format: str = "json") -> str:
        """
        Export analysis report.
        
        Args:
            format: json or markdown
            
        Returns:
            Formatted report
        """
        insights = self.get_insights()
        patterns = self.get_patterns(limit=10)
        
        if format == "json":
            return json.dumps({
                "insights": insights,
                "patterns": [asdict(p) for p in patterns]
            }, indent=2, ensure_ascii=False)
        
        elif format == "markdown":
            md = "# Pattern Analysis Report\n\n"
            md += f"**Generated**: {datetime.now().isoformat()}\n\n"
            
            md += "## Key Insights\n"
            md += f"- Total Feedback Entries: {insights.get('total_feedback_entries', 0)}\n"
            md += f"- Average Score: {insights.get('average_score', 0)}/5\n"
            md += f"- Positive Feedback: {insights.get('positive_feedback_percentage', 0)}%\n"
            md += f"- Detected Patterns: {insights.get('detected_patterns', 0)}\n\n"
            
            md += "## Top Patterns\n"
            for i, pattern in enumerate(patterns, 1):
                md += f"\n### {i}. {pattern.description}\n"
                md += f"- Type: {pattern.pattern_type}\n"
                md += f"- Confidence: {pattern.confidence*100:.0f}%\n"
                if pattern.recommendations:
                    md += f"- Recommendations:\n"
                    for rec in pattern.recommendations:
                        md += f"  - {rec}\n"
            
            return md
        
        return ""
