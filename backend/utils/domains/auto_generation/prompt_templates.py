"""Prompt templates for auto-generation workflows."""

from pathlib import Path
from typing import Tuple


class AutoGenPrompts:
    """Static methods for generating prompts for various auto-generation phases."""

    @staticmethod
    def readme_generation(
        project_description: str,
        template_name: str = "default",
        python_version: str = "3.12",
        license_type: str = "MIT",
        include_docker: bool = False,
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for README generation."""
        system = (
            "You are an expert technical writer. Create engaging, clear README.md files "
            "that help users understand and use the project effectively."
        )
        docker_note = "\nInclude Docker setup instructions." if include_docker else ""
        user = (
            f"Create a professional README.md for a project with the following details:\n"
            f"Description: {project_description}\n"
            f"Template: {template_name}\n"
            f"Python Version: {python_version}\n"
            f"License: {license_type}{docker_note}"
        )
        return system, user

    @staticmethod
    def high_level_structure_generation(description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for high-level project structure."""
        system = (
            "You are a solution architect. Design a clean, scalable project structure "
            "that follows industry best practices and the provided requirements.\n"
            "Respond ONLY with a JSON object. The JSON should represent the file structure with 'path', 'folders', and 'files' keys.\n"
            "Example format:\n"
            "```json\n"
            "{\n"
            '  "path": "./",\n'
            '  "folders": [\n'
            '    {"name": "src", "folders": [], "files": ["main.py"]}\n'
            "  ],\n"
            '  "files": ["README.md"]\n'
            "}\n"
            "```"
        )
        user = f"Create a high-level project structure for:\n\n{description}"
        return system, user

    @staticmethod
    def high_level_structure_generation_simplified(description: str) -> Tuple[str, str]:
        """Simplified version for high-level structure generation."""
        system = (
            "You are a solution architect. Design a simple project structure for this project.\n"
            "Respond ONLY with a JSON object. The JSON should represent the file structure with 'path', 'folders', and 'files' keys.\n"
            "Example format:\n"
            "```json\n"
            "{\n"
            '  "path": "./",\n'
            '  "folders": [\n'
            '    {"name": "src", "folders": [], "files": ["main.py"]}\n'
            "  ],\n"
            '  "files": ["README.md"]\n'
            "}\n"
            "```"
        )
        user = f"Project: {description}"
        return system, user

    @staticmethod
    def sub_structure_generation(structure: str, description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for sub-structure generation."""
        system = (
            "You are a software architect. Fill in details for the project structure, "
            "specifying all necessary files and folders."
        )
        user = (
            f"Expand this project structure with all necessary files and folders:\n"
            f"Structure:\n{structure}\n\nProject: {description}"
        )
        return system, user

    @staticmethod
    def sub_structure_generation_simplified(structure: str) -> Tuple[str, str]:
        """Simplified version for sub-structure generation."""
        system = "Expand the project structure with all files needed."
        user = f"Structure:\n{structure}"
        return system, user

    @staticmethod
    def file_content_generation_basic(
        file_path: str, parent_context: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for basic file content generation."""
        system = (
            "You are an expert software developer. Generate clean, complete, and well-structured code "
            "that follows best practices and the provided context."
        )
        user = f"Generate content for file '{file_path}' with the following context:\n\n{parent_context}"
        return system, user

    @staticmethod
    def file_refinement(file_path: str, content: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file refinement."""
        system = (
            "You are a senior code reviewer. Refine and improve the provided code "
            "while maintaining its intended functionality."
        )
        user = f"Please refine and improve the content of '{file_path}':\n\n{content}"
        return system, user

    @staticmethod
    def file_refinement_with_issues(
        file_path: str, content: str, issues: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file refinement with issues."""
        system = (
            "You are a senior code reviewer. Fix the identified issues in the code "
            "while improving overall quality."
        )
        user = f"Fix these issues in '{file_path}':\n{issues}\n\nCurrent content:\n{content}"
        return system, user

    @staticmethod
    def file_fix(file_path: str, content: str, error: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file fixing."""
        system = "You are an expert debugger. Analyze the error and fix the code accordingly."
        user = (
            f"Fix this error in '{file_path}':\n\nError: {error}\n\nContent:\n{content}"
        )
        return system, user

    @staticmethod
    def generate_unit_tests(
        file_path: str, content: str, readme: str = ""
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for unit test generation."""
        system = (
            "You are a QA engineer. Generate comprehensive, clear unit tests "
            "that cover the main functionality and edge cases."
        )
        context = f"Project info:\n{readme}\n\n" if readme else ""
        user = f"{context}Generate unit tests for '{file_path}':\n\n{content}"
        return system, user

    @staticmethod
    def suggest_improvements_prompt(project_summary: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for improvement suggestions."""
        system = (
            "You are a senior architect. Suggest impactful improvements for the project "
            "that enhance functionality, performance, and maintainability."
        )
        user = f"Suggest improvements for this project:\n\n{project_summary}"
        return system, user

    @staticmethod
    def generate_improvement_plan_prompt(improvements: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for improvement plan generation."""
        system = (
            "You are a project planner. Create a detailed, actionable plan "
            "to implement the suggested improvements."
        )
        user = (
            f"Create an implementation plan for these improvements:\n\n{improvements}"
        )
        return system, user

    @staticmethod
    def senior_review_prompt(project_summary: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for senior review."""
        system = (
            "You are a senior software architect with years of experience. "
            "Provide a comprehensive but concise review of the project's quality and completeness."
        )
        user = f"Review this project:\n\n{project_summary}"
        return system, user

    @staticmethod
    def project_review(project_summary: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for a final project review."""
        system = (
            "You are a senior software engineer performing a final code review. "
            "Provide a concise, high-level summary of the project's state. "
            "Comment on completeness, correctness, and adherence to the initial request. "
            "Keep the review to 3-5 sentences."
        )
        user = (
            "Please review the following project summary and provide a brief, "
            f"high-level review of its overall status.\n\n{project_summary}"
        )
        return system, user

    @staticmethod
    def file_content_generation(
        file_path: str, content: str, readme: str = ""
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file content generation."""
        system = (
            "You are an expert software developer generating production-ready code. "
            "IMPORTANT: Generate COMPLETE, working code with no TODOs or placeholders. "
            "Every function must be fully implemented. Include all necessary imports. "
            "Make code immediately usable."
        )

        file_ext = Path(file_path).suffix.lower() if "Path" in locals() else ""

        # Specialized prompts by file type
        type_guidance = ""
        if file_ext in [".py", ".pyi"]:
            type_guidance = (
                "\n- Use Python best practices and PEP 8\n"
                "- Include type hints for all functions\n"
                "- Add docstrings\n"
                "- Handle errors appropriately"
            )
        elif file_ext in [".js", ".jsx"]:
            type_guidance = (
                "\n- Use modern ES6+ syntax\n"
                "- No async/await issues\n"
                "- All functions must work immediately\n"
                "- No console errors"
            )
        elif file_ext in [".ts", ".tsx"]:
            type_guidance = (
                "\n- Use proper TypeScript type annotations\n"
                "- Interface definitions required\n"
                "- Strict null checks\n"
                "- No 'any' types unless necessary"
            )
        elif file_ext in [".html", ".vue"]:
            type_guidance = (
                "\n- Use semantic HTML5\n"
                "- Proper accessibility attributes\n"
                "- Include DOCTYPE and meta tags\n"
                "- Valid markup structure"
            )
        elif file_ext in [".css", ".scss"]:
            type_guidance = (
                "\n- Modern CSS (flexbox, grid)\n"
                "- Responsive design\n"
                "- Organized selectors\n"
                "- Comments for complex rules"
            )

        user = (
            f"Generate the COMPLETE content for: {file_path}\n\n"
            f"Project README:\n{readme[:800]}\n\n"
            f"File to generate: {file_path}\n"
            f"REQUIREMENTS:{type_guidance}\n\n"
            f"CRITICAL:\n"
            f"1. No TODO markers\n"
            f"2. No empty functions\n"
            f"3. All imports included\n"
            f"4. Production-ready immediately\n"
            f"5. Generate ONLY the file content, nothing else"
        )
        return system, user

    @staticmethod
    def architecture_planning(description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for project architecture planning."""
        system = (
            "You are a solution architect. Plan a well-structured project architecture "
            "that addresses the requirements and follows industry best practices."
        )
        user = (
            f"Create an architecture plan for the following project:\n\n{description}"
        )
        return system, user
