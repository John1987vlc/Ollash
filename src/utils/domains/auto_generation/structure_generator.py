from pathlib import Path
from typing import List

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

    def generate(self, readme_content: str, max_retries: int = 3) -> dict:
        """Generate a JSON project structure from README content using a hierarchical approach.

        Includes retry logic and falls back to a basic structure on failure.
        """
        self.logger.info("  Starting hierarchical structure generation...")
        
        # Phase 1: Generate high-level structure (root files and top-level folders)
        high_level_structure = self._generate_high_level_structure(readme_content, max_retries)
        if not high_level_structure:
            self.logger.error("  Failed to generate high-level structure. Using fallback.")
            return self.create_fallback_structure(readme_content)

        # Phase 2: Recursively generate sub-structures for each folder
        final_structure = self._recursively_generate_sub_structure(
            high_level_structure, readme_content, max_retries
        )
        
        file_count = len(self.extract_file_paths(final_structure))
        self.logger.info(f"  Successfully generated hierarchical structure with {file_count} files")
        return final_structure

    def _generate_high_level_structure(self, readme_content: str, max_retries: int) -> dict:
        """Generates the high-level (root) folders and files for the project."""
        system_prompt, user_prompt = AutoGenPrompts.high_level_structure_generation(readme_content)

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
                
                # Basic validation for high-level structure to prevent infinite loops
                if not structure["folders"] and not structure["files"]:
                    raise ValueError("High-level structure is empty. Rellamando a la funcion para regenerar el JSON de la estructura del proyecto")

                return structure
            except Exception as e:
                self.logger.error(f"  High-level attempt {attempt + 1} failed: {e}")
                # Simplificado prompt para el retry si falla
                if attempt < max_retries - 1:
                    self.logger.info("  Retrying high-level generation with simplified prompt...")
                    system_prompt, user_prompt = AutoGenPrompts.high_level_structure_generation_simplified(readme_content)
                else:
                    self.logger.error("  All high-level attempts failed.")
                    return {}
        return {}
    
    def _recursively_generate_sub_structure(
        self,
        current_structure: dict,
        readme_content: str,
        max_retries: int,
        parent_path: str = ""
    ) -> dict:
        """Recursively generates detailed structure for folders within the project."""
        
        # Deep copy to avoid modifying the original structure during recursion
        detailed_structure = json.loads(json.dumps(current_structure))

        for i, folder_data in enumerate(detailed_structure.get("folders", [])):
            folder_name = folder_data.get("name")
            if folder_name:
                full_folder_path = str(Path(parent_path) / folder_name)
                self.logger.info(f"    Generating sub-structure for folder: {full_folder_path}")

                sub_structure_content = self._generate_folder_sub_structure(
                    full_folder_path, readme_content, max_retries, detailed_structure
                )
                
                if sub_structure_content:
                    # Merge the generated sub-structure into the current folder_data
                    folder_data["folders"] = sub_structure_content.get("folders", [])
                    folder_data["files"] = sub_structure_content.get("files", [])
                    # Recursively process this newly detailed sub-structure
                    detailed_structure["folders"][i] = self._recursively_generate_sub_structure(
                        folder_data, readme_content, max_retries, full_folder_path
                    )
                else:
                    self.logger.warning(f"    Failed to generate sub-structure for {full_folder_path}. Leaving as is.")

        return detailed_structure

    def _generate_folder_sub_structure(
        self,
        folder_path: str,
        readme_content: str,
        max_retries: int,
        overall_structure: dict
    ) -> dict:
        """Generates the immediate sub-folders and files for a specific folder path."""
        # Provide more specific context including the overall structure but focusing on the current folder
        overall_structure_str = json.dumps(overall_structure, indent=2)
        system_prompt, user_prompt = AutoGenPrompts.sub_structure_generation(
            folder_path, readme_content, overall_structure_str
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
                
                # Ensure it only returns folders and files for the current path, not a full new path field
                sub_structure.pop("path", None)
                sub_structure.setdefault("folders", [])
                sub_structure.setdefault("files", [])

                return sub_structure
            except Exception as e:
                self.logger.error(f"      Sub-structure attempt {attempt + 1} for {folder_path} failed: {e}")
                if attempt < max_retries - 1:
                    self.logger.info("      Retrying sub-structure generation with simplified prompt...")
                    system_prompt, user_prompt = AutoGenPrompts.sub_structure_generation_simplified(
                        folder_path, readme_content, overall_structure_str
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
            
            # Check for name conflict: if a directory exists with the same name as the file
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
                
                # Check for name conflict: if a file exists with the same name as the directory
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
    def create_fallback_structure(readme_content: str) -> dict:
        """Create a basic fallback project structure when generation fails.

        Detects project type from README keywords and produces an appropriate
        structure. Supports Python, Node.js, C#/.NET, C/C++, Go, Rust, Java,
        Ruby, shell scripts, and a generic fallback.
        """
        readme_lower = readme_content.lower()

        root_files = ["README.md", ".gitignore"]
        folders = []

        # --- Python projects ---
        if any(kw in readme_lower for kw in ["flask", "django", "fastapi", "python", "pip", "pyproject"]):
            root_files.append("requirements.txt")
            if "flask" in readme_lower:
                folders.extend([
                    {
                        "name": "static",
                        "folders": [
                            {"name": "css", "folders": [], "files": ["style.css"]},
                            {"name": "js", "folders": [], "files": ["main.js"]},
                        ],
                        "files": [],
                    },
                    {"name": "templates", "folders": [], "files": ["index.html", "base.html"]},
                ])
                root_files.extend(["app.py", "config.py"])
            elif "fastapi" in readme_lower:
                folders.extend([
                    {"name": "api", "folders": [], "files": ["__init__.py", "routes.py", "models.py"]},
                    {"name": "core", "folders": [], "files": ["__init__.py", "config.py"]},
                    {"name": "tests", "folders": [], "files": ["__init__.py", "test_api.py"]},
                ])
                root_files.append("main.py")
            elif "django" in readme_lower:
                folders.extend([
                    {"name": "project", "folders": [], "files": ["__init__.py", "settings.py", "urls.py", "wsgi.py"]},
                    {"name": "app", "folders": [], "files": ["__init__.py", "models.py", "views.py", "urls.py"]},
                ])
                root_files.append("manage.py")
            else:
                folders.append({"name": "src", "folders": [], "files": ["__init__.py", "main.py"]})
                folders.append({"name": "tests", "folders": [], "files": ["__init__.py", "test_main.py"]})

        # --- C# / .NET projects ---
        elif any(kw in readme_lower for kw in ["c#", "csharp", ".net", "dotnet", "unity", "asp.net", "monogame"]):
            if "unity" in readme_lower:
                folders.extend([
                    {"name": "Assets", "folders": [
                        {"name": "Scripts", "folders": [], "files": ["GameManager.cs", "PlayerController.cs"]},
                        {"name": "Scenes", "folders": [], "files": []},
                        {"name": "Prefabs", "folders": [], "files": []},
                    ], "files": []},
                    {"name": "ProjectSettings", "folders": [], "files": []},
                ])
            else:
                folders.append({"name": "src", "folders": [], "files": ["Program.cs", "project.csproj"]})
                folders.append({"name": "tests", "folders": [], "files": ["Tests.cs", "tests.csproj"]})
                root_files.append("solution.sln")

        # --- Node.js / JavaScript / TypeScript projects ---
        elif any(kw in readme_lower for kw in ["node", "npm", "javascript", "typescript", "react", "next.js", "express", "vue", "angular"]):
            root_files.extend(["package.json", "tsconfig.json"])
            folders.append({"name": "src", "folders": [], "files": ["index.ts", "app.ts"]})
            folders.append({"name": "tests", "folders": [], "files": ["app.test.ts"]})

        # --- Go projects ---
        elif any(kw in readme_lower for kw in ["golang", " go ", "go module"]):
            root_files.extend(["go.mod", "go.sum"])
            folders.append({"name": "cmd", "folders": [], "files": ["main.go"]})
            folders.append({"name": "internal", "folders": [], "files": []})
            folders.append({"name": "pkg", "folders": [], "files": []})

        # --- Rust projects ---
        elif "rust" in readme_lower or "cargo" in readme_lower:
            root_files.append("Cargo.toml")
            folders.append({"name": "src", "folders": [], "files": ["main.rs", "lib.rs"]})

        # --- Java / Kotlin projects ---
        elif any(kw in readme_lower for kw in ["java ", "kotlin", "gradle", "maven", "spring"]):
            if "gradle" in readme_lower:
                root_files.extend(["build.gradle", "settings.gradle"])
            else:
                root_files.append("pom.xml")
            folders.append({
                "name": "src",
                "folders": [
                    {"name": "main", "folders": [
                        {"name": "java", "folders": [], "files": ["Main.java"]},
                        {"name": "resources", "folders": [], "files": ["application.properties"]},
                    ], "files": []},
                    {"name": "test", "folders": [
                        {"name": "java", "folders": [], "files": ["MainTest.java"]},
                    ], "files": []},
                ],
                "files": [],
            })

        # --- C / C++ projects ---
        elif any(kw in readme_lower for kw in ["c++", "cpp", "cmake", "makefile"]):
            root_files.append("CMakeLists.txt")
            folders.append({"name": "src", "folders": [], "files": ["main.cpp"]})
            folders.append({"name": "include", "folders": [], "files": []})
            folders.append({"name": "tests", "folders": [], "files": ["test_main.cpp"]})

        # --- Ruby projects ---
        elif "ruby" in readme_lower or "rails" in readme_lower:
            root_files.extend(["Gemfile", "Rakefile"])
            folders.append({"name": "lib", "folders": [], "files": ["main.rb"]})
            folders.append({"name": "spec", "folders": [], "files": ["main_spec.rb"]})

        # --- Shell script projects ---
        elif any(kw in readme_lower for kw in ["bash", "shell", "script"]):
            folders.append({"name": "scripts", "folders": [], "files": ["main.sh"]})
            root_files.append("Makefile")

        # --- Generic fallback ---
        else:
            folders.append({"name": "src", "folders": [], "files": ["main.py"]})
            root_files.append("Makefile")

        return {
            "path": "./",
            "folders": folders,
            "files": root_files,
        }
