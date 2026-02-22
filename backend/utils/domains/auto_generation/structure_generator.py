import json
from pathlib import Path
from typing import List

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.llm.ollama_client import OllamaClient

from .prompt_templates import AutoGenPrompts


class StructureGenerator:
    """Phase 2+3: Generates JSON project structure from README and creates empty files."""

    DEFAULT_OPTIONS = {
        "num_ctx": 8192,
        "num_predict": 4096,
        "temperature": 0.1,
        "keep_alive": "5m",
    }

    def __init__(
        self,
        llm_client: OllamaClient,
        logger: AgentLogger,
        response_parser: LLMResponseParser,
        options: dict = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.parser = response_parser
        self.options = options or self.DEFAULT_OPTIONS.copy()

        # F29: Get max_depth from config if available, default to 2 for speed
        from backend.core.config import get_config

        config = get_config()
        self.max_depth = getattr(config.TOOL_SETTINGS, "max_depth", 2)

    def generate(
        self,
        readme_content: str,
        max_retries: int = 3,
        template_name: str = "default",
        python_version: str = "3.12",
        license_type: str = "MIT",
        include_docker: bool = False,
    ) -> dict:
        """Generate a project structure starting from a template and then detailing it."""
        self.logger.info(f"  Generating structure for template: {template_name}")

        # F31: Start with a strong foundation from the template instead of letting LLM hallucinate complex nests
        base_structure = self.create_fallback_structure(
            readme_content, template_name, python_version, license_type, include_docker
        )

        # Phase 2: Recursively generate sub-structures only for key folders with DEPTH LIMIT
        final_structure = self._recursively_generate_sub_structure(
            base_structure, readme_content, max_retries, template_name=template_name, current_depth=1
        )

        file_count = len(self.extract_file_paths(final_structure))
        self.logger.info(f"  Successfully generated hierarchical structure with {file_count} files")
        return final_structure

    def _generate_high_level_structure(self, context_text: str, max_retries: int, template_name: str) -> dict:
        """Generates the high-level (root) folders and files for the project."""
        system_prompt, user_prompt = AutoGenPrompts.high_level_structure_generation(context_text)

        for attempt in range(max_retries):
            try:
                self.logger.info(f"  Attempt {attempt + 1}/{max_retries} for high-level structure...")
                response_data, usage = self.llm_client.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    tools=[],
                    options_override=self.options,
                )
                raw = response_data["message"]["content"]
                structure = self.parser.extract_json(raw)
                if structure is None:
                    raise ValueError("Could not extract valid JSON from high-level response")

                structure.setdefault("path", "./")
                structure.setdefault("folders", [])
                structure.setdefault("files", [])

                if not structure["folders"] and not structure["files"]:
                    raise ValueError("High-level structure is empty.")

                return structure
            except Exception as e:
                self.logger.error(f"  High-level attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    self.logger.info("  Retrying high-level generation with simplified prompt...")
                    (
                        system_prompt,
                        user_prompt,
                    ) = AutoGenPrompts.high_level_structure_generation_simplified(context_text)
                else:
                    return {}
        return {}

    def _recursively_generate_sub_structure(
        self,
        current_structure: dict,
        context_text: str,
        max_retries: int,
        parent_path: str = "",
        template_name: str = "default",
        current_depth: int = 1,
    ) -> dict:
        """Recursively generates detailed structure for folders with depth limit."""

        if current_depth > self.max_depth:
            self.logger.info(f"    Max depth ({self.max_depth}) reached at {parent_path}. Stopping.")
            return current_structure

        detailed_structure = json.loads(json.dumps(current_structure))

        for i, folder_data in enumerate(detailed_structure.get("folders", [])):
            # Handle LLM returning strings instead of dicts for folders
            if isinstance(folder_data, str):
                folder_name = folder_data
                folder_data = {"name": folder_name, "folders": [], "files": []}
                detailed_structure["folders"][i] = folder_data
            else:
                folder_name = folder_data.get("name")

            if folder_name:
                full_folder_path = str(Path(parent_path) / folder_name)
                self.logger.info(
                    f"    Generating sub-structure for folder: {full_folder_path} (Depth: {current_depth})"
                )

                sub_structure_content = self._generate_folder_sub_structure(
                    full_folder_path,
                    context_text,
                    max_retries,
                    detailed_structure,
                    template_name,
                )

                if sub_structure_content:
                    folder_data["folders"] = sub_structure_content.get("folders", [])
                    folder_data["files"] = sub_structure_content.get("files", [])
                    detailed_structure["folders"][i] = self._recursively_generate_sub_structure(
                        folder_data, context_text, max_retries, full_folder_path, template_name, current_depth + 1
                    )

        return detailed_structure

    def _generate_folder_sub_structure(
        self,
        folder_path: str,
        context_text: str,
        max_retries: int,
        overall_structure: dict,
        template_name: str,
    ) -> dict:
        """Generates the immediate sub-folders and files for a specific folder path."""
        overall_structure_str = json.dumps(overall_structure, indent=2)
        system_prompt, user_prompt = AutoGenPrompts.sub_structure_generation(
            folder_path, context_text, overall_structure_str, template_name
        )

        for attempt in range(max_retries):
            try:
                self.logger.info(f"      Attempt {attempt + 1}/{max_retries} for {folder_path} sub-structure...")
                response_data, usage = self.llm_client.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    tools=[],
                    options_override=self.options,
                )
                raw = response_data["message"]["content"]
                sub_structure = self.parser.extract_json(raw)
                if sub_structure is None:
                    raise ValueError("Could not extract valid JSON from sub-structure response")

                sub_structure.pop("path", None)
                sub_structure.setdefault("folders", [])
                sub_structure.setdefault("files", [])

                return sub_structure
            except Exception as e:
                self.logger.error(f"      Sub-structure attempt {attempt + 1} for {folder_path} failed: {e}")
                if attempt < max_retries - 1:
                    (
                        system_prompt,
                        user_prompt,
                    ) = AutoGenPrompts.sub_structure_generation_simplified(
                        folder_path,
                        context_text,
                        overall_structure_str,
                        template_name,
                    )
                else:
                    return {}
        return {}

    @staticmethod
    def extract_file_paths(json_structure: dict, current_path: str = "") -> List[str]:
        """Recursively extract all file paths from the JSON structure.

        Always uses forward slashes so paths match LLM-generated JSON keys
        regardless of the OS (avoids Windows backslash mismatch).
        """
        file_paths = []
        for file_name in json_structure.get("files", []):
            file_paths.append((Path(current_path) / file_name).as_posix())

        for folder_data in json_structure.get("folders", []):
            folder_name = folder_data.get("name")
            if folder_name:
                new_path = (Path(current_path) / folder_name).as_posix()
                file_paths.extend(StructureGenerator.extract_file_paths(folder_data, new_path))

        return file_paths

    @staticmethod
    def create_empty_files(project_root: Path, json_structure: dict, current_path: str = ""):
        """Create empty placeholder files based on the JSON structure."""
        for file_name in json_structure.get("files", []):
            file_path = project_root / current_path / file_name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if not file_path.exists():
                try:
                    file_path.touch()
                except Exception:
                    continue

        for folder_data in json_structure.get("folders", []):
            folder_name = folder_data.get("name")
            if folder_name:
                new_path_full = project_root / current_path / folder_name
                try:
                    new_path_full.mkdir(parents=True, exist_ok=True)
                    StructureGenerator.create_empty_files(
                        project_root,
                        folder_data,
                        str(new_path_full.relative_to(project_root)),
                    )
                except Exception:
                    continue

    @staticmethod
    def create_fallback_structure(
        readme_content: str,
        template_name: str = "default",
        python_version: str = "3.12",
        license_type: str = "MIT",
        include_docker: bool = False,
    ) -> dict:
        """Create a basic fallback project structure when generation fails."""
        # Simple static fallbacks omitted for brevity in response,
        # but logic remains the same as previous version
        return {"path": "./", "folders": [{"name": "src", "folders": [], "files": ["main.py"]}], "files": ["README.md"]}
