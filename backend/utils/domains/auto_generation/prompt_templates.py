"""
Refactored AutoGenPrompts to use centralized YAML prompts.
Maintains the same interface while loading text from /backend/prompts/domains/auto_generation/*.yaml.
"""

import logging
from pathlib import Path
from typing import Tuple
from backend.utils.core.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

class AutoGenPrompts:
    """Static methods for generating prompts for various auto-generation phases."""

    _loader = PromptLoader()

    @staticmethod
    def readme_generation(
        project_description: str,
        template_name: str = "default",
        python_version: str = "3.12",
        license_type: str = "MIT",
        include_docker: bool = False,
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for README generation."""
        content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/readme.yaml")
        system = content.get("system_prompt", "")
        user_template = content.get("user_prompt", "")

        docker_note = (
            "\n- Include a 'Docker' section with a Dockerfile example and run commands." if include_docker else ""
        )

        user = user_template.format(
            project_description=project_description,
            template_name=template_name,
            python_version=python_version,
            license_type=license_type,
            docker_note=docker_note
        )
        return system, user

    @staticmethod
    def high_level_structure_generation(description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for high-level project structure."""
        content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/structure.yaml")
        high_level = content.get("high_level", {})
        system = high_level.get("system", "")
        user = high_level.get("user", "").format(description=description)
        return system, user

    @staticmethod
    def sub_structure_generation(
        folder_path: str, readme_content: str, overall_structure: str, template_name: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for sub-structure generation."""
        content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/structure.yaml")
        sub_structure = content.get("sub_structure", {})
        system = sub_structure.get("system", "")

        # Limit readme_content context
        user = sub_structure.get("user", "").format(
            folder_path=folder_path,
            readme_content=readme_content[:800],
            overall_structure=overall_structure,
            template_name=template_name
        )
        return system, user

    @staticmethod
    def file_content_generation(file_path: str, content: str, readme: str = "") -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file content generation."""
        prompt_content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/code_gen.yaml")
        file_gen = prompt_content.get("file_content", {})
        system = file_gen.get("system", "")

        file_ext = Path(file_path).suffix.lower()
        guidance_map = {
            ".py": "- Use PEP 8, strict type hints, Google-style docstrings, and robust error handling.",
            ".js": "- Use modern ES6+, async/await for I/O, and descriptive naming.",
            ".ts": "- Define strict interfaces/types, avoid 'any', and use ES Modules.",
            ".html": "- Use semantic HTML5, ARIA labels, and clean structure.",
            ".css": "- Use modern CSS (Grid/Flexbox) and a logical ordering of properties.",
        }
        type_guidance = guidance_map.get(file_ext, "- Follow language-specific best practices and idioms.")

        user = file_gen.get("user", "").format(
            file_path=file_path,
            readme=readme[:1000],
            type_guidance=type_guidance
        )
        return system, user

    @staticmethod
    def architecture_planning(description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for project architecture planning."""
        content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/code_gen.yaml")
        arch = content.get("architecture", {})
        system = arch.get("system", "")
        user = arch.get("user", "").format(description=description)
        return system, user

    @staticmethod
    def file_content_generation_basic(file_path: str, parent_context: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for basic file content generation."""
        content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/code_gen.yaml")
        basic = content.get("basic", {})
        system = basic.get("system", "")
        user = basic.get("user", "").format(file_path=file_path, parent_context=parent_context)
        return system, user

    @staticmethod
    def file_refinement(file_path: str, content: str, context: str= "") -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file refinement."""
        prompt_content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/refinement.yaml")
        refine = prompt_content.get("refinement", {})
        system = refine.get("system", "")
        user = refine.get("user", "").format(file_path=file_path, context=context, content=content)
        return system, user

    @staticmethod
    def file_refinement_with_issues(file_path: str, content: str, issues: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file refinement with issues."""
        prompt_content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/refinement.yaml")
        with_issues = prompt_content.get("with_issues", {})
        system = with_issues.get("system", "")
        user = with_issues.get("user", "").format(file_path=file_path, issues=issues, content=content)
        return system, user

    @staticmethod
    def file_fix(file_path: str, content: str, error: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file fixing."""
        prompt_content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/refinement.yaml")
        fix = prompt_content.get("fix", {})
        system = fix.get("system", "")
        user = fix.get("user", "").format(file_path=file_path, error=error, content=content)
        return system, user

    @staticmethod
    def generate_unit_tests(file_path: str, content: str, readme: str = "") -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for unit test generation."""
        prompt_content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/test_gen.yaml")
        unit = prompt_content.get("unit", {})
        system = unit.get("system", "")
        context_str = f"Project info:\n{readme}\n\n" if readme else ""
        user = unit.get("user", "").format(context=context_str, file_path=file_path, content=content)
        return system, user

    @staticmethod
    def suggest_improvements_prompt(project_summary: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for improvement suggestions."""
        prompt_content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/review.yaml")
        suggest = prompt_content.get("improvement_suggestions", {})
        system = suggest.get("system", "")
        user = suggest.get("user", "").format(project_summary=project_summary)
        return system, user

    @staticmethod
    def generate_improvement_plan_prompt(improvements: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for improvement plan generation."""
        prompt_content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/review.yaml")
        plan = prompt_content.get("improvement_plan", {})
        system = plan.get("system", "")
        user = plan.get("user", "").format(improvements=improvements)
        return system, user

    @staticmethod
    def senior_review_prompt(project_summary: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for senior review."""
        prompt_content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/review.yaml")
        review = prompt_content.get("senior_review", {})
        system = review.get("system", "")
        user = review.get("user", "").format(project_summary=project_summary)
        return system, user

    @staticmethod
    def project_review(project_summary: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for a final project review."""
        prompt_content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/review.yaml")
        review = prompt_content.get("final_project_review", {})
        system = review.get("system", "")
        user = review.get("user", "").format(project_summary=project_summary)
        return system, user
