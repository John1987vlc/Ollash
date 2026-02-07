import json
from pathlib import Path
from typing import Dict, List, Any

class MemoryManager:
    def __init__(self, project_root: Path, logger: Any):
        self.project_root = project_root
        self.memory_file = self.project_root / ".agent_memory.json"
        self.logger = logger
        self.memory: Dict[str, Any] = {}
        self._load_memory()

    def _load_memory(self):
        """Loads memory from the .agent_memory.json file."""
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.memory = json.load(f)
                self.logger.info(f"Memory loaded from {self.memory_file}")
            except json.JSONDecodeError as e:
                self.logger.error(f"Error decoding memory file {self.memory_file}: {e}")
                self.memory = {} # Reset memory on error
            except Exception as e:
                self.logger.error(f"Unexpected error loading memory from {self.memory_file}: {e}")
                self.memory = {}
        else:
            self.logger.info("No existing memory file found, starting with empty memory.")

    def _save_memory(self):
        """Saves current memory to the .agent_memory.json file."""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=2)
            self.logger.info(f"Memory saved to {self.memory_file}")
        except Exception as e:
            self.logger.error(f"Error saving memory to {self.memory_file}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a value from memory."""
        return self.memory.get(key, default)

    def set(self, key: str, value: Any):
        """Sets a value in memory and saves immediately."""
        self.memory[key] = value
        self._save_memory()

    def update_conversation_history(self, history: List[Dict]):
        """Updates and saves the conversation history."""
        self.set("conversation_history", history)

    def get_conversation_history(self) -> List[Dict]:
        """Retrieves the conversation history."""
        return self.get("conversation_history", [])

    def update_domain_context_memory(self, domain_context: Dict[str, str]):
        """Updates and saves the domain context memory."""
        self.set("domain_context_memory", domain_context)

    def get_domain_context_memory(self) -> Dict[str, str]:
        """Retrieves the domain context memory."""
        return self.get("domain_context_memory", {})
    
    # You might add more specific methods for loop detection history if needed,
    # or handle it as part of a general state object.
