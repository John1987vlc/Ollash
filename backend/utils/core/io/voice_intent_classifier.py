"""
Advanced Voice Intent Classifier

Uses LLM-based classification for complex natural language voice commands,
extending the basic VoiceCommandProcessor with richer intent recognition.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger


# Extended command types for advanced voice control
ADVANCED_COMMAND_TYPES = {
    "NAVIGATE_FILE": "Navigate to a specific file in the project",
    "SEARCH_CODE": "Search for code patterns or symbols",
    "RUN_PHASE": "Execute a specific AutoAgent phase",
    "MODIFY_STRUCTURE": "Modify project structure or files",
    "EXPLAIN_CODE": "Explain what a piece of code does",
    "GENERATE_CODE": "Generate new code or files",
    "RUN_TESTS": "Run project tests",
    "DEPLOY_PROJECT": "Deploy or export the project",
    "SHOW_STATUS": "Show project or agent status",
    "CONFIGURE": "Change settings or configuration",
    "UNDO_ACTION": "Undo the last action",
    "HELP": "Get help or list available commands",
}


@dataclass
class ClassifiedIntent:
    """A classified voice command with extracted parameters."""

    command_type: str
    confidence: float
    parameters: Dict[str, Any]
    original_text: str
    action_description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_type": self.command_type,
            "confidence": self.confidence,
            "parameters": self.parameters,
            "original_text": self.original_text,
            "action_description": self.action_description,
        }


class VoiceIntentClassifier:
    """LLM-based intent classifier for complex voice commands.

    Extends the basic keyword-based VoiceCommandProcessor with:
    - LLM-based natural language understanding
    - Context-aware classification
    - Parameter extraction from free-form speech
    """

    def __init__(self, logger: AgentLogger, llm_client: Any = None):
        self.logger = logger
        self.llm_client = llm_client
        self._keyword_map = self._build_keyword_map()

    def _build_keyword_map(self) -> Dict[str, List[str]]:
        """Build keyword-to-command mapping for fast classification."""
        return {
            "NAVIGATE_FILE": ["open", "go to", "navigate", "show file", "find file"],
            "SEARCH_CODE": ["search", "find", "where is", "look for", "grep"],
            "RUN_PHASE": ["run phase", "execute phase", "start phase", "generate"],
            "MODIFY_STRUCTURE": ["create", "delete", "rename", "move", "add file", "remove"],
            "EXPLAIN_CODE": ["explain", "what does", "how does", "describe"],
            "GENERATE_CODE": ["generate", "write", "create code", "implement"],
            "RUN_TESTS": ["run tests", "test", "testing", "check tests"],
            "DEPLOY_PROJECT": ["deploy", "export", "publish", "upload"],
            "SHOW_STATUS": ["status", "progress", "show", "list"],
            "CONFIGURE": ["set", "change", "configure", "update setting"],
            "UNDO_ACTION": ["undo", "revert", "rollback", "cancel"],
            "HELP": ["help", "what can", "commands", "how do I"],
        }

    def classify_keyword(self, text: str) -> ClassifiedIntent:
        """Fast keyword-based classification (no LLM needed)."""
        text_lower = text.lower().strip()
        best_match = "HELP"
        best_confidence = 0.3
        parameters: Dict[str, Any] = {}

        for cmd_type, keywords in self._keyword_map.items():
            for keyword in keywords:
                if keyword in text_lower:
                    confidence = len(keyword) / max(1, len(text_lower))
                    if confidence > best_confidence:
                        best_confidence = min(0.9, confidence + 0.3)
                        best_match = cmd_type

        # Extract basic parameters
        parameters = self._extract_parameters(text_lower, best_match)

        return ClassifiedIntent(
            command_type=best_match,
            confidence=best_confidence,
            parameters=parameters,
            original_text=text,
            action_description=ADVANCED_COMMAND_TYPES.get(best_match, ""),
        )

    async def classify_complex(self, text: str, context: Optional[Dict[str, Any]] = None) -> ClassifiedIntent:
        """LLM-based classification for complex commands."""
        if not self.llm_client:
            return self.classify_keyword(text)

        available_commands = "\n".join(f"- {cmd}: {desc}" for cmd, desc in ADVANCED_COMMAND_TYPES.items())

        context_info = ""
        if context:
            context_info = f"\nCurrent context: {context}"

        prompt = f"""Classify this voice command into one of these types:

{available_commands}

Voice command: "{text}"
{context_info}

Respond with JSON:
{{"command_type": "TYPE", "confidence": 0.0-1.0, "parameters": {{}}, "action_description": "what to do"}}"""

        try:
            import json

            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client.chat(messages=messages)
            if response and "message" in response:
                content = response["message"].get("content", "")
                # Try to parse JSON
                import re

                json_match = re.search(r"\{[^}]+\}", content)
                if json_match:
                    data = json.loads(json_match.group())
                    return ClassifiedIntent(
                        command_type=data.get("command_type", "HELP"),
                        confidence=float(data.get("confidence", 0.5)),
                        parameters=data.get("parameters", {}),
                        original_text=text,
                        action_description=data.get("action_description", ""),
                    )
        except Exception as e:
            self.logger.warning(f"LLM classification failed, using keyword fallback: {e}")

        return self.classify_keyword(text)

    def _extract_parameters(self, text: str, command_type: str) -> Dict[str, Any]:
        """Extract basic parameters from command text."""
        params: Dict[str, Any] = {}

        if command_type == "NAVIGATE_FILE":
            # Try to extract file path/name
            words = text.split()
            for i, w in enumerate(words):
                if "." in w and len(w) > 2:
                    params["file_name"] = w
                    break

        elif command_type == "SEARCH_CODE":
            # Extract search query
            for prefix in ["search for", "find", "look for", "where is"]:
                if prefix in text:
                    params["query"] = text.split(prefix, 1)[1].strip()
                    break

        elif command_type == "RUN_PHASE":
            # Extract phase name
            for phase in ["readme", "structure", "content", "test", "review", "refactor"]:
                if phase in text:
                    params["phase_name"] = phase
                    break

        return params
