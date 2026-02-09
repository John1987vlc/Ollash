import json
import re
from pathlib import Path
from typing import Dict, List, Tuple


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
    def readme_generation(project_description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 1."""
        system = (
            "You are a senior software architect. "
            "Create comprehensive, detailed technical documentation. "
            "Adapt the README structure to fit the project type — "
            "do NOT assume the project is a web application."
        )
        user = (
            "Create a comprehensive and detailed README.md for the following project. "
            "The README should include:\n"
            "- Project title and description\n"
            "- Main features and functionality\n"
            "- Technology stack (languages, frameworks, libraries, tools)\n"
            "- Project structure overview\n"
            "- Installation and setup instructions\n"
            "- Usage examples\n"
            "- Build/run commands appropriate for the project type\n\n"
            "Be thorough and specific. This README will be used to generate the "
            "entire project structure. Adapt the format to the project type — "
            "not every project has a frontend/backend split.\n\n"
            f"Project Description: {project_description}"
        )
        return system, user

    @staticmethod
    def structure_generation(readme_content: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 2."""
        # Extract Project Structure section from README if it exists
        project_structure_section_match = re.search(
            r"##\s+.*?Project Structure.*?\n(.*?)(?=\n##|\Z)",
            readme_content,
            re.DOTALL | re.IGNORECASE,
        )
        project_structure_hint = ""
        if project_structure_section_match:
            project_structure_hint = (
                "\n\nHere is a suggested 'Project Structure' section from the README "
                "to guide your JSON output:\n"
                f"{project_structure_section_match.group(1).strip()}\n"
            )

        tech_summary = _detect_project_technologies(readme_content)

        system = (
            "You are an expert at designing comprehensive project file structures "
            "for ANY type of software project (web apps, CLI tools, games, scripts, "
            "libraries, microservices, embedded systems, etc.).\n\n"
            "Your task: given a project README.md, output a single JSON object "
            "representing the COMPLETE and DETAILED project file structure.\n\n"
            "The JSON format must follow this structure exactly:\n"
            "{\n"
            '  "path": "./",\n'
            '  "folders": [\n'
            "    {\n"
            '      "name": "folder-name",\n'
            '      "folders": [],\n'
            '      "files": ["file1.ext", "file2.ext"]\n'
            "    }\n"
            "  ],\n"
            '  "files": ["rootfile.ext"]\n'
            "}\n\n"
            "Rules:\n"
            "- Infer the structure strictly from the README.md content.\n"
            "- If there is an explicit 'Project Structure' section, prioritize it.\n"
            "- Include files appropriate for the detected technologies "
            "(e.g., Makefile for C/C++, .csproj for C#, Cargo.toml for Rust, "
            "setup.py/pyproject.toml for Python, package.json for Node.js, "
            "build.gradle for Java/Kotlin, CMakeLists.txt for CMake, etc.).\n"
            "- Do not invent features not described in the README.\n"
            "- Output ONLY valid JSON, no comments, no markdown, no prose.\n"
            "- Complete the ENTIRE JSON structure. Do not truncate.\n"
            "- The structure should follow best practices for the detected tech stack."
        )
        user = (
            "Based on the following README.md, generate the COMPLETE and DETAILED "
            "JSON project structure.\n\n"
            f"{tech_summary}\n\n"
            f"Project README:\n{readme_content}\n"
            f"{project_structure_hint}\n\n"
            "Remember: Output ONLY the complete JSON, nothing else."
        )
        return system, user

    @staticmethod
    def file_content_generation(
        file_path: str,
        readme_content: str,
        json_structure: dict,
        related_files: Dict[str, str],
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 4.

        Instructs model to output raw file content without markdown.
        Works for any file type in any project.
        """
        ext = Path(file_path).suffix.lower()
        filename = Path(file_path).name

        # Provide language-aware hints
        hints = []
        if ext == ".py" and filename == "__init__.py":
            hints.append("- This is a Python __init__.py, provide proper imports")
        elif ext in (".json",):
            hints.append("- Output must be valid JSON starting with { or [")
        elif ext in (".yaml", ".yml"):
            hints.append("- Output must be valid YAML")
        elif ext in (".toml",):
            hints.append("- Output must be valid TOML")
        elif ext in (".xml", ".csproj", ".fsproj"):
            hints.append("- Output must be valid XML")
        elif ext in (".sh", ".bash"):
            hints.append("- Start with appropriate shebang (e.g., #!/bin/bash)")
        elif ext in (".bat", ".cmd"):
            hints.append("- Use Windows batch syntax")
        elif ext in (".ps1",):
            hints.append("- Use PowerShell syntax")
        elif ext in (".sln",):
            hints.append("- Use Visual Studio solution file format")

        extra_hints = "\n".join(hints)
        if extra_hints:
            extra_hints = "\n" + extra_hints

        system = (
            f"You are generating the file: {file_path}\n"
            "Output ONLY the raw file content. "
            "Do NOT use markdown code blocks or ``` fences. "
            "Do NOT include any explanation before or after the content. "
            "Start directly with the first line of the file."
        )
        user = (
            f"Generate the COMPLETE content for: {file_path}\n\n"
            f"Project README:\n{readme_content}\n\n"
            f"Project Structure:\n{json.dumps(json_structure, indent=2)}\n"
            f"{_format_related_files(related_files)}\n"
            "Requirements:\n"
            "- Output ONLY the raw file content, nothing else\n"
            "- Do NOT wrap in markdown code blocks\n"
            "- Include necessary imports, comments, and documentation\n"
            "- If it's a config file, provide appropriate configuration\n"
            "- The file must be complete and syntactically correct\n"
            "- Follow best practices for the language/technology"
            f"{extra_hints}\n"
        )
        return system, user

    @staticmethod
    def file_refinement(
        file_path: str, current_content: str, readme_excerpt: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 5."""
        system = (
            f"You are refining: {file_path}\n"
            "Output ONLY the improved raw file content. "
            "No markdown fences. No explanation."
        )
        user = (
            f"Improve the following file: {file_path}\n\n"
            f"Current content:\n{current_content}\n\n"
            f"Project context:\n{readme_excerpt}\n\n"
            "Tasks:\n"
            "- Add error handling where appropriate\n"
            "- Improve code quality and efficiency\n"
            "- Add missing documentation\n"
            "- Fix any obvious bugs or issues\n"
            "- Keep existing functionality intact\n\n"
            "Output ONLY the complete improved file content. "
            "No markdown code blocks. No explanation."
        )
        return system, user

    @staticmethod
    def file_refinement_with_issues(
        file_path: str,
        current_content: str,
        readme_excerpt: str,
        issues: List[Dict],
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for issue-aware refinement."""
        issues_text = "\n".join(
            f"- [{issue.get('severity', 'unknown').upper()}] {issue.get('description', '')} "
            f"→ Recommendation: {issue.get('recommendation', 'N/A')}"
            for issue in issues
        )
        system = (
            f"You are fixing specific issues in: {file_path}\n"
            "Output ONLY the complete corrected raw file content. "
            "No markdown fences. No explanation."
        )
        user = (
            f"Fix the following issues in file: {file_path}\n\n"
            f"Issues identified by senior reviewer:\n{issues_text}\n\n"
            f"Current content:\n{current_content}\n\n"
            f"Project context:\n{readme_excerpt}\n\n"
            "Requirements:\n"
            "- Address ALL listed issues\n"
            "- Keep existing functionality intact\n"
            "- Ensure the file is COMPLETE — no placeholders, TODOs, or stub code\n"
            "- All source files must have functional implementations, not empty functions\n"
            "- All config files must be complete and valid\n"
            "- All documentation files must have real content under every heading\n\n"
            "Output ONLY the complete improved file content. "
            "No markdown code blocks. No explanation."
        )
        return system, user

    @staticmethod
    def file_fix(
        file_path: str, current_content: str, validation_error: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for verification-fix loop."""
        system = (
            f"You are fixing the file: {file_path}\n"
            "Output ONLY the corrected raw file content. "
            "No markdown fences. No explanation."
        )
        user = (
            f"The following file failed validation. Fix it and output the COMPLETE "
            f"corrected file.\n\n"
            f"File: {file_path}\n\n"
            f"Validation error: {validation_error}\n\n"
            f"Current content:\n{current_content}\n\n"
            "Output ONLY the corrected raw file content. "
            "No markdown. No explanation."
        )
        return system, user

    @staticmethod
    def project_review(project_summary: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for Phase 6."""
        system = "You are conducting a final project review."
        user = (
            f"Review the following project and provide a brief assessment:\n\n"
            f"{project_summary}\n\n"
            "Provide:\n"
            "1. Overall quality assessment (1-10)\n"
            "2. Key strengths\n"
            "3. Potential improvements\n"
            "4. Any critical issues to address\n\n"
            "Keep your response concise and actionable."
        )
        return system, user

    @staticmethod
    def suggest_improvements_prompt(
        project_description: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
        loop_num: int,
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for suggesting improvements."""
        system = (
            "You are an AI assistant specialized in software architecture and code quality. "
            "Your task is to analyze a software project of ANY type and suggest "
            "concrete improvements to make it more complete, functional, and adhere to best practices. "
            "Adapt your analysis to the project's technology stack — "
            "do NOT assume it is a web application."
        )
        # Prepare file context
        file_context = ""
        for path, content in list(current_files.items())[:10]:
            truncated = content[:1000]
            suffix = "..." if len(content) > 1000 else ""
            file_context += f"--- File: {path} ---\n{truncated}{suffix}\n\n"

        tech_summary = _detect_project_technologies(readme_content)

        user = (
            f"Analyze the following project at its current state (Iteration {loop_num}). "
            "Identify 3-5 concrete, actionable improvements that would significantly enhance the project's "
            "completeness, functionality, or code quality, based on the initial project description and README.\n\n"
            "Consider aspects like:\n"
            "- Missing core functionalities or features mentioned in the README.\n"
            "- Incomplete or invalid configuration files for the project's tech stack.\n"
            "- Source files with empty/stub functions, TODO placeholders, or placeholder content.\n"
            "- Documentation files with empty sections or placeholder text.\n"
            "- Missing build scripts, dependency manifests, or project metadata files.\n"
            "- Best practices for the specific technologies used.\n\n"
            f"{tech_summary}\n\n"
            f"Project Description: {project_description}\n\n"
            f"Project README:\n{readme_content}\n\n"
            f"Project Structure (current):\n{json.dumps(json_structure, indent=2)}\n\n"
            f"Currently generated files (first 1000 chars of each):\n{file_context}"
            "Output your suggestions as a markdown bullet list. Each suggestion should be concise "
            "and clearly state what needs to be improved."
        )
        return system, user

    @staticmethod
    def generate_improvement_plan_prompt(
        suggestions: List[str],
        project_description: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for generating an improvement plan."""
        system = (
            "You are an AI project manager and architect. "
            "Your task is to create a detailed, step-by-step plan to implement "
            "a set of suggested improvements for a software project of ANY type. "
            "The plan should be in JSON format and describe concrete actions."
        )

        suggestions_str = "\n".join([f"- {s}" for s in suggestions])

        file_context = ""
        for path, content in list(current_files.items())[:10]:
            truncated = content[:1000]
            suffix = "..." if len(content) > 1000 else ""
            file_context += f"--- File: {path} ---\n{truncated}{suffix}\n\n"

        user = (
            "Based on the following project context and suggested improvements, "
            "create a detailed action plan in JSON format. "
            "The plan should prioritize actions and describe how to achieve each suggestion.\n\n"
            f"Suggested Improvements:\n{suggestions_str}\n\n"
            f"Project Description: {project_description}\n\n"
            f"Project README:\n{readme_content}\n\n"
            f"Project Structure (current):\n{json.dumps(json_structure, indent=2)}\n\n"
            f"Currently generated files (first 1000 chars of each):\n{file_context}"
            "The JSON plan should be a single object with an 'actions' key, "
            "which is a list of action objects. Each action object must have:\n"
            "- 'type': 'create_file', 'modify_file', 'create_folder', 'delete_file'\n"
            "- 'path': (string) The relative path to the file/folder. Required for 'create_file', 'modify_file', 'delete_file'.\n"
            "- 'target_folder': (string) The relative path to the folder. Required for 'create_folder'.\n"
            "- 'description': (string) A brief explanation of the action.\n"
            "- 'content': (string, optional) The full content for 'create_file' or 'modify_file' if the content is small and deterministic. "
            "Otherwise, leave empty for LLM to generate dynamically.\n\n"
            "Output ONLY the JSON plan, nothing else."
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
