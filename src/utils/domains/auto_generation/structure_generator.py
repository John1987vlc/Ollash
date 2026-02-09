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
        """Generate a JSON project structure from README content.

        Includes retry logic and falls back to a basic structure on failure.
        """
        system, user = AutoGenPrompts.structure_generation(readme_content)

        for attempt in range(max_retries):
            try:
                self.logger.info(f"  Attempt {attempt + 1}/{max_retries} to generate JSON structure...")
                response_data, usage = self.llm_client.chat(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    tools=[],
                    options_override=self.options,
                )

                raw = response_data["message"]["content"]
                self.logger.info(f"  Raw response length: {len(raw)} characters")

                structure = self.parser.extract_json(raw)
                if structure is None:
                    raise ValueError("Could not extract valid JSON from response")

                # Ensure required fields
                structure.setdefault("path", "./")
                structure.setdefault("folders", [])
                structure.setdefault("files", [])

                file_count = len(self.extract_file_paths(structure))
                self.logger.info(f"  Successfully generated structure with {file_count} files")
                return structure

            except Exception as e:
                self.logger.error(f"  Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    self.logger.info("  Retrying with simplified prompt...")
                    user = (
                        "Generate a SIMPLE project structure JSON for this project. "
                        "Keep it minimal with only essential files.\n\n"
                        f"README summary: {readme_content[:500]}...\n\n"
                        "Output ONLY valid, complete JSON."
                    )
                else:
                    self.logger.error("  All attempts failed. Using fallback structure.")
                    return self.create_fallback_structure(readme_content)

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
            if not file_path.exists():
                file_path.touch()

        for folder_data in json_structure.get("folders", []):
            folder_name = folder_data.get("name")
            if folder_name:
                new_path = str(Path(current_path) / folder_name)
                (project_root / new_path).mkdir(parents=True, exist_ok=True)
                StructureGenerator.create_empty_files(project_root, folder_data, new_path)

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
