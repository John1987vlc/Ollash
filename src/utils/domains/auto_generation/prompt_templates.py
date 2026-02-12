import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def _format_related_files(related_files: Dict[str, str]) -> str:
    """Format related files context for prompts."""
    if not related_files:
        return ""
    context = "\nAlready generated files:\n"
    for path in related_files:
        context += f"- {path}\n"
    return context


def _detect_project_technologies(readme_content: str) -> str:
    """Extract a technology summary from the README for context.

    Scans for common technology keywords and returns a concise summary
    string. Works for any project type (web, CLI, game, embedded, etc.).
    """
    tech_keywords = {
        # Languages
        "python": "Python", "javascript": "JavaScript", "typescript": "TypeScript",
        "c#": "C#", "csharp": "C#", "java ": "Java", "golang": "Go", "go ": "Go",
        "rust": "Rust", "ruby": "Ruby", "php": "PHP", "swift": "Swift",
        "kotlin": "Kotlin", "scala": "Scala", "lua": "Lua", "perl": "Perl",
        "r ": "R", "matlab": "MATLAB", "bash": "Bash", "shell": "Shell",
        "powershell": "PowerShell", "c++": "C++", "cpp": "C++",
        # Web frameworks
        "react": "React", "next.js": "Next.js", "nextjs": "Next.js",
        "angular": "Angular", "vue": "Vue.js", "svelte": "Svelte",
        "express": "Express.js", "nestjs": "NestJS", "fastapi": "FastAPI",
        "flask": "Flask", "django": "Django", "spring": "Spring",
        "asp.net": "ASP.NET", "rails": "Rails",
        # Game engines
        "unity": "Unity", "unreal": "Unreal Engine", "godot": "Godot",
        "pygame": "Pygame", "monogame": "MonoGame",
        # Mobile
        "react native": "React Native", "flutter": "Flutter",
        "xamarin": "Xamarin", "swiftui": "SwiftUI",
        # Data / ML
        "tensorflow": "TensorFlow", "pytorch": "PyTorch", "pandas": "Pandas",
        "numpy": "NumPy", "scikit": "scikit-learn",
        # DevOps / Infra
        "docker": "Docker", "kubernetes": "Kubernetes", "terraform": "Terraform",
        "ansible": "Ansible", "nginx": "Nginx",
        # Databases
        "postgresql": "PostgreSQL", "mysql": "MySQL", "mongodb": "MongoDB",
        "redis": "Redis", "sqlite": "SQLite", "sql server": "SQL Server",
        # Build tools
        "cmake": "CMake", "make": "Make", "gradle": "Gradle", "maven": "Maven",
        "cargo": "Cargo", "npm": "npm", "yarn": "Yarn", "pip": "pip",
        "nuget": "NuGet", "dotnet": ".NET",
    }
    readme_lower = readme_content.lower()
    found = []
    for keyword, display_name in tech_keywords.items():
        if keyword in readme_lower and display_name not in found:
            found.append(display_name)

    if found:
        return "Detected technologies: " + ", ".join(found[:15])
    return "No specific technologies detected — infer from project description."


class AutoGenPrompts:
    """Centralized prompt templates for the auto-generation pipeline.

    All prompts are technology-agnostic and work for any project type:
    web apps, CLI tools, scripts, games, libraries, microservices, etc.

    All prompts instruct models to output RAW file content without markdown fences.
    """

    @staticmethod
    def readme_generation(project_description: str, template_name: str, python_version: str, license_type: str, include_docker: bool) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 1."""
        system = (
            "You are a senior software architect. "
            "Create comprehensive, detailed technical documentation. "
            "Adapt the README structure to fit the project type — "
            "do NOT assume the project is a web application. "
            "Integrate the following specific project details seamlessly into the README."
        )
        user = (
            f"Generate a comprehensive and detailed README.md for the following project, "
            f"considering the user's choices:\n\n"
            f"Project Description: {project_description}\n"
            f"Selected Template: {template_name}\n"
            f"Python Version: {python_version}\n"
            f"License Type: {license_type}\n"
            f"Include Docker: {'Yes' if include_docker else 'No'}\n\n"
            "The README should include:\n"
            "- Project title and description\n"
            "- Main features and functionality\n"
            "- Technology stack (languages, frameworks, libraries, tools)\n"
            "- Project structure overview\n"
            "- Installation and setup instructions (tailored to Python version and Docker if included)\n"
            "- Usage examples\n"
            "- Build/run commands appropriate for the project type (including Docker if requested)\n\n"
            "Be thorough and specific. This README will be used to generate the "
            "entire project structure. Adapt the format to the project type — "
            "not every project has a frontend/backend split.\n\n"
        )
        return system, user

    @staticmethod
    def high_level_structure_generation(readme_content: str, template_name: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for high-level structure generation."""
        tech_summary = _detect_project_technologies(readme_content)

        system = (
            "You are an expert at designing comprehensive, high-level project file structures "
            "for ANY type of software project (web apps, CLI tools, games, scripts, "
            "libraries, microservices, embedded systems, etc.).\n\n"
            f"The user has selected the '{template_name}' template. This should guide your decisions.\n\n"
            "Your task: given a project README.md, output a single JSON object "
            "representing the TOP-LEVEL folders and root files of the project. "
            "Do NOT include nested folders or files within subdirectories at this stage. "
            "Focus ONLY on the immediate children of the project root.\n\n"
            "The JSON format must follow this structure exactly:\n"
            "{\n"
            '  "path": "./",\n'
            '  "folders": [\n'
            "    {\n"
            '      "name": "top-level-folder-name",\n'
            '      "folders": [],\n'  # MUST be empty
            '      "files": []\n'     # MUST be empty
            "    }\n"
            "  ],\n"
            '  "files": ["rootfile.ext"]\n'
            "}\n\n"
            "Rules:\n"
            "- Infer the structure strictly from the README.md content.\n"
            "- Only include folders directly under the project root.\n"
            "- Only include files directly under the project root.\n"
            "- Do NOT include any nested folders or files within the 'folders' entries.\n"
            "- Include files appropriate for the detected technologies "
            "(e.g., Makefile, .csproj, Cargo.toml, setup.py, package.json, build.gradle, CMakeLists.txt, etc.).\n"
            "- Output ONLY valid JSON, no comments, no markdown, no prose.\n"
            "- The structure should follow best practices for the detected tech stack."
        )
        user = (
            "Based on the following README.md, generate the HIGH-LEVEL JSON project structure. "
            "Only include top-level folders and root files.\n\n"
            f"{tech_summary}\n\n"
            f"Project README:\n{readme_content}\n\n"
            "Remember: Output ONLY the complete JSON, nothing else."
        )
        return system, user

    @staticmethod
    def high_level_structure_generation_simplified(readme_content: str, template_name: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for simplified high-level structure generation."""
        tech_summary = _detect_project_technologies(readme_content)

        system = (
            "You are an expert at designing simple project file structures. "
            f"The user has selected the '{template_name}' template. Keep this in mind when simplifying.\n\n"
            "Your task is to output a single JSON object representing the "
            "MINIMAL TOP-LEVEL folders and root files of a project. "
            "Do NOT include nested folders or files within subdirectories. "
            "Focus ONLY on the immediate children of the project root.\n\n"
            "The JSON format must follow this structure exactly:\n"
            "{\n"
            '  "path": "./",\n'
            '  "folders": [\n'
            "    {\n"
            '      "name": "folder-name",\n'
            '      "folders": [],\n'  # MUST be empty
            '      "files": []\n'     # MUST be empty
            "    }\n"
            "  ],\n"
            '  "files": ["rootfile.ext"]\n'
            "}\n\n"
            "Rules:\n"
            "- Infer the structure from the README.md content, keep it minimal.\n"
            "- Output ONLY valid JSON, no comments, no markdown, no prose.\n"
            "- The structure should be very basic, only essential top-level items."
        )
        user = (
            "Generate a MINIMAL HIGH-LEVEL JSON project structure for a project "
            "described by the following README.md. Only include top-level folders and root files.\n\n"
            f"{tech_summary}\n\n"
            f"Project README (summary): {readme_content[:500]}...\n\n"
            "Remember: Output ONLY the complete JSON, nothing else."
        )
        return system, user

    @staticmethod
    def sub_structure_generation(
        folder_path: str, readme_content: str, overall_structure_str: str, template_name: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for sub-structure generation."""
        tech_summary = _detect_project_technologies(readme_content)

        system = (
            "You are an expert at recursively detailing project file structures. "
            f"The user has selected the '{template_name}' template. Ensure the sub-structure aligns with this.\n\n"
            "Your task is to generate the JSON structure (sub-folders and files) "
            "specifically for the folder path provided, given the overall project context.\n\n"
            "The JSON format must follow this structure exactly (for the *contents* of the folder):\n"
            "{\n"
            '  "folders": [\n'
            "    {\n"
            '      "name": "nested-folder-name",\n'
            '      "folders": [],\n'
            '      "files": []\n'
            "    }\n"
            "  ],\n"
            '  "files": ["file-in-this-folder.ext"]\n'
            "}\n\n"
            "Rules:\n"
            f"- Generate the detailed structure for the folder: {folder_path}\n"
            "- Infer the structure from the README.md content and the overall project structure.\n"
            "- Do NOT include the 'path' field in the output JSON. "
            "The output should only describe the *contents* (folders and files) of the specified folder.\n"
            "- Fill in the 'folders' and 'files' arrays recursively with their immediate children.\n"
            "- Output ONLY valid JSON, no comments, no markdown, no prose.\n"
            "- Complete the ENTIRE JSON structure for this folder. Do not truncate.\n"
            "- The structure should follow best practices for the detected tech stack."
        )
        user = (
            f"Generate the detailed JSON structure for the folder: {folder_path}\n\n"
            f"{tech_summary}\n\n"
            f"Project README:\n{readme_content}\n\n"
            f"Overall Project Structure (for context):\n{overall_structure_str}\n\n"
            "Remember: Output ONLY the complete JSON (for the folder's contents), nothing else. "
            "Do NOT include the 'path' field."
        )
        return system, user

    @staticmethod
    def sub_structure_generation_simplified(
        folder_path: str, readme_content: str, overall_structure_str: str, template_name: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for simplified sub-structure generation."""
        tech_summary = _detect_project_technologies(readme_content)

        system = (
            "You are an expert at designing simple, nested project file structures. "
            f"The user has selected the '{template_name}' template. Keep this in mind when simplifying.\n\n"
            "Your task is to generate a MINIMAL JSON structure (sub-folders and files) "
            "specifically for the folder path provided.\n\n"
            "The JSON format must follow this structure exactly (for the *contents* of the folder):\n"
            "{\n"
            '  "folders": [\n'
            "    {\n"
            '      "name": "nested-folder-name",\n'
            '      "folders": [],\n'  # MUST be empty
            '      "files": []\n'     # MUST be empty
            "    }\n"
            "  ],\n"
            '  "files": ["file-in-this-folder.ext"]\n'
            "}\n\n"
            "Rules:\n"
            f"- Generate the detailed structure for the folder: {folder_path}\n"
            "- Infer the structure from the README.md content, keep it minimal.\n"
            "- Do NOT include the 'path' field in the output JSON. "
            "The output should only describe the *contents* (folders and files) of the specified folder.\n"
            "- Output ONLY valid JSON, no comments, no markdown, no prose.\n"
            "- The structure should be very basic, only essential immediate children."
        )
        user = (
            f"Generate a MINIMAL JSON structure for the folder: {folder_path}\n\n"
            f"{tech_summary}\n\n"
            f"Project README (summary): {readme_content[:500]}...\n\n"
            f"Overall Project Structure (for context): {overall_structure_str[:500]}...\n\n"
            "Remember: Output ONLY the complete JSON (for the folder's contents), nothing else. "
            "Do NOT include the 'path' field."
        )
        return system, user
    
    @staticmethod
    def file_content_generation(file_path: str, readme_content: str, json_structure: dict, related_files: Dict[str, str]) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for generating file content."""
        related_files_context = _format_related_files(related_files)
        tech_summary = _detect_project_technologies(readme_content)

        system = (
            "You are an expert programmer. Your task is to generate the complete, "
            "functional source code for a given file path based on the project context. "
            "The project can be of ANY type. The code MUST be complete and production-ready.\n"
            "Output ONLY the raw file content. Do NOT include markdown fences, "
            "explanations, or any other prose. Start directly with the first line of the file."
        )
        user = (
            f"Generate the complete source code for the following file: {file_path}\n\n"
            f"{tech_summary}\n\n"
            f"Project README:\n{readme_content}\n\n"
            f"Overall Project Structure:\n{json.dumps(json_structure, indent=2)}\n"
            f"{related_files_context}\n\n"
            "Requirements:\n"
            "- The code must be complete, functional, and production-ready.\n"
            "- Implement all functions, classes, and logic based on the file's purpose within the project.\n"
            "- Do not use placeholder comments like '// TODO' or '...'.\n"
            "- Adhere to best practices for the detected programming language.\n"
            "- Ensure the code is consistent with the overall project structure and other files.\n"
            "- Output ONLY the raw file content, nothing else.\n"
            "- Do NOT wrap in markdown code blocks."
        )
        return system, user

    @staticmethod
    def file_refinement(file_path: str, current_content: str, readme_excerpt: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for refining a file."""
        system = (
            "You are a senior developer tasked with refining a file. "
            "Review the code for correctness, completeness, and adherence to best practices. "
            "Output ONLY the complete, corrected raw file content. "
            "No markdown fences. No explanation."
        )
        user = (
            f"Refine the following file: {file_path}\n\n"
            f"Current content:\n```\n{current_content}\n```\n\n"
            f"Project context:\n{readme_excerpt}\n\n"
            "Requirements:\n"
            "- Improve the code quality, clarity, and performance.\n"
            "- Fix any potential bugs or logical errors.\n"
            "- Ensure the code is complete and functional.\n"
            "- Output ONLY the complete refined raw file content, nothing else."
        )
        return system, user

    @staticmethod
    def file_refinement_with_issues(file_path: str, current_content: str, readme_excerpt: str, issues: List[Dict]) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for refining a file based on issues."""
        issues_str = "\n".join([
            f"- {issue['severity'].upper()}: {issue['description']} (Recommendation: {issue['recommendation']})"
            for issue in issues
        ])
        system = (
            f"You are fixing code in: {file_path} based on a list of issues.\n"
            "Output ONLY the complete corrected raw file content. "
            "No markdown fences. No explanation."
        )
        user = (
            f"The following file has issues that need to be addressed. Analyze the issues and "
            f"output the COMPLETE corrected file content to resolve them.\n\n"
            f"File: {file_path}\n\n"
            f"Issues to address:\n{issues_str}\n\n"
            f"Current content:\n```\n{current_content}\n```\n\n"
            f"Project context:\n{readme_excerpt}\n\n"
            "Requirements:\n"
            "- Address ALL listed issues.\n"
            "- Ensure the corrected code is syntactically correct and adheres to best practices.\n"
            "- Output ONLY the complete corrected raw file content, nothing else."
        )
        return system, user

    @staticmethod
    def file_fix(file_path: str, current_content: str, error_message: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for fixing a file based on an error."""
        system = (
            f"You are fixing a syntax or logical error in: {file_path}.\n"
            "Output ONLY the complete corrected raw file content. "
            "No markdown fences. No explanation."
        )
        user = (
            f"The following file has an error. Analyze the error and "
            f"output the COMPLETE corrected file content to resolve it.\n\n"
            f"File: {file_path}\n\n"
            f"Error message:\n```\n{error_message}\n```\n\n"
            f"Current content:\n```\n{current_content}\n```\n\n"
            "Requirements:\n"
            "- Fix the specified error.\n"
            "- Ensure the corrected code is syntactically correct and adheres to best practices.\n"
            "- Output ONLY the complete corrected raw file content, nothing else."
        )
        return system, user

    @staticmethod
    def generate_unit_tests(file_path: str, content: str, readme_context: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for generating unit tests."""
        system = (
            "You are an expert at writing comprehensive unit tests for any programming language. "
            "Your task is to generate unit tests for the given source file, ensuring good coverage "
            "and adherence to best practices for the detected language and testing framework.\n"
            "Output ONLY the raw content of the test file. Do NOT include markdown fences, "
            "explanations, or any other prose. Start directly with the first line of the test file."
        )
        user = (
            f"Generate unit tests for the following file: {file_path}\n\n"
            f"File content:\n```\n{content}\n```\n\n"
            f"Project README Context:\n```\n{readme_context}\n```\n\n"
            "Requirements:\n"
            "- Use 'pytest' framework for Python.\n"
            "- Ensure comprehensive test coverage for functions, classes, and edge cases.\n"
            "- Mock dependencies as necessary.\n"
            "- The test file should be named appropriately (e.g., test_module.py).\n"
            "- Output ONLY the raw test file content, nothing else.\n"
            "- Do NOT wrap in markdown code blocks.\n"
            "- Include necessary imports and comments."
        )
        return system, user

    @staticmethod
    def file_fix_test_failure(
        file_path: str, current_content: str, readme_excerpt: str, test_failures: List[Dict]
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for fixing file based on test failures."""
        failures_str = "\n".join([
            f"- Test: {f.get('nodeid')}\n  Message: {f.get('message')}\n  Traceback: {f.get('traceback')}"
            for f in test_failures
        ])
        system = (
            f"You are fixing code in: {file_path} based on unit test failures.\n"
            "Output ONLY the complete corrected raw file content. "
            "No markdown fences. No explanation."
        )
        user = (
            f"The following file has unit test failures. Analyze the failures and "
            f"output the COMPLETE corrected file content to resolve them.\n\n"
            f"File: {file_path}\n\n"
            f"Unit Test Failures:\n```\n{failures_str}\n```\n\n"
            f"Current content:\n```\n{current_content}\n```\n\n"
            f"Project context:\n{readme_excerpt}\n\n"
            "Requirements:\n"
            "- Address ALL listed test failures.\n"
            "- Ensure the corrected code is syntactically correct and adheres to best practices.\n"
            "- Keep existing functionality intact where not related to the failures.\n"
            "- Output ONLY the complete corrected raw file content, nothing else.\n"
            "- Do NOT wrap in markdown code blocks."
        )
        return system, user

    @staticmethod
    def senior_review_prompt(
        project_description: str,
        project_name: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
        review_attempt: int,
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for a senior-level project review."""
        tech_summary = _detect_project_technologies(readme_content)

        system = (
            "You are a highly experienced Senior Software Architect and Lead Developer. "
            "Your task is to perform a rigorous, critical review of a software project. "
            "The project can be of ANY type (web app, CLI tool, game, script, library, etc.). "
            "Your assessment should ensure the project is correct, complete, logical, "
            "adheres to best practices, and fully addresses the initial description.\n\n"
            "You MUST check for the following completeness criteria:\n"
            "1. Source code files must have functional implementations — "
            "not empty functions, TODO stubs, or placeholder code.\n"
            "2. Configuration and build files must be complete and valid for their format.\n"
            "3. Documentation files must have all sections filled with actual descriptive content — "
            "no TODO placeholders, empty sections, or 'lorem ipsum' text.\n"
            "4. Cross-file consistency: imports must reference existing files/modules, "
            "routes/endpoints must be consistent, dependencies must match actual usage.\n"
            "5. Build/run instructions in README must match the actual project structure.\n"
            "6. Language-specific best practices must be followed "
            "(proper project layout, naming conventions, error handling).\n\n"
            "Provide your review in JSON format, indicating overall status and specific issues."
        )

        file_context = ""
        for path, content in current_files.items():
            truncated = content[:2000]
            suffix = "...[TRUNCATED]" if len(content) > 2000 else ""
            file_context += f"--- File: {path} ({len(content)} chars total) ---\n{truncated}{suffix}\n\n"

        user = (
            f"Perform a comprehensive review of the project '{project_name}' (Review Attempt {review_attempt}).\n\n"
            f"{tech_summary}\n\n"
            f"Project Description: {project_description}\n\n"
            f"Project README:\n{readme_content}\n\n"
            f"Project Structure (current):\n{json.dumps(json_structure, indent=2)}\n\n"
            f"All currently generated files (up to 2000 chars each):\n{file_context}"
            "IMPORTANT REVIEW CHECKLIST — You MUST check each item:\n"
            "- Are source code files fully implemented (no empty functions or TODO stubs)?\n"
            "- Are config/build files complete and valid for their format?\n"
            "- Is the documentation fully written with actual content in every section?\n"
            "- Do imports and references point to files that actually exist?\n"
            "- Are build/run instructions in the README accurate?\n"
            "- Does the project follow best practices for its technology stack?\n\n"
            "Provide your review in JSON format with the following keys:\n"
            "- 'status': (string) 'passed' if the project is complete and satisfactory, 'failed' otherwise.\n"
            "- 'summary': (string) A concise overall assessment of the project.\n"
            "- 'issues': (list of objects) A list of specific, actionable issues if the status is 'failed'. "
            "Each issue object must have:\n"
            "  - 'description': (string) Detail the problem.\n"
            "  - 'severity': (string) 'critical', 'major', 'minor'.\n"
            "  - 'recommendation': (string) Suggest a concrete solution.\n"
            "  - 'file': (string, optional) The relative path to the file most relevant to the issue.\n\n"
            "If the project 'passed', the 'issues' list should be empty.\n"
            "Output ONLY the JSON, nothing else."
        )
        return system, user