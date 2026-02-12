from pathlib import Path
from typing import List, Dict, Any
import json

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.llm_response_parser import LLMResponseParser
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

    def generate(self, readme_content: str, max_retries: int = 3, template_name: str = "default",
                 python_version: str = "3.12", license_type: str = "MIT", include_docker: bool = False) -> dict:
        """Generate a JSON project structure from README content using a hierarchical approach.

        Includes retry logic and falls back to a basic structure on failure.
        """
        self.logger.info("  Starting hierarchical structure generation...")
        
        # Phase 1: Generate high-level structure (root files and top-level folders)
        high_level_structure = self._generate_high_level_structure(
            readme_content, max_retries, template_name
        )
        if not high_level_structure:
            self.logger.error("  Failed to generate high-level structure. Using fallback.")
            return self.create_fallback_structure(
                readme_content, template_name, python_version, license_type, include_docker
            )

        # Phase 2: Recursively generate sub-structures for each folder
        final_structure = self._recursively_generate_sub_structure(
            high_level_structure, readme_content, max_retries, template_name=template_name
        )
        
        file_count = len(self.extract_file_paths(final_structure))
        self.logger.info(f"  Successfully generated hierarchical structure with {file_count} files")
        return final_structure

    def _generate_high_level_structure(self, readme_content: str, max_retries: int, template_name: str) -> dict:
        """Generates the high-level (root) folders and files for the project."""
        system_prompt, user_prompt = AutoGenPrompts.high_level_structure_generation(
            readme_content, template_name
        )

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
                self.logger.info(f"  Raw high-level response length: {len(raw)} characters")
                structure = self.parser.extract_json(raw)
                if structure is None:
                    raise ValueError("Could not extract valid JSON from high-level response")

                structure.setdefault("path", "./")
                structure.setdefault("folders", [])
                structure.setdefault("files", [])
                
                if not structure["folders"] and not structure["files"]:
                    raise ValueError("High-level structure is empty. Rellamando a la funcion para regenerar el JSON de la estructura del proyecto")

                return structure
            except Exception as e:
                self.logger.error(f"  High-level attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    self.logger.info("  Retrying high-level generation with simplified prompt...")
                    system_prompt, user_prompt = AutoGenPrompts.high_level_structure_generation_simplified(
                        readme_content, template_name
                    )
                else:
                    self.logger.error("  All high-level attempts failed.")
                    return {}
        return {}
    
    def _recursively_generate_sub_structure(
        self,
        current_structure: dict,
        readme_content: str,
        max_retries: int,
        parent_path: str = "",
        template_name: str = "default"
    ) -> dict:
        """Recursively generates detailed structure for folders within the project."""
        
        detailed_structure = json.loads(json.dumps(current_structure))

        for i, folder_data in enumerate(detailed_structure.get("folders", [])):
            folder_name = folder_data.get("name")
            if folder_name:
                full_folder_path = str(Path(parent_path) / folder_name)
                self.logger.info(f"    Generating sub-structure for folder: {full_folder_path}")

                sub_structure_content = self._generate_folder_sub_structure(
                    full_folder_path, readme_content, max_retries, detailed_structure, template_name
                )
                
                if sub_structure_content:
                    folder_data["folders"] = sub_structure_content.get("folders", [])
                    folder_data["files"] = sub_structure_content.get("files", [])
                    detailed_structure["folders"][i] = self._recursively_generate_sub_structure(
                        folder_data, readme_content, max_retries, full_folder_path, template_name
                    )
                else:
                    self.logger.warning(f"    Failed to generate sub-structure for {full_folder_path}. Leaving as is.")

        return detailed_structure

    def _generate_folder_sub_structure(
        self,
        folder_path: str,
        readme_content: str,
        max_retries: int,
        overall_structure: dict,
        template_name: str
    ) -> dict:
        """Generates the immediate sub-folders and files for a specific folder path."""
        overall_structure_str = json.dumps(overall_structure, indent=2)
        system_prompt, user_prompt = AutoGenPrompts.sub_structure_generation(
            folder_path, readme_content, overall_structure_str, template_name
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
                self.logger.info(f"      Raw sub-structure response length: {len(raw)} characters")
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
                    self.logger.info("      Retrying sub-structure generation with simplified prompt...")
                    system_prompt, user_prompt = AutoGenPrompts.sub_structure_generation_simplified(
                        folder_path, readme_content, overall_structure_str, template_name
                    )
                else:
                    self.logger.error(f"      All sub-structure attempts for {folder_path} failed.")
                    return {}
        return {}

    @staticmethod
    def extract_file_paths(json_structure: dict, current_path: str = "") -> List[str]:
        """Recursively extract all file paths from the JSON structure."""
        file_paths = []
        for file_name in json_structure.get("files", []):
            file_paths.append(str(Path(current_path) / file_name))

        for folder_data in json_structure.get("folders", []):
            folder_name = folder_data.get("name")
            if folder_name:
                new_path = str(Path(current_path) / folder_name)
                file_paths.extend(StructureGenerator.extract_file_paths(folder_data, new_path))

        return file_paths

    @staticmethod
    def create_empty_files(project_root: Path, json_structure: dict, current_path: str = ""):
        """Create empty placeholder files based on the JSON structure."""
        for file_name in json_structure.get("files", []):
            file_path = project_root / current_path / file_name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if file_path.is_dir():
                print(f"WARNING: Attempted to create file '{file_path}' but a directory with that name already exists. Skipping file creation.")
                continue

            if not file_path.exists():
                try:
                    file_path.touch()
                except Exception as e:
                    print(f"ERROR touching file '{file_path}': {e}")
                    continue

        for folder_data in json_structure.get("folders", []):
            folder_name = folder_data.get("name")
            if folder_name:
                new_path_full = project_root / current_path / folder_name
                
                if new_path_full.is_file():
                    print(f"WARNING: Attempted to create directory '{new_path_full}' but a file with that name already exists. Skipping directory creation.")
                    continue

                try:
                    new_path_full.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    print(f"ERROR creating directory '{new_path_full}': {e}")
                    continue
                
                StructureGenerator.create_empty_files(project_root, folder_data, str(new_path_full.relative_to(project_root)))

    @staticmethod
    def create_fallback_structure(readme_content: str, template_name: str = "default",
                                  python_version: str = "3.12", license_type: str = "MIT",
                                  include_docker: bool = False) -> dict:
        """Create a basic fallback project structure when generation fails or a specific template is requested."""
        TEMPLATE_FALLBACKS = {
            "default": {
                "path": "./",
                "folders": [
                    {"name": "src", "folders": [], "files": ["main.py"]},
                    {"name": "tests", "folders": [], "files": ["test_main.py"]},
                ],
                "files": ["README.md", ".gitignore", "requirements.txt", "Dockerfile"],
            },
            "fastapi-backend": {
                "path": "./",
                "folders": [
                    {"name": "app", "folders": [
                        {"name": "api", "folders": [], "files": ["__init__.py", "v1", "routers.py"]},
                        {"name": "core", "folders": [], "files": ["config.py", "database.py"]},
                        {"name": "models", "folders": [], "files": ["__init__.py", "item.py"]},
                        {"name": "schemas", "folders": [], "files": ["__init__.py", "item.py"]},
                        {"name": "services", "folders": [], "files": ["__init__.py", "item.py"]},
                    ], "files": ["main.py"]},
                    {"name": "tests", "folders": [], "files": ["test_main.py", "test_api.py"]},
                ],
                "files": ["README.md", ".gitignore", "requirements.txt", "Dockerfile", "docker-compose.yml"],
            },
            "react-frontend": {
                "path": "./",
                "folders": [
                    {"name": "src", "folders": [
                        {"name": "assets", "folders": [], "files": ["logo.svg"]},
                        {"name": "components", "folders": [], "files": ["Button.jsx", "Header.jsx"]},
                        {"name": "pages", "folders": [], "files": ["HomePage.jsx", "AboutPage.jsx"]},
                    ], "files": ["App.jsx", "index.css", "main.jsx"]},
                    {"name": "public", "folders": [], "files": ["index.html"]},
                    {"name": "tests", "folders": [], "files": ["App.test.jsx"]},
                ],
                "files": ["README.md", ".gitignore", "package.json", "package-lock.json", "vite.config.js"],
            },
            "automation-script": {
                "path": "./",
                "folders": [
                    {"name": "src", "folders": [], "files": ["script.py", "utils.py"]},
                    {"name": "config", "folders": [], "files": ["settings.ini"]},
                    {"name": "logs", "folders": [], "files": [".gitkeep"]},
                ],
                "files": ["README.md", ".gitignore", "requirements.txt"],
            },
        }

        if template_name in TEMPLATE_FALLBACKS:
            return TEMPLATE_FALLBACKS[template_name]
        else:
            return TEMPLATE_FALLBACKS["default"]
