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
            "You are a Senior Technical Writer. Your goal is to produce professional, "
            "comprehensive, and highly readable documentation. Focus on clarity, "
            "visual hierarchy, and actionable instructions."
        )
        docker_note = (
            "\n- Include a 'Docker' section with a Dockerfile example and run commands." if include_docker else ""
        )
        user = (
            f"Generate a professional README.md for the following project:\n"
            f"PROJECT DESCRIPTION: {project_description}\n"
            f"CONSTRAINTS:\n"
            f"- Template Style: {template_name}\n"
            f"- Tech Stack: Python {python_version}\n"
            f"- License: {license_type}{docker_note}\n\n"
            "THE README MUST INCLUDE:\n"
            "1. Project Overview & Value Proposition\n"
            "2. Key Features (bulleted list)\n"
            "3. Visual/Architecture overview (placeholder or description)\n"
            "4. Quick Start (Dependencies, Installation, Execution)\n"
            "5. Project Structure description\n\n"
            "Output ONLY the markdown content."
        )
        return system, user

    @staticmethod
    def high_level_structure_generation(description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for high-level project structure."""
        system = (
            "You are a Senior Solution Architect. Design a scalable, modular project "
            "structure following industry best practices (SOLID, Clean Architecture, etc.).\n"
            "Respond ONLY with a valid JSON object. No preambles, no chat."
        )
        user = (
            f"Design the high-level folder/file structure for this project:\n\n{description}\n\n"
            "JSON SCHEMA:\n"
            "{\n"
            '  "path": "./",\n'
            '  "folders": [\n'
            '    {"name": "folder_name", "folders": [], "files": ["file1.ext"]}\n'
            "  ],\n"
            '  "files": ["README.md", "requirements.txt"]\n'
            "}\n"
        )
        return system, user

    @staticmethod
    def sub_structure_generation(
        folder_path: str, readme_content: str, overall_structure: str, template_name: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for sub-structure generation."""
        system = (
            "You are a Software Architect. Your task is to expand a specific directory "
            "within a project structure. Ensure consistency with existing files and architecture."
        )
        user = (
            f"Expand the folder: '{folder_path}'\n\n"
            f"PROJECT CONTEXT (README):\n{readme_content[:800]}\n\n"
            f"OVERALL STRUCTURE (CONTEXT):\n{overall_structure}\n\n"
            f"TEMPLATE: {template_name}\n\n"
            "REQUIREMENT: Return ONLY a JSON object with 'folders' and 'files' for the target folder."
        )
        return system, user

    @staticmethod
    def file_content_generation(file_path: str, content: str, readme: str = "") -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file content generation."""
        system = (
            "You are an Expert Software Engineer. Generate production-ready, complete, "
            "and idiomatic code. CRITICAL: No TODOs, no 'implementation goes here' "
            "placeholders, no empty functions. Every line must be functional."
        )

        file_ext = Path(file_path).suffix.lower()

        guidance = {
            ".py": "- Use PEP 8, strict type hints, Google-style docstrings, and robust error handling.",
            ".js": "- Use modern ES6+, async/await for I/O, and descriptive naming.",
            ".ts": "- Define strict interfaces/types, avoid 'any', and use ES Modules.",
            ".html": "- Use semantic HTML5, ARIA labels, and clean structure.",
            ".css": "- Use modern CSS (Grid/Flexbox) and a logical ordering of properties.",
        }
        type_guidance = guidance.get(file_ext, "- Follow language-specific best practices and idioms.")

        user = (
            f"Generate COMPLETE source code for: {file_path}\n\n"
            f"CONTEXT (README):\n{readme[:1000]}\n\n"
            f"TECHNICAL GUIDANCE:\n{type_guidance}\n\n"
            f"STRICT RULES:\n"
            "1. NO PLACEHOLDERS. NO TODOs.\n"
            "2. EVERY function/method must be fully implemented.\n"
            "3. Include ALL necessary imports/dependencies.\n"
            "4. Return ONLY the code content."
        )
        return system, user

    @staticmethod
    def architecture_planning(description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for project architecture planning."""
        system = (
            "You are a Chief Architect. Create a high-level technical blueprint "
            "specifying design patterns, tech stack justifications, and data flow."
        )
        user = f"Define the architectural strategy for:\n\n{description}"
        return system, user

    @staticmethod
    def file_content_generation_basic(file_path: str, parent_context: str) -> Tuple[str, str]:
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
    def file_refinement_with_issues(file_path: str, content: str, issues: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file refinement with issues."""
        system = (
            "You are a senior code reviewer. Fix the identified issues in the code while improving overall quality."
        )
        user = f"Fix these issues in '{file_path}':\n{issues}\n\nCurrent content:\n{content}"
        return system, user

    @staticmethod
    def file_fix(file_path: str, content: str, error: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file fixing."""
        system = "You are an expert debugger. Analyze the error and fix the code accordingly."
        user = f"Fix this error in '{file_path}':\n\nError: {error}\n\nContent:\n{content}"
        return system, user

    @staticmethod
    def generate_unit_tests(file_path: str, content: str, readme: str = "") -> Tuple[str, str]:
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
            "You are a project planner. Create a detailed, actionable plan to implement the suggested improvements."
        )
        user = f"Create an implementation plan for these improvements:\n\n{improvements}"
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
