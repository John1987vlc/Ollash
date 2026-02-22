"""
Refactored AutoGenPrompts to use centralized YAML prompts.
Maintains the same interface while loading text from /prompts/domains/auto_generation/*.yaml.
"""

import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from backend.utils.core.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

class AutoGenPrompts:
    """Static methods for generating prompts for various auto-generation phases.
    Now integrated with PromptRepository for dynamic editing and versioning.
    """

    _loader = PromptLoader()
    _repository = None

    @classmethod
    def _get_repository(cls):
        """Lazy load PromptRepository from main container."""
        if cls._repository is None:
            try:
                from backend.core.containers import main_container
                # Try multiple ways to access the prompt_repository provider
                if hasattr(main_container, "core"):
                    core = main_container.core
                    if hasattr(core, "prompt_repository"):
                        cls._repository = core.prompt_repository()
                    else:
                        # If core is the provider itself and hasn't delegated attributes
                        cls._repository = core().prompt_repository()
                elif hasattr(main_container, "prompt_repository"):
                    cls._repository = main_container.prompt_repository()
            except Exception as e:
                logger.warning(f"Could not initialize PromptRepository in AutoGenPrompts: {e}")
        return cls._repository

    @classmethod
    def _get_prompt_pair(cls, role: str, yaml_path: str, section: str = None) -> Tuple[str, str]:
        """Helper to get prompt from Repository (active version) or Fallback to YAML."""
        repo = cls._get_repository()
        if repo:
            active_prompt = repo.get_active_prompt(role)
            if active_prompt:
                # If stored as JSON in DB, parse it
                try:
                    data = eval(active_prompt) # Caution: only if we trust our DB storage format
                    if isinstance(data, dict):
                        return data.get("system", ""), data.get("user", "")
                except:
                    # If it's just a string, it might be the system prompt or combined
                    return active_prompt, ""

        # Fallback to YAML
        content = cls._loader.load_prompt(yaml_path)
        if section:
            content = content.get(section, {})
        
        return content.get("system", content.get("system_prompt", "")), \
               content.get("user", content.get("user_prompt", ""))

    @staticmethod
    def architecture_planning_detailed(category: str, files_list: str, project_description: str) -> Tuple[str, str]:
        """Returns (system, user) for Phase 2.5 Planning."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "architecture_planning_detailed", 
            "domains/auto_generation/planning.yaml",
            "architecture_planning_detailed"
        )
        user = user_template.format(
            category=category,
            files_list=files_list,
            project_description=project_description
        )
        return system, user

    @staticmethod
    def agile_backlog_planning(project_description: str, initial_structure: str, readme_content: str) -> Tuple[str, str]:
        """Returns (system, user) for Agile Backlog generation."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "agile_backlog_planning", 
            "domains/auto_generation/planning.yaml",
            "agile_backlog_planning"
        )
        user = user_template.format(
            project_description=project_description,
            initial_structure=initial_structure,
            readme_content=readme_content
        )
        return system, user

    @staticmethod
    def micro_task_execution(
        title: str, description: str, file_path: str, task_type: str, readme_content: str, context_files_content: str
    ) -> Tuple[str, str]:
        """Returns (system, user) for a single micro-task execution."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "micro_task_execution", 
            "domains/auto_generation/code_gen.yaml",
            "micro_task_execution"
        )
        user = user_template.format(
            title=title,
            description=description,
            file_path=file_path,
            task_type=task_type,
            readme_content=readme_content,
            context_files_content=context_files_content
        )
        return system, user

    @staticmethod
    def project_analysis_gaps(total_files: int, total_loc: int, languages: str, has_tests: bool, test_files_count: int, project_description: str, readme_content: str) -> Tuple[str, str]:
        """Returns (system, user) for Phase 0.5 Analysis."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "project_analysis_gaps",
            "domains/auto_generation/analysis.yaml",
            "project_analysis_gaps"
        )
        user = user_template.format(
            total_files=total_files,
            total_loc=total_loc,
            languages=languages,
            has_tests=has_tests,
            test_files_count=test_files_count,
            project_description=project_description,
            readme_content=readme_content[:1000]
        )
        return system, user

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
    def high_level_structure_generation_simplified(description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for simplified high-level structure."""
        content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/structure.yaml")
        high_level = content.get("high_level_simplified", content.get("high_level", {}))
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
    def sub_structure_generation_simplified(
        folder_path: str, readme_content: str, overall_structure: str, template_name: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for simplified sub-structure generation."""
        content = AutoGenPrompts._loader.load_prompt("domains/auto_generation/structure.yaml")
        sub_structure = content.get("sub_structure_simplified", content.get("sub_structure", {}))
        system = sub_structure.get("system", "")

        user = sub_structure.get("user", "").format(
            folder_path=folder_path,
            readme_content=readme_content[:400], # Less context for simplified
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
