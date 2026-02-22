import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PromptLoader:
    """
    Utility class for loading centralized prompts from YAML files.
    Ensures consistent prompt management across the codebase.
    """

    _instance = None
    _cache: Dict[str, Any] = {}

    def __new__(cls, prompts_dir: Optional[Path] = None):
        if cls._instance is None:
            cls._instance = super(PromptLoader, cls).__new__(cls)
            if prompts_dir is None:
                # Default to root/prompts
                project_root = Path(__file__).parent.parent.parent.parent.parent
                prompts_dir = project_root / "prompts"
            cls._instance.prompts_dir = prompts_dir
        return cls._instance

    def load_prompt(self, relative_path: str) -> Dict[str, Any]:
        """
        Loads a prompt file from the prompts directory.
        Caches the result for performance.
        
        Args:
            relative_path: Path relative to the prompts directory (e.g., 'roles/analyst.yaml')
            
        Returns:
            Dictionary containing the parsed YAML content.
        """
        if relative_path in self._cache:
            return self._cache[relative_path]

        file_path = self.prompts_dir / relative_path
        if not file_path.exists():
            logger.error(f"Prompt file not found: {file_path}")
            return {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                self._cache[relative_path] = content
                return content
        except Exception as e:
            logger.error(f"Error loading prompt file {file_path}: {e}")
            return {}

    def get_prompt(self, file_path: str, key: str) -> Optional[str]:
        """Helper to get a specific prompt string from a file."""
        content = self.load_prompt(file_path)
        return content.get(key)

    def get_task_prompt(self, file_path: str, task_name: str) -> Optional[str]:
        """Helper to get a prompt from the 'tasks' dictionary in a file."""
        content = self.load_prompt(file_path)
        tasks = content.get("tasks", {})
        return tasks.get(task_name)
