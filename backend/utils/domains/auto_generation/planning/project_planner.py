from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.ollama_client import OllamaClient
from backend.utils.core.llm.llm_response_parser import LLMResponseParser

from backend.utils.domains.auto_generation.utilities.prompt_templates import AutoGenPrompts


class ProjectPlanner:
    """Phase 1: Generates a README.md from a project description."""

    DEFAULT_OPTIONS = {
        "num_ctx": 4096,
        "num_predict": 2048,
        "temperature": 0.4,
        "keep_alive": "0s",
    }

    DOC_OPTIONS = {
        "num_ctx": 4096,
        "num_predict": 1024,
        "temperature": 0.3,
        "keep_alive": "0s",
    }

    def __init__(self, llm_client: OllamaClient, logger: AgentLogger, options: dict = None):
        self.llm_client = llm_client
        self.logger = logger
        self.options = options or self.DEFAULT_OPTIONS.copy()

    async def generate_readme(
        self, project_name: str, project_description: str, features_and_stack: str = "", project_structure: str = ""
    ) -> str:
        """Generate a comprehensive README.md using specialized prompts."""
        system, user = await AutoGenPrompts.readme_generation(
            project_name=project_name,
            project_description=project_description,
            features_and_stack=features_and_stack,
            project_structure=project_structure,
        )
        response_data, usage = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.options,
        )
        raw_content = response_data["message"]["content"]
        content = LLMResponseParser.extract_code(raw_content, "README.md")
        self.logger.info(f"README generated: {len(content)} characters")
        return content

    # ------------------------------------------------------------------
    # E7: Dynamic documentation helpers
    # ------------------------------------------------------------------

    async def generate_changelog_entry(
        self,
        project_name: str,
        changes: List[str],
        version: str = "",
    ) -> str:
        """Generate a Keep-a-Changelog formatted entry for the current auto-cycle.

        Args:
            project_name: Name of the project.
            changes: List of human-readable change descriptions.
            version: Optional semantic version tag (e.g. "1.2.0"); uses date if empty.

        Returns:
            Markdown string for a single changelog entry block.
        """
        system, user = await AutoGenPrompts.changelog_entry_prompt(
            project_name=project_name,
            changes=changes,
            version=version,
        )
        response_data, _ = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.DOC_OPTIONS,
        )
        raw_content = response_data["message"]["content"]
        content = LLMResponseParser.extract_code(raw_content, "CHANGELOG.md")
        self.logger.info(f"Changelog entry generated: {len(content)} chars")
        return content

    async def generate_roadmap(
        self,
        project_name: str,
        improvement_gaps: Dict[str, Any],
        tech_stack_info: Optional[Any] = None,
    ) -> str:
        """Generate a ROADMAP.md based on current improvement gaps and tech stack.

        Args:
            project_name: Name of the project.
            improvement_gaps: Dict of identified gaps from ProjectAnalysisPhase.
            tech_stack_info: Optional TechStackInfo for technology-specific hints.

        Returns:
            Full ROADMAP.md content as a markdown string.
        """
        tech_hints: List[str] = []
        if tech_stack_info is not None and hasattr(tech_stack_info, "prompt_hints"):
            tech_hints = tech_stack_info.prompt_hints or []

        system, user = await AutoGenPrompts.roadmap_prompt(
            project_name=project_name,
            improvement_gaps=improvement_gaps,
            tech_hints=tech_hints,
        )
        response_data, _ = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.DOC_OPTIONS,
        )
        raw_content = response_data["message"]["content"]
        content = LLMResponseParser.extract_code(raw_content, "ROADMAP.md")
        self.logger.info(f"Roadmap generated: {len(content)} chars")
        return content

    async def update_readme_summary(
        self,
        existing_readme: str,
        cycle_summary: str,
    ) -> str:
        """Append or replace the '## Last Auto-Update' section in README.md.

        Args:
            existing_readme: Current README.md content.
            cycle_summary: Compact summary of what the current auto-cycle changed.

        Returns:
            Updated README.md content with refreshed auto-update section.
        """
        system, user = await AutoGenPrompts.readme_summary_update_prompt(
            existing_readme=existing_readme,
            cycle_summary=cycle_summary,
        )
        response_data, _ = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.DOC_OPTIONS,
        )
        raw_content = response_data["message"]["content"]
        content = LLMResponseParser.extract_code(raw_content, "README.md")
        self.logger.info("README Last Auto-Update section refreshed")
        return content
