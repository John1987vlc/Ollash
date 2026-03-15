import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.llm.ollama_client import OllamaClient
from backend.utils.core.system.retry_policy import RetryPolicy

from backend.utils.domains.auto_generation.utilities.prompt_templates import AutoGenPrompts


class StructureGenerator:
    """Phase 2+3: Generates JSON project structure from README and creates empty files."""

    DEFAULT_OPTIONS = {
        "num_ctx": 32768,  # Increased for efficiency on all models, especially nano
        "num_predict": 8192,  # Increased to allow large folder trees without truncation
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
        self.retry_policy = RetryPolicy()

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
        constraint_hint: str = "",
    ) -> dict:
        """Generate a project structure starting from a template and then detailing it."""
        self.logger.info_sync(f"  Generating structure for template: {template_name}")
        self._constraint_hint = constraint_hint

        # F31: Detect nano/small models (<=8B)
        is_small = (
            "0.8b" in self.llm_client.model
            or "1.5b" in self.llm_client.model
            or "3b" in self.llm_client.model
            or "4b" in self.llm_client.model
            or "6b" in self.llm_client.model
            or "7b" in self.llm_client.model
            or "8b" in self.llm_client.model
        )

        # Detect project type for better scaffolding
        from backend.utils.domains.auto_generation.project_type_detector import ProjectTypeDetector

        type_info = ProjectTypeDetector.detect("", readme_content)
        p_type = type_info.project_type if type_info else ""

        # F31: Start with a strong foundation from the template
        base_structure = self.create_fallback_structure(
            readme_content, template_name, python_version, license_type, include_docker, project_type=p_type
        )

        if is_small:
            self.logger.info_sync(f"  Small model ({self.llm_client.model}) detected: Using Skeleton-First approach.")
            # For small models, we use the base_structure as the master and only ask for minor additions
            # instead of a recursive generation that often fails or hangs.
            final_structure = self._generate_small_model_additions(base_structure, readme_content, p_type)
        else:
            # Phase 2: Recursively generate sub-structures only for key folders with DEPTH LIMIT
            final_structure = self._recursively_generate_sub_structure(
                base_structure,
                readme_content,
                max_retries,
                template_name=template_name,
                current_depth=1,
                max_depth_override=self.max_depth,
            )

        file_count = len(self.extract_file_paths(final_structure))
        self.logger.info_sync(f"  Successfully generated structure with {file_count} files")
        return final_structure

    def _generate_small_model_additions(self, base_structure: dict, readme_content: str, project_type: str) -> dict:
        """Ask small model for only 2-3 extra files to add to the deterministic scaffold."""
        try:
            prompt = (
                f"Project Type: {project_type}\n"
                f"Current Scaffold: {json.dumps(base_structure, indent=1)}\n"
                f"README: {readme_content[:1000]}\n\n"
                "Based on the README, suggest 2-3 additional core files needed for this project. "
                'Return ONLY a JSON list of file paths (relative to root). Example: ["src/utils/math.js", "docs/usage.md"]'
            )

            response_data, _ = self.llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                options_override={"temperature": 0.1, "num_predict": 2048},
            )
            raw = response_data.get("content", "")
            extra_files = self.parser.extract_json(raw)

            if isinstance(extra_files, list):
                # Merging extra files into base_structure
                for file_path in extra_files:
                    if not isinstance(file_path, str):
                        continue
                    # Simple split to find folder and file
                    parts = file_path.replace("\\", "/").split("/")
                    if len(parts) == 1:
                        if file_path not in base_structure["files"]:
                            base_structure["files"].append(file_path)
                    else:
                        # Find or create folder
                        curr = base_structure
                        for folder_name in parts[:-1]:
                            found = False
                            for f_node in curr.get("folders", []):
                                if f_node.get("name") == folder_name:
                                    curr = f_node
                                    found = True
                                    break
                            if not found:
                                new_folder = {"name": folder_name, "folders": [], "files": []}
                                curr.setdefault("folders", []).append(new_folder)
                                curr = new_folder
                        if parts[-1] not in curr.get("files", []):
                            curr.setdefault("files", []).append(parts[-1])

            return base_structure
        except Exception as e:
            self.logger.info_sync(f"  Error getting small model additions: {e}. Returning base scaffold.")
            return base_structure

    def _generate_high_level_structure(self, context_text: str, max_retries: int, template_name: str) -> dict:
        """Generates the high-level (root) folders and files for the project."""
        system_prompt, user_prompt = AutoGenPrompts.high_level_structure_generation(context_text)

        for attempt in range(max_retries):
            try:
                self.logger.info_sync(f"  Attempt {attempt + 1}/{max_retries} for high-level structure...")
                response_data, usage = self.llm_client.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    tools=[],
                    options_override=self.options,
                )
                raw = response_data.get("content", "")
                structure = self.parser.extract_json(raw)
                if structure is None:
                    raise ValueError("Could not extract valid JSON from high-level response")

                # Handle list if LLM returns a flat list
                if isinstance(structure, list):
                    structure = {"folders": [], "files": structure}

                structure.setdefault("path", "./")
                structure.setdefault("folders", [])
                structure.setdefault("files", [])

                if not structure["folders"] and not structure["files"]:
                    raise ValueError("High-level structure is empty.")

                return structure
            except Exception as e:
                self.logger.info_sync(f"  High-level attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    self.logger.info_sync("  Retrying high-level generation with simplified prompt...")
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
        max_depth_override: int = None,
    ) -> dict:
        """Recursively generates detailed structure for folders with depth limit."""
        target_max_depth = max_depth_override if max_depth_override is not None else self.max_depth

        if current_depth > target_max_depth:
            self.logger.info_sync(f"    Max depth ({target_max_depth}) reached at {parent_path}. Stopping.")
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
                self.logger.info_sync(
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
                    # F31: Robust path normalization to prevent duplication (e.g., src/src/main.js)
                    # We ensure sub-files and sub-folders don't carry the parent's path prefix
                    raw_sub_files = sub_structure_content.get("files", [])
                    raw_sub_folders = sub_structure_content.get("folders", [])

                    normalized_sub_files = []
                    for f in raw_sub_files:
                        f_name = f.get("name") if isinstance(f, dict) else str(f)
                        # If LLM returned "src/main.js" inside "src" folder, just keep "main.js"
                        if "/" in f_name:
                            f_name = f_name.split("/")[-1]
                        elif "\\" in f_name:
                            f_name = f_name.split("\\")[-1]

                        if isinstance(f, dict):
                            f["name"] = f_name
                            normalized_sub_files.append(f)
                        else:
                            normalized_sub_files.append(f_name)

                    normalized_sub_folders = []
                    for sub_f in raw_sub_folders:
                        sub_f_name = sub_f.get("name") if isinstance(sub_f, dict) else str(sub_f)
                        if "/" in sub_f_name:
                            sub_f_name = sub_f_name.split("/")[-1]
                        elif "\\" in sub_f_name:
                            sub_f_name = sub_f_name.split("\\")[-1]

                        if isinstance(sub_f, dict):
                            sub_f["name"] = sub_f_name
                            normalized_sub_folders.append(sub_f)
                        else:
                            normalized_sub_folders.append({"name": sub_f_name, "folders": [], "files": []})

                    folder_data["folders"] = normalized_sub_folders
                    folder_data["files"] = normalized_sub_files

                    detailed_structure["folders"][i] = self._recursively_generate_sub_structure(
                        folder_data,
                        context_text,
                        max_retries,
                        full_folder_path,
                        template_name,
                        current_depth + 1,
                        max_depth_override=target_max_depth,
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
        _hint = getattr(self, "_constraint_hint", "")
        system_prompt, user_prompt = AutoGenPrompts.sub_structure_generation(
            folder_path,
            context_text,
            overall_structure_str,
            template_name,
            constraint_hint=_hint,
        )

        for attempt in range(max_retries):
            try:
                self.logger.info_sync(f"      Attempt {attempt + 1}/{max_retries} for {folder_path} sub-structure...")
                response_data, usage = self.llm_client.chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    tools=[],
                    options_override=self.options,
                )
                raw = response_data.get("content", "")
                sub_structure = self.parser.extract_json(raw)
                if sub_structure is None:
                    raise ValueError("Could not extract valid JSON from sub-structure response")

                if isinstance(sub_structure, list):
                    # Flatten if it's a list (common LLM error for folders/files)
                    sub_structure = {"folders": [], "files": sub_structure}
                elif not isinstance(sub_structure, dict):
                    sub_structure = {"folders": [], "files": []}

                sub_structure.pop("path", None)
                sub_structure.setdefault("folders", [])
                sub_structure.setdefault("files", [])

                # Path normalisation: ensure files don't have redundant prefixes
                # e.g. if folder_path is 'src', and file is 'src/app.js', change to 'app.js'
                normalized_files = []
                for f in sub_structure["files"]:
                    f_name = f.get("name") if isinstance(f, dict) else str(f)
                    if not f_name:
                        continue
                    # Remove redundant prefix
                    if "/" in f_name and f_name.startswith(folder_path.replace("\\", "/") + "/"):
                        f_name = f_name[len(folder_path) + 1 :]
                    elif "\\" in f_name and f_name.startswith(folder_path.replace("/", "\\") + "\\"):
                        f_name = f_name[len(folder_path) + 1 :]

                    if isinstance(f, dict):
                        f["name"] = f_name
                        normalized_files.append(f)
                    else:
                        normalized_files.append(f_name)
                sub_structure["files"] = normalized_files

                return sub_structure
            except Exception as e:
                self.logger.info_sync(f"      Sub-structure attempt {attempt + 1} for {folder_path} failed: {e}")
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
        for file_item in json_structure.get("files", []):
            # Handle cases where LLM incorrectly returns a dict instead of a string for a file
            if isinstance(file_item, dict):
                file_name = file_item.get("name")
            else:
                file_name = str(file_item)

            if file_name:
                # Normalise to forward slashes
                rel_path = (Path(current_path) / file_name).as_posix()
                file_paths.append(rel_path)

        for folder_data in json_structure.get("folders", []):
            # Handle cases where LLM incorrectly returns a string instead of a dict for a folder
            if isinstance(folder_data, str):
                folder_name = folder_data
                new_path = (Path(current_path) / folder_name).as_posix()
            elif isinstance(folder_data, dict):
                folder_name = folder_data.get("name")
                if folder_name:
                    new_path = (Path(current_path) / folder_name).as_posix()
                    file_paths.extend(StructureGenerator.extract_file_paths(folder_data, new_path))

        return file_paths

    @staticmethod
    def create_empty_files(project_root: Path, json_structure: dict, current_path: str = ""):
        """Create empty placeholder files based on the JSON structure."""
        for file_item in json_structure.get("files", []):
            if isinstance(file_item, dict):
                file_name = file_item.get("name")
            else:
                file_name = str(file_item)

            if file_name:
                # Path normalisation: if file_name is absolute or contains redundant prefix
                if file_name.startswith("./") or file_name.startswith(".\\"):
                    file_name = file_name[2:]

                file_path = project_root / current_path / file_name
                file_path.parent.mkdir(parents=True, exist_ok=True)
                if not file_path.exists() and not file_path.is_dir():
                    try:
                        file_path.touch()
                    except Exception:
                        continue

        for folder_data in json_structure.get("folders", []):
            if isinstance(folder_data, dict):
                folder_name = folder_data.get("name")
                if folder_name:
                    # Normalise folder name
                    if folder_name.startswith("./") or folder_name.startswith(".\\"):
                        folder_name = folder_name[2:]

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
        project_type: str = "",
    ) -> dict:
        """Create a basic fallback project structure when generation fails.

        When *project_type* is provided (detected by :class:`ProjectTypeDetector`),
        returns a type-appropriate scaffold instead of the default Python layout.

        Args:
            readme_content: Unused here but kept for API consistency.
            template_name: Template identifier (passed through).
            python_version: Python version string (used by Python fallback).
            license_type: License identifier (unused in minimal fallback).
            include_docker: Whether to add Docker files (unused in minimal fallback).
            project_type: Short project-type identifier from ProjectTypeDetector
                (e.g. ``'frontend_web'``, ``'react_app'``).
        """
        if project_type == "frontend_web":
            return {
                "path": "./",
                "folders": [
                    {
                        "name": "src",
                        "folders": [],
                        "files": ["index.html", "styles.css", "app.js"],
                    }
                ],
                "files": ["README.md"],
            }
        if project_type in ("react_app", "typescript_app"):
            return {
                "path": "./",
                "folders": [
                    {
                        "name": "src",
                        "folders": [],
                        "files": ["App.tsx", "index.tsx", "App.css"],
                    }
                ],
                "files": ["README.md", "package.json", "tsconfig.json"],
            }
        if project_type == "node_backend":
            return {
                "path": "./",
                "folders": [
                    {
                        "name": "src",
                        "folders": [],
                        "files": ["index.js", "app.js", "routes.js"],
                    }
                ],
                "files": ["README.md", "package.json", ".env"],
            }
        if project_type == "go_service":
            return {
                "path": "./",
                "folders": [
                    {
                        "name": "cmd",
                        "folders": [],
                        "files": ["main.go"],
                    },
                    {
                        "name": "internal",
                        "folders": [],
                        "files": ["handler.go", "service.go"],
                    },
                ],
                "files": ["README.md", "go.mod", "go.sum"],
            }
        if project_type == "rust_project":
            return {
                "path": "./",
                "folders": [
                    {
                        "name": "src",
                        "folders": [],
                        "files": ["main.rs", "lib.rs"],
                    }
                ],
                "files": ["README.md", "Cargo.toml"],
            }
        # Default: Python fallback
        return {
            "path": "./",
            "folders": [{"name": "src", "folders": [], "files": ["main.py"]}],
            "files": ["README.md"],
        }

    @staticmethod
    def filter_structure_by_extensions(
        structure: Dict[str, Any],
        allowed_extensions: set,
        logger: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Remove files with disallowed extensions from a structure dict (recursive).

        Files without an extension (e.g. ``Makefile``, ``Dockerfile``) are always
        kept. Only removes files whose dot-suffix is not in *allowed_extensions*.

        Args:
            structure: Project structure dict with ``"files"`` and ``"folders"`` keys.
            allowed_extensions: Set of dot-prefixed extensions to keep (e.g. ``{".js", ".html"}``).
            logger: Optional logger for warning messages about removed files.

        Returns:
            A deep copy of *structure* with disallowed files removed.
        """

        def _clean_files(files_list: list) -> list:
            result = []
            for item in files_list:
                name = item.get("name") if isinstance(item, dict) else str(item)
                if not name:
                    continue
                suffix = Path(name).suffix.lower()
                # Keep files with no extension (Makefile, Dockerfile, etc.)
                if suffix == "" or suffix in allowed_extensions:
                    result.append(item)
                else:
                    if logger:
                        # Use info_sync if logger is AgentLogger
                        if hasattr(logger, "warning"):
                            # AgentLogger.warning is async, but we are in a sync nested func
                            if hasattr(logger, "info_sync"):
                                logger.info_sync(f"[StructureFilter] Removed disallowed file: '{name}'")
                            else:
                                pass
            return result

        def _clean(node: dict) -> dict:
            node["files"] = _clean_files(node.get("files", []))
            cleaned_folders = []
            for folder in node.get("folders", []):
                if isinstance(folder, dict):
                    cleaned_folders.append(_clean(folder))
                else:
                    cleaned_folders.append(folder)
            node["folders"] = cleaned_folders
            return node

        filtered = json.loads(json.dumps(structure))  # Deep copy
        return _clean(filtered)
