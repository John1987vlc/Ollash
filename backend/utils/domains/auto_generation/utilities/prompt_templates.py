"""
Refactored AutoGenPrompts to use centralized YAML prompts.
Maintains the same interface while loading text from /prompts/domains/auto_generation/*.yaml.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from backend.utils.core.llm.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


# Opt 1: Allowed actions per task type for Prompt-as-a-State-Machine
TASK_TYPE_ALLOWED_ACTIONS: Dict[str, List[str]] = {
    "define_imports": ["EMIT_IMPORTS", "REPORT_MISSING_DEP", "REQUEST_CLARIFICATION"],
    "implement_function": ["EMIT_CODE", "EMIT_CODE_WITH_TODO", "REPORT_AMBIGUITY"],
    "write_tests": ["EMIT_TEST_CODE", "SKIP_UNTESTABLE", "REQUEST_CLARIFICATION"],
    "write_config": ["EMIT_CONFIG", "USE_DEFAULTS", "REPORT_MISSING_ENV"],
}


class AutoGenPrompts:
    """Static methods for generating prompts for various auto-generation phases.
    Now integrated with PromptRepository for dynamic editing and versioning.
    """

    # Lazy-initialised on first use — keeps import time near-zero.
    _loader: "Optional[PromptLoader]" = None
    _repository = None

    @classmethod
    def _get_loader(cls) -> "PromptLoader":
        """Return the PromptLoader singleton, creating it on first call."""
        if cls._loader is None:
            from backend.utils.core.llm.prompt_loader import PromptLoader  # noqa: PLC0415

            cls._loader = PromptLoader()
        return cls._loader

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
            try:
                # get_active_prompt may be async in some implementations
                active_prompt = repo.get_active_prompt(role)
                import inspect

                if inspect.isawaitable(active_prompt):
                    active_prompt.close()
                    active_prompt = None
                if active_prompt:
                    # If stored as JSON in DB, parse it
                    try:
                        # Safer parsing if it looks like JSON
                        if active_prompt.strip().startswith("{"):
                            import json

                            data = json.loads(active_prompt)
                            if isinstance(data, dict):
                                return data.get("system", ""), data.get("user", "")
                    except:
                        # If it's just a string, it might be the system prompt
                        return active_prompt, ""
            except Exception as e:
                logger.debug(f"Failed to load prompt from repo for {role}: {e}")

        # Fallback to YAML
        content = cls._get_loader().load_prompt_sync(yaml_path)
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
    def logic_planning(
        project_description: str, initial_structure: str, planning_files: str, module_system_hint: str = ""
    ) -> Tuple[str, str]:
        """Returns (system, user) for Unified Logic Planning (Phase 2.5)."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "logic_planning", "domains/auto_generation/planning.yaml", "logic_planning"
        )
        user = user_template.format(
            project_description=project_description,
            initial_structure=initial_structure,
            planning_files=planning_files,
            module_system_hint=module_system_hint,
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
        allowed_actions: Optional[str] = None,
        anti_pattern_warnings: str = "",
        few_shot_section: str = "",
    ) -> Tuple[str, str]:
        """Returns (system, user) for a single micro-task execution.

        Args:
            allowed_actions: If provided (Opt 1), appended as a constrained
                action list so the model must choose from a closed set.
            anti_pattern_warnings: If non-empty (Opt 5), prepended with an
                ``EVITAR_ESTOS_ERRORES:`` header and injected into the prompt.
            few_shot_section: If non-empty (Feature 2), injects validated
                examples from previous successful generations.
        """
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "micro_task_execution", "domains/auto_generation/code_gen.yaml", "micro_task_execution"
        )
        # Opt 1: build allowed-actions block
        actions_block = ""
        if allowed_actions:
            actions_block = f"\n\n## ALLOWED ACTIONS (choose exactly one):\n{allowed_actions}"
        # Opt 5: build anti-pattern block
        anti_block = f"\n\nEVITAR_ESTOS_ERRORES:\n{anti_pattern_warnings}" if anti_pattern_warnings else ""
        # Feature 2: few-shot examples block
        few_shot_block = f"\n\n{few_shot_section}" if few_shot_section else ""
        user = user_template.format(
            title=title,
            description=description,
            file_path=file_path,
            task_type=task_type,
            readme_content=readme_content,
            context_files_content=context_files_content,
            logic_plan_section=logic_plan_section,
            allowed_actions=actions_block,
            anti_pattern_warnings=anti_block,
            few_shot_section=few_shot_block,
        )
        return system, user

    @staticmethod
    def next_backlog_task(
        project_description: str,
        initial_structure: str,
        backlog_so_far: List[Dict[str, Any]],
    ) -> Tuple[str, str]:
        """Returns (system, user) for incremental backlog generation (Opt 4).

        Each call asks the LLM for exactly ONE next micro-task given the tasks
        generated so far, or ``{"complete": true}`` when no more tasks are needed.
        """
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "next_backlog_task", "domains/auto_generation/planning.yaml", "next_backlog_task"
        )
        import json as _json

        backlog_json = _json.dumps(backlog_so_far, ensure_ascii=False, indent=2)
        user = user_template.format(
            project_description=project_description,
            initial_structure=initial_structure,
            task_count=len(backlog_so_far),
            backlog_so_far=backlog_json,
        )
        return system, user

    @staticmethod
    def nano_format_corrector(
        language: str,
        format_error: str,
        code: str,
    ) -> Tuple[str, str]:
        """Returns (system, user) for format-only correction by nano_reviewer (Opt 6).

        The model must fix ONLY the structural/format error and return the
        corrected code inside ``<code_fixed>`` tags.
        """
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "nano_format_corrector", "domains/auto_generation/nano_roles.yaml", "nano_format_corrector"
        )
        user = user_template.format(
            language=language,
            format_error=format_error,
            code=code,
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
        folder_path: str,
        readme_content: str,
        overall_structure: str,
        template_name: str,
        constraint_hint: str = "",
    ) -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for sub-structure generation.

        Args:
            folder_path: Path of the folder being expanded.
            readme_content: Project README used as LLM context.
            overall_structure: Current full structure JSON string.
            template_name: Template identifier.
            constraint_hint: Optional extension constraint injected at end of prompt
                (e.g. "ONLY create files with: .html .css .js — DO NOT create .py").
        """
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "sub_structure", "domains/auto_generation/structure.yaml", "sub_structure"
        )
        user = user_template.format(
            folder_path=folder_path,
            readme_content=readme_content[:800],
            overall_structure=overall_structure,
            template_name=template_name,
        )
        if constraint_hint:
            user += f"\n\n## EXTENSION CONSTRAINT (CRITICAL — DO NOT VIOLATE)\n{constraint_hint}"
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
    def file_refinement(file_path: str, content: str, context: str = "") -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for general file refinement."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "refine", "domains/auto_generation/refinement.yaml", "refine"
        )
        user = user_template.format(file_path=file_path, content=content, context=context)
        return system, user

    @staticmethod
    def file_refinement_with_issues(file_path: str, content: str, issues: str, context: str = "") -> Tuple[str, str]:
        """Returns (system_prompt, user_prompt) for file refinement based on specific issues."""
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "refine_with_issues", "domains/auto_generation/refinement.yaml", "refine_with_issues"
        )
        user = user_template.format(file_path=file_path, content=content, issues=issues, context=context)
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

    # ------------------------------------------------------------------
    # E7: Dynamic documentation prompts
    # ------------------------------------------------------------------

    @staticmethod
    def changelog_entry_prompt(
        project_name: str,
        changes: List[str],
        version: str = "",
    ) -> Tuple[str, str]:
        """Returns (system, user) for generating a Keep-a-Changelog entry.

        Args:
            project_name: Name of the project.
            changes: List of change descriptions from the current cycle.
            version: Optional semantic version; uses today's date if empty.
        """
        from datetime import date

        version_tag = version if version else f"[Auto-{date.today().isoformat()}]"
        changes_md = "\n".join(f"- {c}" for c in changes)

        system = (
            "You are a technical writer that produces concise Keep-a-Changelog formatted entries. "
            "Output ONLY the changelog block starting with '## [version] - date' and ending before "
            "the next '## ' heading. Use sections ### Added, ### Changed, ### Fixed as appropriate. "
            "Be concise — no more than 20 bullet points total."
        )
        user = (
            f"Project: {project_name}\n"
            f"Version: {version_tag}\n\n"
            f"Changes applied in this automation cycle:\n{changes_md}\n\n"
            "Generate the Keep-a-Changelog entry block now."
        )
        return system, user

    @staticmethod
    def roadmap_prompt(
        project_name: str,
        improvement_gaps: Dict[str, Any],
        tech_hints: Optional[List[str]] = None,
    ) -> Tuple[str, str]:
        """Returns (system, user) for generating a ROADMAP.md.

        Args:
            project_name: Name of the project.
            improvement_gaps: Dict of gap categories → list of gap descriptions.
            tech_hints: Optional tech-stack prompt hints from TechStackDetector.
        """
        gaps_md = ""
        for category, items in improvement_gaps.items():
            if isinstance(items, list):
                gaps_md += f"\n**{category}**\n" + "\n".join(f"- {i}" for i in items[:5])
            else:
                gaps_md += f"\n**{category}**: {items}"

        tech_section = ""
        if tech_hints:
            tech_section = "\nTechnology context: " + "; ".join(tech_hints[:3])

        system = (
            "You are a technical product manager. Generate a concise ROADMAP.md with three sections: "
            "'## Current Focus', '## Near-term (next 3 cycles)', '## Future'. "
            "Each section should have 3-7 bullet points. Be specific and actionable. "
            "Output ONLY the markdown content."
        )
        user = (
            f"Project: {project_name}{tech_section}\n\n"
            f"Identified improvement gaps:{gaps_md}\n\n"
            "Generate the ROADMAP.md content now."
        )
        return system, user

    @staticmethod
    def readme_summary_update_prompt(
        existing_readme: str,
        cycle_summary: str,
    ) -> Tuple[str, str]:
        """Returns (system, user) to update the '## Last Auto-Update' section in README.

        Args:
            existing_readme: Current README.md content.
            cycle_summary: Compact summary of what changed in the current auto-cycle.
        """
        system = (
            "You are a documentation assistant. You will receive a README.md and a cycle summary. "
            "Return the complete README with the '## Last Auto-Update' section at the very end "
            "replaced (or appended if absent) with the provided cycle summary. "
            "Do NOT modify any other section. Output ONLY the full README content."
        )
        user = (
            f"CYCLE SUMMARY:\n{cycle_summary}\n\n"
            f"EXISTING README:\n{existing_readme[:3000]}\n\n"
            "Return the updated README now."
        )
        return system, user

    # ------------------------------------------------------------------
    # Nano Roles — ultra-focused prompts for small models (≤4B)
    # ------------------------------------------------------------------

    @staticmethod
    def nano_planner(project_name: str, project_description: str) -> Tuple[str, str]:
        """Returns (system, user) for NanoPlanner: outputs only a JSON list of files to create.

        Designed for small models (≤4B) that need a single, minimal task to perform.
        """
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "nano_planner_prompt",
            "domains/auto_generation/nano_roles.yaml",
            "nano_planner_prompt",
        )
        user = user_template.format(
            project_name=project_name,
            project_description=project_description,
        )
        return system, user

    @staticmethod
    def nano_coder(
        function_name: str,
        signature: str,
        docstring: str,
        context_snippet: str = "",
    ) -> Tuple[str, str]:
        """Returns (system, user) for NanoCoder: writes the body of ONE specific function.

        Designed for small models (≤4B) so that the model focuses on a single function,
        reducing the risk of hallucinated structure or missing imports.

        Args:
            function_name: The name of the function to implement.
            signature: Full signature string (e.g. "def foo(x: int, y: str) -> bool:").
            docstring: Docstring describing what the function must do.
            context_snippet: Optional snippet of existing code in the same file for context.
        """
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "nano_coder_prompt",
            "domains/auto_generation/nano_roles.yaml",
            "nano_coder_prompt",
        )
        user = user_template.format(
            function_name=function_name,
            signature=signature,
            docstring=docstring,
            context_snippet=context_snippet or "(no context available)",
        )
        return system, user

    @staticmethod
    def nano_reviewer(language: str, code: str) -> Tuple[str, str]:
        """Returns (system, user) for NanoReviewer: checks indentation and syntax only.

        Designed for small models (≤4B). The reviewer's scope is intentionally minimal
        so the model can reliably detect basic structural errors without semantic analysis.

        Args:
            language: Programming language name (e.g. "Python", "JavaScript").
            code: Source code content to review.
        """
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "nano_reviewer_prompt",
            "domains/auto_generation/nano_roles.yaml",
            "nano_reviewer_prompt",
        )
        user = user_template.format(language=language, code=code)
        return system, user

    @staticmethod
    def nano_critic_review(language: str, code: str) -> Tuple[str, str]:
        """Returns (system, user) for the Critic-Correction Loop.

        Extends ``nano_reviewer`` with a missing-import check to enable
        closed-loop auto-correction after file generation (Feature 1).

        Args:
            language: Programming language name (e.g. ``"python"``).
            code: Generated source code to audit.
        """
        system, user_template = AutoGenPrompts._get_prompt_pair(
            "nano_critic_review",
            "domains/auto_generation/nano_roles.yaml",
            "nano_critic_review",
        )
        user = user_template.format(language=language, code=code)
        return system, user
