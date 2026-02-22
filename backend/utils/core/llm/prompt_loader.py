import yaml
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PromptLoader:
    """
    Utility class for loading centralized prompts from SQLite or YAML files.
    Ensures DB-first priority with filesystem fallback.
    """

    _instance = None
    _cache: Dict[str, Any] = {}
    _repository = None

    def __new__(cls, prompts_dir: Optional[Path] = None):
        if cls._instance is None:
            cls._instance = super(PromptLoader, cls).__new__(cls)
            if prompts_dir is None:
                # Default to root/prompts
                project_root = Path(__file__).parent.parent.parent.parent.parent
                prompts_dir = project_root / "prompts"
            cls._instance.prompts_dir = prompts_dir
        return cls._instance

    def set_repository(self, repository):
        """Injects the PromptRepository for DB access."""
        self._repository = repository

    def _get_db_prompt(self, role: str) -> Optional[Dict[str, Any]]:
        """Attempt to load a prompt dictionary from the database."""
        if not self._repository:
            # Try to lazy load from main container to avoid circular imports
            try:
                from backend.core.containers import main_container
                if hasattr(main_container, "core"):
                    self._repository = main_container.core.prompt_repository()
                elif hasattr(main_container, "prompt_repository"):
                    self._repository = main_container.prompt_repository()
            except:
                return None

        if self._repository:
            try:
                text = self._repository.get_active_prompt(role)
                if text:
                    # Try to parse as JSON if it looks like one, otherwise return as system prompt
                    if text.strip().startswith("{") or text.strip().startswith("["):
                        return json.loads(text)
                    return {"system": text}
            except Exception as e:
                logger.debug(f"DB prompt load failed for {role}: {e}")
        return None

    def load_prompt(self, relative_path: str) -> Dict[str, Any]:
        """
        Loads a prompt from DB (priority) or filesystem.
        """
        role_key = Path(relative_path).stem
        
        # 1. Try DB first
        db_content = self._get_db_prompt(role_key)
        if db_content:
            return db_content

        # 2. Cache check for filesystem
        if relative_path in self._cache:
            return self._cache[relative_path]

        # 3. Filesystem fallback
        file_path = self.prompts_dir / relative_path
        if not file_path.exists():
            # Try with .yaml extension if missing
            if not file_path.suffix:
                file_path = file_path.with_suffix(".yaml")
            
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
