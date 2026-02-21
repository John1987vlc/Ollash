"""
CI/CD Auto-Healing

Detects GitHub Actions failures and generates fix commits
for configuration or dependency errors.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.command_executor import CommandExecutor


@dataclass
class CIFailureAnalysis:
    """Analysis of a CI/CD pipeline failure."""

    workflow_name: str
    failure_step: str
    error_messages: List[str]
    root_cause: str
    category: str  # "dependency", "config", "test", "build", "lint", "deploy"
    suggested_fixes: List[str]
    affected_files: List[str] = field(default_factory=list)
    confidence: float = 0.7

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "failure_step": self.failure_step,
            "error_messages": self.error_messages,
            "root_cause": self.root_cause,
            "category": self.category,
            "suggested_fixes": self.suggested_fixes,
            "affected_files": self.affected_files,
            "confidence": self.confidence,
        }


# Common CI failure patterns
CI_FAILURE_PATTERNS = [
    {
        "pattern": r"ModuleNotFoundError:\s+No module named '(\w+)'",
        "category": "dependency",
        "fix_template": "Add '{match}' to requirements.txt",
    },
    {
        "pattern": r"Cannot find module '([^']+)'",
        "category": "dependency",
        "fix_template": "Add '{match}' to package.json dependencies",
    },
    {
        "pattern": r"Error:\s+Process completed with exit code (\d+)",
        "category": "build",
        "fix_template": "Check build configuration for exit code {match}",
    },
    {
        "pattern": r"(?:SyntaxError|IndentationError):\s+(.+)",
        "category": "build",
        "fix_template": "Fix syntax error: {match}",
    },
    {
        "pattern": r"(?:FAILED|ERRORS)\s+tests?/(\S+)",
        "category": "test",
        "fix_template": "Fix failing test: {match}",
    },
    {
        "pattern": r"uses:\s+actions/(\S+)@v(\d+).*deprecated",
        "category": "config",
        "fix_template": "Update GitHub Action 'actions/{match}' to latest version",
    },
    {
        "pattern": r"pip install.*(?:failed|error)",
        "category": "dependency",
        "fix_template": "Fix Python dependency installation",
    },
    {
        "pattern": r"npm (?:ERR!|error)\s+(.+)",
        "category": "dependency",
        "fix_template": "Fix npm error: {match}",
    },
    {
        "pattern": r"docker:.*(?:not found|error)",
        "category": "config",
        "fix_template": "Fix Docker configuration",
    },
    {
        "pattern": r"(?:ruff|flake8|eslint|pylint).*(?:error|failed)",
        "category": "lint",
        "fix_template": "Fix linting errors",
    },
]


class CICDHealer:
    """Analyzes CI/CD failures and generates automatic fixes.

    Supports:
    - Dependency resolution (missing packages)
    - Configuration fixes (action versions, paths)
    - Build error diagnosis
    - Test failure analysis
    """

    def __init__(
        self,
        logger: AgentLogger,
        command_executor: Optional[CommandExecutor] = None,
        llm_client: Any = None,
    ):
        self.logger = logger
        self.command_executor = command_executor
        self.llm_client = llm_client

    def analyze_failure(self, workflow_log: str, workflow_name: str = "") -> CIFailureAnalysis:
        """Analyze a CI/CD workflow failure log.

        Uses pattern matching to identify the root cause and suggest fixes.
        """
        error_messages = self._extract_errors(workflow_log)
        failure_step = self._identify_failure_step(workflow_log)
        category = "unknown"
        suggested_fixes = []
        affected_files = []

        # Match against known patterns
        for pattern_info in CI_FAILURE_PATTERNS:
            pattern = pattern_info["pattern"]
            match = re.search(pattern, workflow_log, re.IGNORECASE)
            if match:
                category = pattern_info["category"]
                fix = pattern_info["fix_template"].format(match=match.group(1) if match.groups() else "")
                suggested_fixes.append(fix)

        # Detect affected files
        file_patterns = re.findall(r"(?:File|file)\s+[\"']?([^\s\"']+\.\w+)", workflow_log)
        affected_files = list(set(file_patterns))

        # Determine root cause
        root_cause = self._determine_root_cause(category, error_messages, suggested_fixes)

        analysis = CIFailureAnalysis(
            workflow_name=workflow_name or "unknown",
            failure_step=failure_step,
            error_messages=error_messages[:10],  # Limit to 10
            root_cause=root_cause,
            category=category,
            suggested_fixes=suggested_fixes,
            affected_files=affected_files,
        )

        self.logger.info(
            f"CI failure analysis: {category} in step '{failure_step}', {len(suggested_fixes)} fix suggestions"
        )

        return analysis

    def _extract_errors(self, log: str) -> List[str]:
        """Extract error messages from log output."""
        errors = []
        for line in log.split("\n"):
            line_lower = line.lower()
            if any(kw in line_lower for kw in ["error:", "failed", "exception:", "fatal:"]):
                errors.append(line.strip())
        return errors

    def _identify_failure_step(self, log: str) -> str:
        """Identify which CI step failed."""
        # GitHub Actions format
        step_match = re.search(r"##\[error\].*?in step '([^']+)'", log)
        if step_match:
            return step_match.group(1)

        # Generic step markers
        step_match = re.search(r"(?:Step|Run)\s+(\d+/\d+\s*:?\s*\w+)", log)
        if step_match:
            return step_match.group(1)

        return "unknown"

    def _determine_root_cause(self, category: str, errors: List[str], fixes: List[str]) -> str:
        """Determine the root cause based on category and errors."""
        if category == "dependency":
            return "Missing or incompatible dependency"
        elif category == "config":
            return "CI/CD configuration error"
        elif category == "test":
            return "Test failure"
        elif category == "build":
            return "Build error"
        elif category == "lint":
            return "Code style / linting error"
        elif category == "deploy":
            return "Deployment error"
        elif errors:
            return errors[0][:200]
        return "Unknown failure"

    async def generate_fix(self, analysis: CIFailureAnalysis, project_files: Dict[str, str]) -> Dict[str, str]:
        """Generate file changes to fix the CI failure.

        Uses LLM to generate intelligent fixes based on the analysis.
        """
        fixes: Dict[str, str] = {}

        if not self.llm_client:
            self.logger.warning("No LLM client available for CI fix generation")
            return fixes

        prompt = f"""Fix the following CI/CD pipeline failure:

Category: {analysis.category}
Root cause: {analysis.root_cause}
Error messages:
{chr(10).join(analysis.error_messages[:5])}

Suggested fixes:
{chr(10).join(analysis.suggested_fixes)}

Affected files: {", ".join(analysis.affected_files)}

Generate the corrected file contents. For each file that needs changes,
provide the complete corrected content.

Respond with JSON: {{"file_path": "corrected content", ...}}"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm_client.chat(messages=messages)
            if response and "message" in response:
                content = response["message"].get("content", "")
                # Try to parse JSON from response
                import json

                # Extract JSON from markdown code blocks if present
                json_match = re.search(r"```(?:json)?\s*({.*?})\s*```", content, re.DOTALL)
                if json_match:
                    fixes = json.loads(json_match.group(1))
                else:
                    try:
                        fixes = json.loads(content)
                    except json.JSONDecodeError:
                        self.logger.warning("Could not parse LLM fix response as JSON")
        except Exception as e:
            self.logger.error(f"Failed to generate CI fix: {e}")

        return fixes
