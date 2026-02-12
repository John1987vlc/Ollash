"""
Voice Command Processor - Handles voice input and converts to structured actions.

Features:
- Speech-to-text conversion via Web Speech API
- Voice command classification
- Confidence scoring
- Multi-language support
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of voice commands."""
    ADD_TASK = "add_task"
    QUERY_STATUS = "query_status"
    EXECUTE_ACTION = "execute_action"
    PROVIDE_FEEDBACK = "provide_feedback"
    CONFIGURE_SETTING = "configure_setting"
    GET_REPORT = "get_report"
    SCHEDULE_TASK = "schedule_task"
    UNKNOWN = "unknown"


class CommandConfidence(Enum):
    """Confidence levels for command recognition."""
    HIGH = "high"        # > 80%
    MEDIUM = "medium"    # 50-80%
    LOW = "low"          # < 50%


@dataclass
class VoiceCommand:
    """Structured voice command."""
    id: str
    timestamp: str
    raw_text: str
    command_type: CommandType
    confidence: float  # 0-100
    confidence_level: CommandConfidence
    parameters: Dict[str, Any]
    language: str
    original_language: str = "en"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "raw_text": self.raw_text,
            "command_type": self.command_type.value,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "parameters": self.parameters,
            "language": self.language
        }


class VoiceCommandProcessor:
    """
    Processes voice commands and converts them to structured actions.
    
    This is a backend processor that works with the Web Speech API frontend.
    The frontend sends transcribed text to these methods for processing.
    
    Features:
    - Command type classification
    - Parameter extraction
    - Confidence scoring
    - Command history tracking
    """
    
    def __init__(self):
        """Initialize the voice command processor."""
        self.command_history: List[VoiceCommand] = []
        self.max_history = 100
        self.command_patterns = self._initialize_command_patterns()
        logger.info("VoiceCommandProcessor initialized")
    
    def process_voice_input(
        self,
        transcribed_text: str,
        confidence: float = 0.0,
        language: str = "en"
    ) -> VoiceCommand:
        """
        Process transcribed voice input and classify the command.
        
        Args:
            transcribed_text: Text from speech recognition
            confidence: Speech recognition confidence (0-100)
            language: Language code (e.g., 'en', 'es', 'fr')
        
        Returns:
            VoiceCommand: Structured command object
        """
        try:
            command_id = f"voice_{datetime.now().timestamp()}"
            
            # Normalize input
            normalized_text = self._normalize_text(transcribed_text)
            
            # Classify command type
            command_type, command_confidence = self._classify_command(normalized_text)
            
            # Extract parameters based on command type
            parameters = self._extract_parameters(normalized_text, command_type)
            
            # Combine confidence scores
            final_confidence = min(confidence * 0.6 + command_confidence * 0.4, 100)
            confidence_level = self._get_confidence_level(final_confidence)
            
            # Create command object
            command = VoiceCommand(
                id=command_id,
                timestamp=datetime.now().isoformat(),
                raw_text=transcribed_text,
                command_type=command_type,
                confidence=final_confidence,
                confidence_level=confidence_level,
                parameters=parameters,
                language=language
            )
            
            # Store in history
            self.command_history.append(command)
            if len(self.command_history) > self.max_history:
                self.command_history = self.command_history[-self.max_history:]
            
            logger.info(
                f"Voice command processed: {command_type.value} "
                f"(confidence: {final_confidence:.1f}%)"
            )
            
            return command
            
        except Exception as e:
            logger.error(f"Failed to process voice input: {e}")
            # Return unknown command
            return self._create_unknown_command(transcribed_text, language)
    
    def execute_voice_command(self, command: VoiceCommand) -> Dict[str, Any]:
        """
        Execute a voice command.
        
        Args:
            command: VoiceCommand object to execute
        
        Returns:
            Dict: Execution result
        """
        try:
            # Only execute if confidence is high enough
            if command.confidence_level == CommandConfidence.LOW:
                return {
                    "success": False,
                    "message": f"Command confidence too low ({command.confidence:.1f}%). Please repeat.",
                    "require_confirmation": True
                }
            
            # Route to handler based on command type
            if command.command_type == CommandType.ADD_TASK:
                return self._execute_add_task(command)
            elif command.command_type == CommandType.QUERY_STATUS:
                return self._execute_query_status(command)
            elif command.command_type == CommandType.EXECUTE_ACTION:
                return self._execute_action(command)
            elif command.command_type == CommandType.PROVIDE_FEEDBACK:
                return self._execute_provide_feedback(command)
            elif command.command_type == CommandType.GET_REPORT:
                return self._execute_get_report(command)
            elif command.command_type == CommandType.SCHEDULE_TASK:
                return self._execute_schedule_task(command)
            else:
                return {
                    "success": False,
                    "message": f"Unknown command type: {command.command_type.value}"
                }
                
        except Exception as e:
            logger.error(f"Failed to execute voice command: {e}")
            return {
                "success": False,
                "message": f"Execution error: {str(e)}"
            }
    
    # ==================== Command Classification ====================
    
    def _classify_command(self, text: str) -> tuple[CommandType, float]:
        """
        Classify a command into a type.
        
        Returns:
            Tuple of (CommandType, confidence_score)
        """
        text_lower = text.lower()
        
        # Strong patterns for command types
        patterns_high_confidence = [
            (CommandType.ADD_TASK, ["add task", "create task", "new task", "remind me", "schedule task"]),
            (CommandType.QUERY_STATUS, ["what's", "whats", "how is", "status", "check", "is the"]),
            (CommandType.GET_REPORT, ["report", "summary", "overview", "analytics", "show me"]),
            (CommandType.PROVIDE_FEEDBACK, ["feedback", "this is too", "could be more", "should be", "is unclear"]),
            (CommandType.CONFIGURE_SETTING, ["set", "configure", "change", "update", "enable", "disable"]),
            (CommandType.SCHEDULE_TASK, ["schedule", "run in", "every", "daily", "weekly", "monthly"])
        ]
        
        # Check patterns
        for cmd_type, keywords in patterns_high_confidence:
            if any(kw in text_lower for kw in keywords):
                return cmd_type, 85.0
        
        # Medium confidence patterns
        if any(word in text_lower for word in ["execute", "run", "do", "perform"]):
            return CommandType.EXECUTE_ACTION, 70.0
        
        # Default to unknown
        return CommandType.UNKNOWN, 30.0
    
    # ==================== Parameter Extraction ====================
    
    def _extract_parameters(self, text: str, command_type: CommandType) -> Dict[str, Any]:
        """Extract parameters from voice input based on command type."""
        
        if command_type == CommandType.ADD_TASK:
            return self._extract_task_parameters(text)
        elif command_type == CommandType.QUERY_STATUS:
            return self._extract_query_parameters(text)
        elif command_type == CommandType.SCHEDULE_TASK:
            return self._extract_schedule_parameters(text)
        elif command_type == CommandType.GET_REPORT:
            return self._extract_report_parameters(text)
        elif command_type == CommandType.PROVIDE_FEEDBACK:
            return self._extract_feedback_parameters(text)
        
        return {}
    
    def _extract_task_parameters(self, text: str) -> Dict[str, Any]:
        """Extract task creation parameters."""
        return {
            "title": self._extract_quoted_string(text) or self._extract_first_sentence(text),
            "priority": self._extract_priority(text),
            "due_date": self._extract_due_date(text),
            "category": self._extract_category(text)
        }
    
    def _extract_query_parameters(self, text: str) -> Dict[str, Any]:
        """Extract query parameters."""
        return {
            "query": text,
            "metric": self._extract_metric(text),
            "time_range": self._extract_time_range(text)
        }
    
    def _extract_schedule_parameters(self, text: str) -> Dict[str, Any]:
        """Extract scheduling parameters."""
        return {
            "frequency": self._extract_frequency(text),
            "time": self._extract_time(text),
            "task_description": self._extract_first_sentence(text)
        }
    
    def _extract_report_parameters(self, text: str) -> Dict[str, Any]:
        """Extract report request parameters."""
        return {
            "report_type": self._extract_report_type(text),
            "time_range": self._extract_time_range(text),
            "format": self._extract_format(text) or "summary"
        }
    
    def _extract_feedback_parameters(self, text: str) -> Dict[str, Any]:
        """Extract feedback parameters."""
        return {
            "feedback_type": self._extract_feedback_type(text),
            "target": self._extract_target(text),
            "comment": text,
            "sentiment": self._extract_sentiment(text)
        }
    
    # ==================== Text Analysis Helpers ====================
    
    @staticmethod
    def _extract_quoted_string(text: str) -> Optional[str]:
        """Extract strings within quotes."""
        import re
        matches = re.findall(r'"([^"]+)"', text)
        return matches[0] if matches else None
    
    @staticmethod
    def _extract_first_sentence(text: str) -> str:
        """Extract the first meaningful sentence."""
        # Remove common prefixes
        prefixes = ["add task", "create task", "new task", "remind me"]
        cleaned = text
        for prefix in prefixes:
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        return cleaned[:100]  # Limit to 100 chars
    
    @staticmethod
    def _extract_priority(text: str) -> str:
        """Extract priority level."""
        text_lower = text.lower()
        if "urgent" in text_lower or "critical" in text_lower or "asap" in text_lower:
            return "critical"
        elif "high" in text_lower or "important" in text_lower:
            return "high"
        elif "low" in text_lower or "eventually" in text_lower:
            return "low"
        return "medium"
    
    @staticmethod
    def _extract_due_date(text: str) -> Optional[str]:
        """Extract due date from text."""
        text_lower = text.lower()
        
        # Simple date extraction
        date_keywords = {
            "today": "today",
            "tomorrow": "tomorrow",
            "next week": "next_week",
            "next month": "next_month",
            "end of day": "end_of_day",
            "eod": "end_of_day"
        }
        
        for keyword, value in date_keywords.items():
            if keyword in text_lower:
                return value
        
        return None
    
    @staticmethod
    def _extract_category(text: str) -> Optional[str]:
        """Extract task category."""
        categories = ["development", "testing", "documentation", "review", "deployment", "bug"]
        text_lower = text.lower()
        
        for cat in categories:
            if cat in text_lower:
                return cat
        
        return None
    
    @staticmethod
    def _extract_metric(text: str) -> Optional[str]:
        """Extract metric name from query."""
        metrics = ["cpu", "memory", "disk", "network", "latency", "error rate", "uptime"]
        text_lower = text.lower()
        
        for metric in metrics:
            if metric in text_lower:
                return metric
        
        return None
    
    @staticmethod
    def _extract_time_range(text: str) -> str:
        """Extract time range."""
        text_lower = text.lower()
        
        if "last hour" in text_lower:
            return "1hour"
        elif "last day" in text_lower or "today" in text_lower:
            return "1day"
        elif "last week" in text_lower:
            return "1week"
        elif "last month" in text_lower:
            return "1month"
        
        return "1day"  # Default
    
    @staticmethod
    def _extract_frequency(text: str) -> str:
        """Extract frequency for scheduled tasks."""
        text_lower = text.lower()
        
        if "every hour" in text_lower or "hourly" in text_lower:
            return "hourly"
        elif "every day" in text_lower or "daily" in text_lower:
            return "daily"
        elif "every week" in text_lower or "weekly" in text_lower:
            return "weekly"
        elif "every month" in text_lower or "monthly" in text_lower:
            return "monthly"
        
        return "once"  # Default
    
    @staticmethod
    def _extract_time(text: str) -> Optional[str]:
        """Extract time of day."""
        import re
        # Find time patterns like "9:00 AM" or "9 AM"
        time_pattern = r'(\d{1,2}):?(\d{2})?\s*(AM|PM|am|pm)?'
        matches = re.findall(time_pattern, text)
        
        if matches:
            h, m, period = matches[0]
            m = m or "00"
            return f"{h}:{m} {period or 'AM'}"
        
        return None
    
    @staticmethod
    def _extract_report_type(text: str) -> str:
        """Extract report type."""
        text_lower = text.lower()
        
        if "daily" in text_lower:
            return "daily_summary"
        elif "weekly" in text_lower:
            return "weekly_digest"
        elif "trend" in text_lower:
            return "performance_trend"
        elif "anomaly" in text_lower:
            return "anomaly_report"
        
        return "daily_summary"  # Default
    
    @staticmethod
    def _extract_format(text: str) -> Optional[str]:
        """Extract output format."""
        text_lower = text.lower()
        
        if "markdown" in text_lower or "mark" in text_lower:
            return "markdown"
        elif "html" in text_lower:
            return "html"
        elif "json" in text_lower:
            return "json"
        elif "text" in text_lower or "plain" in text_lower:
            return "text"
        
        return None
    
    @staticmethod
    def _extract_feedback_type(text: str) -> str:
        """Extract type of feedback."""
        text_lower = text.lower()
        
        if "too" in text_lower or "complex" in text_lower or "difficult" in text_lower:
            return "clarity"
        elif "long" in text_lower or "brief" in text_lower or "short" in text_lower:
            return "conciseness"
        elif "technical" in text_lower or "simple" in text_lower:
            return "technicality"
        
        return "general"
    
    @staticmethod
    def _extract_target(text: str) -> Optional[str]:
        """Extract feedback target (what is being reviewed)."""
        targets = ["report", "summary", "message", "notification", "error", "output"]
        text_lower = text.lower()
        
        for target in targets:
            if target in text_lower:
                return target
        
        return None
    
    @staticmethod
    def _extract_sentiment(text: str) -> str:
        """Extract sentiment from feedback."""
        text_lower = text.lower()
        
        positive_words = ["good", "great", "excellent", "nice", "love"]
        negative_words = ["bad", "poor", "terrible", "hate", "confusing"]
        
        if any(word in text_lower for word in negative_words):
            return "negative"
        elif any(word in text_lower for word in positive_words):
            return "positive"
        
        return "neutral"
    
    # ==================== Helper Methods ====================
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize transcribed text."""
        return text.strip().lower()
    
    @staticmethod
    def _get_confidence_level(confidence: float) -> CommandConfidence:
        """Get confidence level from score."""
        if confidence >= 80:
            return CommandConfidence.HIGH
        elif confidence >= 50:
            return CommandConfidence.MEDIUM
        else:
            return CommandConfidence.LOW
    
    def _initialize_command_patterns(self) -> Dict[str, List[str]]:
        """Initialize command pattern keywords."""
        return {
            CommandType.ADD_TASK.value: ["add", "create", "new", "remind", "task"],
            CommandType.QUERY_STATUS.value: ["whats", "status", "check", "how", "report"],
            CommandType.EXECUTE_ACTION.value: ["execute", "run", "perform", "do"],
            CommandType.GET_REPORT.value: ["report", "summary", "overview", "analytics"],
            CommandType.SCHEDULE_TASK.value: ["schedule", "every", "daily", "weekly"]
        }
    
    def _create_unknown_command(self, text: str, language: str) -> VoiceCommand:
        """Create an unknown command object."""
        return VoiceCommand(
            id=f"voice_{datetime.now().timestamp()}",
            timestamp=datetime.now().isoformat(),
            raw_text=text,
            command_type=CommandType.UNKNOWN,
            confidence=20.0,
            confidence_level=CommandConfidence.LOW,
            parameters={"raw_input": text},
            language=language
        )
    
    # ==================== Command Execution ====================
    
    def _execute_add_task(self, command: VoiceCommand) -> Dict[str, Any]:
        """Execute add task command."""
        return {
            "success": True,
            "action": "task_created",
            "message": f"Task created: {command.parameters.get('title', 'Untitled')}",
            "task_details": command.parameters
        }
    
    def _execute_query_status(self, command: VoiceCommand) -> Dict[str, Any]:
        """Execute status query command."""
        return {
            "success": True,
            "action": "status_fetched",
            "message": f"Fetching {command.parameters.get('metric', 'system')} status...",
            "query_details": command.parameters
        }
    
    def _execute_action(self, command: VoiceCommand) -> Dict[str, Any]:
        """Execute generic action command."""
        return {
            "success": True,
            "action": "action_executed",
            "message": "Action executed successfully",
            "action_details": command.parameters
        }
    
    def _execute_provide_feedback(self, command: VoiceCommand) -> Dict[str, Any]:
        """Execute provide feedback command."""
        return {
            "success": True,
            "action": "feedback_recorded",
            "message": "Your feedback has been recorded",
            "feedback_details": command.parameters
        }
    
    def _execute_get_report(self, command: VoiceCommand) -> Dict[str, Any]:
        """Execute get report command."""
        return {
            "success": True,
            "action": "report_generated",
            "message": f"{command.parameters.get('report_type', 'Report')} generated",
            "report_details": command.parameters
        }
    
    def _execute_schedule_task(self, command: VoiceCommand) -> Dict[str, Any]:
        """Execute schedule task command."""
        return {
            "success": True,
            "action": "task_scheduled",
            "message": f"Task scheduled {command.parameters.get('frequency', 'once')}",
            "schedule_details": command.parameters
        }
    
    # ==================== History & Diagnostics ====================
    
    def get_command_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent command history."""
        return [
            cmd.to_dict()
            for cmd in self.command_history[-limit:]
        ]
    
    def get_command_statistics(self) -> Dict[str, Any]:
        """Get statistics about processed commands."""
        if not self.command_history:
            return {
                "total_commands": 0,
                "commands_by_type": {},
                "average_confidence": 0.0,
                "high_confidence_percent": 0.0
            }
        
        total = len(self.command_history)
        by_type = {}
        
        for cmd in self.command_history:
            cmd_type = cmd.command_type.value
            by_type[cmd_type] = by_type.get(cmd_type, 0) + 1
        
        avg_confidence = sum(cmd.confidence for cmd in self.command_history) / total
        high_confidence = sum(
            1 for cmd in self.command_history
            if cmd.confidence_level == CommandConfidence.HIGH
        )
        
        return {
            "total_commands": total,
            "commands_by_type": by_type,
            "average_confidence": avg_confidence,
            "high_confidence_percent": (high_confidence / total * 100)
        }


# Global instance
_voice_processor = None


def get_voice_command_processor() -> VoiceCommandProcessor:
    """Get or create the global voice command processor instance."""
    global _voice_processor
    if _voice_processor is None:
        _voice_processor = VoiceCommandProcessor()
    return _voice_processor
