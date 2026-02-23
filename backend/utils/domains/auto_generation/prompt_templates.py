"""
Refactored AutoGenPrompts to use centralized YAML prompts.
Maintains the same interface while loading text from /prompts/domains/auto_generation/*.yaml.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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
                    data = eval(active_prompt)  # Caution: only if we trust our DB storage format
                    if isinstance(data, dict):
                        return data.get("system", ""), data.get("user", "")
                except:
                    # If it's just a string, it might be the system prompt or combined
                    return active_prompt, ""

        # Fallback to YAML
        content = cls._loader.load_prompt(yaml_path)
        if section:
            content = content.get(section, {})

        return content.get("system", content.get("system_prompt", "")), content.get(
            "user", content.get("user_prompt", "")
        )

    @staticmethod
    def architecture_planning_detailed(
        category: str, files_list: str, project_description: str, already_planned_contracts: str = ""
    ) -> Tuple[str, str]:
        """Returns (system, user) for Phase 2.5 Planning."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "architecture_planning_detailed", "domains/auto_generation/planning.yaml", "architecture_planning_detailed"
        )
        user = user_template.format(
            category=category,
            files_list=files_list,
            project_description=project_description,
            already_planned_contracts=already_planned_contracts or "(This is the first category — no prior contracts)",
        )
        return system, user

    @staticmethod
    def agile_backlog_planning(
        project_description: str, initial_structure: str, readme_content: str
    ) -> Tuple[str, str]:
        """Returns (system, user) for Agile Backlog generation."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "agile_backlog_planning", "domains/auto_generation/planning.yaml", "agile_backlog_planning"
        )
        user = user_template.format(
            project_description=project_description, initial_structure=initial_structure, readme_content=readme_content
        )
        return system, user

    @staticmethod
    def micro_task_execution(
        title: str,
        description: str,
        file_path: str,
        task_type: str,
        readme_content: str,
        context_files_content: str,
        logic_plan_section: str = "",
    ) -> Tuple[str, str]:
        """Returns (system, user) for a single micro-task execution."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "micro_task_execution", "domains/auto_generation/code_gen.yaml", "micro_task_execution"
        )
        user = user_template.format(
            title=title,
            description=description,
            file_path=file_path,
            task_type=task_type,
            readme_content=readme_content,
            context_files_content=context_files_content,
            logic_plan_section=logic_plan_section,
        )
        return system, user

    @staticmethod
    def project_analysis_gaps(
        total_files: int,
        total_loc: int,
        languages: str,
        has_tests: bool,
        test_files_count: int,
        project_description: str,
        readme_content: str,
        prompt_hints: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """Returns (system, user) for Phase 0.5 Analysis.

        Args:
            prompt_hints: Optional technology-specific hints from TechStackDetector
                          (e.g. ["Flask 2.3 - use Blueprints", "pytest - use fixtures"]).
                          When provided they are appended to the user prompt so the LLM
                          can tailor its gap analysis to the detected stack.
        """
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "project_analysis_gaps", "domains/auto_generation/analysis.yaml", "project_analysis_gaps"
        )
        user = user_template.format(
            total_files=total_files,
            total_loc=total_loc,
            languages=languages,
            has_tests=has_tests,
            test_files_count=test_files_count,
            project_description=project_description,
            readme_content=readme_content[:1000],
        )
        if prompt_hints:
            tech_context = "\n\nTechnology context: " + "; ".join(prompt_hints)
            user = user + tech_context
        return system, user

    @staticmethod
    def readme_generation(
        project_name: str, project_description: str, features_and_stack: str = "", project_structure: str = ""
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for specialized README generation."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "readme_generation", "domains/auto_generation/docs.yaml", "readme_generation"
        )
        user = user_template.format(
            project_name=project_name,
            project_description=project_description,
            features_and_stack=features_and_stack or "(No specific stack provided)",
            project_structure=project_structure or "(Structure not provided)",
        )
        return system, user

    @staticmethod
    def documentation_refinement(file_path: str, content: str, project_description: str = "") -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for specialized documentation refinement."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "documentation_refinement", "domains/auto_generation/docs.yaml", "documentation_refinement"
        )
        user = user_template.format(
            file_path=file_path, content=content, project_description=project_description or "(No additional context)"
        )
        return system, user

    @staticmethod
    def high_level_structure_generation(description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for high-level project structure."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "high_level", "domains/auto_generation/structure.yaml", "high_level"
        )
        user = user_template.format(description=description)
        return system, user

    @staticmethod
    def high_level_structure_generation_simplified(description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for simplified high-level structure."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "high_level_simplified", "domains/auto_generation/structure.yaml", "high_level_simplified"
        )
        if not user_template:  # Fallback
            return AutoGenPrompts.high_level_structure_generation(description)
        user = user_template.format(description=description)
        return system, user

    @staticmethod
    def sub_structure_generation(
        folder_path: str, readme_content: str, overall_structure: str, template_name: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for sub-structure generation."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "sub_structure", "domains/auto_generation/structure.yaml", "sub_structure"
        )
        user = user_template.format(
            folder_path=folder_path,
            readme_content=readme_content[:800],
            overall_structure=overall_structure,
            template_name=template_name,
        )
        return system, user

    @staticmethod
    def sub_structure_generation_simplified(
        folder_path: str, readme_content: str, overall_structure: str, template_name: str
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for simplified sub-structure generation."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "sub_structure_simplified", "domains/auto_generation/structure.yaml", "sub_structure_simplified"
        )
        if not user_template:  # Fallback
            return AutoGenPrompts.sub_structure_generation(
                folder_path, readme_content, overall_structure, template_name
            )

        user = user_template.format(
            folder_path=folder_path,
            readme_content=readme_content[:400],
            overall_structure=overall_structure,
            template_name=template_name,
        )
        return system, user

    @staticmethod
    def file_content_generation(file_path: str, content: str, readme: str = "") -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file content generation."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "file_content", "domains/auto_generation/code_gen.yaml", "file_content"
        )

        file_ext = Path(file_path).suffix.lower()
        guidance_map = {
            ".py": "- Use PEP 8, strict type hints, Google-style docstrings, and robust error handling.",
            ".js": "- Use modern ES6+, async/await for I/O, and descriptive naming.",
            ".ts": "- Define strict interfaces/types, avoid 'any', and use ES Modules.",
            ".html": "- Use semantic HTML5, ARIA labels, and clean structure.",
            ".css": "- Use modern CSS (Grid/Flexbox) and a logical ordering of properties.",
        }
        type_guidance = guidance_map.get(file_ext, "- Follow language-specific best practices and idioms.")

        user = user_template.format(file_path=file_path, readme=readme[:1000], type_guidance=type_guidance)
        return system, user

    @staticmethod
    def architecture_planning(description: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for project architecture planning."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "architecture", "domains/auto_generation/code_gen.yaml", "architecture"
        )
        user = user_template.format(description=description)
        return system, user

    @staticmethod
    def file_content_generation_basic(file_path: str, parent_context: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for basic file content generation."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "basic", "domains/auto_generation/code_gen.yaml", "basic"
        )
        user = user_template.format(file_path=file_path, parent_context=parent_context)
        return system, user

    @staticmethod
    def file_fix(file_path: str, content: str, error: str, readme: str = "") -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file fixing."""
        system, user_template = AutoGenPrompts._get_prompt_pair("fix", "domains/auto_generation/refinement.yaml", "fix")
        user = user_template.format(file_path=file_path, error=error, content=content, readme=readme[:1000])
        return system, user

    @staticmethod
    def generate_unit_tests(file_path: str, content: str, readme: str = "") -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for unit test generation."""
        system, user_template = AutoGenPrompts._get_prompt_pair("unit", "domains/auto_generation/test_gen.yaml", "unit")
        context_str = f"Project info:\n{readme}\n\n" if readme else ""
        user = user_template.format(context=context_str, file_path=file_path, content=content)
        return system, user

    @staticmethod
    def suggest_improvements_prompt(
        project_description: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
        loop_num: int,
        risk_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for improvement suggestions.

        Args:
            risk_context: Optional vulnerability scan results from VulnerabilityScanner.
                          When provided (and contains critical/high vulns) a priority
                          block is prepended so the LLM addresses security issues first.
                          Expected keys: critical_vulns, high_vulns, blocked_files,
                          top_vulnerabilities (list of {file, severity, count}).
        """
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "improvement_suggestions", "domains/auto_generation/review.yaml", "improvement_suggestions"
        )
        project_summary = (
            f"Description: {project_description}\nStructure: {json_structure}\nLoop iteration: {loop_num + 1}"
        )

        user = user_template.format(project_summary=project_summary)

        # Inject security priority block when critical/high vulnerabilities detected
        if risk_context and (risk_context.get("critical_vulns", 0) > 0 or risk_context.get("high_vulns", 0) > 0):
            vuln_lines = "\n".join(
                f"  - {v['file']} ({v['severity']}, {v['count']} issue(s))"
                for v in risk_context.get("top_vulnerabilities", [])
            )
            security_block = (
                f"\n\nSECURITY PRIORITY: The project has {risk_context['critical_vulns']} critical "
                f"and {risk_context['high_vulns']} high security vulnerabilities that MUST be "
                f"addressed before any other improvements:\n{vuln_lines}\n"
                f"List security fixes as your FIRST suggestions."
            )
            user = security_block + "\n\n" + user

        return system, user

    @staticmethod
    def generate_improvement_plan_prompt(
        suggestions: List[str],
        project_description: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for improvement plan generation."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "improvement_plan", "domains/auto_generation/review.yaml", "improvement_plan"
        )
        improvements = "\n".join([f"- {s}" for s in suggestions])
        user = user_template.format(improvements=improvements)
        return system, user

    @staticmethod
    def senior_review_prompt(project_summary: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for senior review."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "senior_review", "domains/auto_generation/review.yaml", "senior_review"
        )
        user = user_template.format(project_summary=project_summary)
        return system, user

    @staticmethod
    def project_review(project_summary: str) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for a final project review."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "final_project_review", "domains/auto_generation/review.yaml", "final_project_review"
        )
        user = user_template.format(project_summary=project_summary)
        return system, user
