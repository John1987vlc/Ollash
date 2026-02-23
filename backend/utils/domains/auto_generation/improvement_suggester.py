from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.llm.ollama_client import OllamaClient

from .prompt_templates import AutoGenPrompts


class ImprovementSuggester:
    """Suggests improvements based on project context.

    When a VulnerabilityScanner is provided, security vulnerabilities are
    scanned first and injected into the prompt as high-priority items so the
    LLM prioritises fixing them over cosmetic quality improvements.
    """

    DEFAULT_OPTIONS = {
        "num_ctx": 16384,
        "num_predict": 4096,
        "temperature": 0.5,
        "keep_alive": "0s",
    }

    def __init__(
        self,
        llm_client: OllamaClient,
        logger: AgentLogger,
        response_parser: LLMResponseParser,
        options: dict = None,
        vulnerability_scanner: Optional[Any] = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.parser = response_parser
        self.options = options or self.DEFAULT_OPTIONS.copy()
        self.vulnerability_scanner = vulnerability_scanner

    def _build_risk_context(self, current_files: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Run a vulnerability scan and return a risk context dict, or None."""
        if not self.vulnerability_scanner or not current_files:
            return None
        try:
            report = self.vulnerability_scanner.scan_project(
                current_files, block_on_critical=False
            )
            if report.total_vulnerabilities == 0:
                return None
            top_vulns = [
                {
                    "file": r.file_path,
                    "severity": r.max_severity if hasattr(r, "max_severity") else "unknown",
                    "count": len(r.vulnerabilities),
                }
                for r in report.file_results
                if r.vulnerabilities
            ][:5]
            return {
                "critical_vulns": report.critical_count,
                "high_vulns": report.high_count,
                "blocked_files": report.blocked_files,
                "top_vulnerabilities": top_vulns,
            }
        except Exception as exc:
            self.logger.warning(f"Vulnerability scan skipped during improvement suggestion: {exc}")
            return None

    def suggest_improvements(
        self,
        project_description: str,
        readme_content: str,
        json_structure: dict,
        current_files: Dict[str, str],
        loop_num: int,
    ) -> List[str]:
        """Suggests improvements for the project.

        When a vulnerability_scanner is configured, security issues are
        scanned first and surfaced to the LLM as priority items.

        Returns a list of suggested improvements (strings).
        """
        risk_context = self._build_risk_context(current_files)
        if risk_context and (risk_context["critical_vulns"] > 0 or risk_context["high_vulns"] > 0):
            self.logger.info(
                f"Risk-based suggestions: {risk_context['critical_vulns']} critical, "
                f"{risk_context['high_vulns']} high vulnerabilities detected"
            )

        system, user = AutoGenPrompts.suggest_improvements_prompt(
            project_description, readme_content, json_structure, current_files, loop_num,
            risk_context=risk_context,
        )
        response_data, _ = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.options,
        )
        raw_suggestions = response_data["message"]["content"]
        # Assuming the LLM returns a markdown list or similar
        suggestions = [line.strip("- ").strip() for line in raw_suggestions.split("\n") if line.strip().startswith("-")]
        return suggestions
