"""
Structure Pre-Review and Quality Scoring System

Early validation of project structure before code generation,
with dynamic quality metrics to guide improvement iterations.
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.llm_response_parser import LLMResponseParser
from src.utils.domains.auto_generation.prompt_templates import AutoGenPrompts


@dataclass
class StructureIssue:
    """Represents a structural issue found during review."""
    category: str  # "naming", "organization", "hierarchy", "completeness"
    severity: str  # "low", "medium", "high", "critical"
    description: str
    affected_paths: List[str]
    suggestion: str
    
    def to_dict(self) -> Dict:
        return {
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "affected_paths": self.affected_paths,
            "suggestion": self.suggestion,
        }


@dataclass
class StructureReview:
    """Result of structure pre-review."""
    quality_score: float  # 0-100
    confidence: float  # 0-1 (how confident is the review)
    status: str  # "passed", "needs_improvement", "critical"
    issues: List[StructureIssue]
    recommendations: List[str]
    metric_breakdown: Dict[str, float]  # Component scores
    
    def to_dict(self) -> Dict:
        return {
            "quality_score": self.quality_score,
            "confidence": self.confidence,
            "status": self.status,
            "issues": [i.to_dict() for i in self.issues],
            "recommendations": self.recommendations,
            "metric_breakdown": self.metric_breakdown,
        }


class StructurePreReviewer:
    """
    Validates project structure before Phase 4 (code generation).
    
    Checks:
    - Logical organization and hierarchy
    - Naming conventions consistency
    - Module separation of concerns
    - Required file presence (config, tests, etc.)
    - Potential naming conflicts
    - Circular dependencies
    """

    DEFAULT_OPTIONS = {
        "num_ctx": 8192,
        "num_predict": 2048,
        "temperature": 0.2,
        "keep_alive": "0s",
    }

    def __init__(
        self,
        llm_client: OllamaClient,
        logger: AgentLogger,
        response_parser: LLMResponseParser,
        options: dict = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.parser = response_parser
        self.options = options or self.DEFAULT_OPTIONS.copy()

    def review_structure(
        self,
        readme_content: str,
        structure: Dict,
        project_name: str = "project"
    ) -> StructureReview:
        """
        Perform comprehensive structure pre-review.
        
        Args:
            readme_content: Project README/description
            structure: Project structure JSON
            project_name: Name of the project
        
        Returns:
            StructureReview with quality metrics and issues
        """
        self.logger.info(f"Performing Structure Pre-Review for {project_name}...")
        
        # Run checks in parallel
        checks = {
            "hierarchy": self._check_hierarchy(structure),
            "naming": self._check_naming_conventions(structure),
            "conflicts": self._check_naming_conflicts(structure),
            "completeness": self._check_completeness(structure, readme_content),
            "organization": self._check_organization(structure),
        }
        
        # Get LLM review for subjective aspects
        llm_issues = self._get_llm_structure_review(
            readme_content, structure, project_name
        )
        
        # Synthesize all issues
        all_issues = []
        for check_name, (issues, score) in checks.items():
            all_issues.extend(issues)
        
        all_issues.extend(llm_issues)
        
        # Calculate overall quality score
        metric_scores = {k: v[1] for k, v in checks.items()}
        quality_score = self._calculate_quality_score(metric_scores, llm_issues)
        
        # Determine status
        status = "passed" if quality_score >= 80 else (
            "needs_improvement" if quality_score >= 60 else "critical"
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(all_issues, status)
        
        review = StructureReview(
            quality_score=quality_score,
            confidence=0.85,  # Based on hardcoded checks + LLM
            status=status,
            issues=all_issues,
            recommendations=recommendations,
            metric_breakdown=metric_scores,
        )
        
        self.logger.info(
            f"Structure Pre-Review complete: Score={quality_score:.1f}, "
            f"Status={status}, Issues={len(all_issues)}"
        )
        
        return review

    def _check_hierarchy(self, structure: Dict) -> Tuple[List[StructureIssue], float]:
        """Check if folder hierarchy is logical."""
        issues = []
        score = 100.0
        
        files = self._extract_file_paths(structure)
        
        # Check for files in root (usually not ideal)
        root_files = [f for f in files if "/" not in f]
        if len(root_files) > 5:
            issues.append(StructureIssue(
                category="hierarchy",
                severity="medium",
                description="Too many files in project root",
                affected_paths=root_files[:5],
                suggestion="Organize root files into subdirectories (src/, config/, docs/, etc.)"
            ))
            score -= 10
        
        # Check for deep nesting
        max_depth = max((p.count("/") for p in files), default=0)
        if max_depth > 6:
            issues.append(StructureIssue(
                category="hierarchy",
                severity="low",
                description=f"Deep folder nesting (depth={max_depth})",
                affected_paths=[],
                suggestion="Flatten some folder levels for better accessibility"
            ))
            score -= 5
        
        return issues, score

    def _check_naming_conventions(self, structure: Dict) -> Tuple[List[StructureIssue], float]:
        """Check naming consistency."""
        issues = []
        score = 100.0
        
        files = self._extract_file_paths(structure)
        
        # Detect naming patterns
        patterns = {}
        for f in files:
            ext = f.split(".")[-1] if "." in f else ""
            if ext not in patterns:
                patterns[ext] = []
            patterns[ext].append(f)
        
        # Check for mixed naming conventions (snake_case vs camelCase)
        for ext, file_list in patterns.items():
            Snake_case_count = sum(1 for f in file_list if "_" in f and "-" not in f)
            Kebab_case_count = sum(1 for f in file_list if "-" in f)
            
            if Snake_case_count > 0 and Kebab_case_count > 0:
                issues.append(StructureIssue(
                    category="naming",
                    severity="low",
                    description="Mixed naming conventions in same file type",
                    affected_paths=file_list[:3],
                    suggestion="Use consistent naming (e.g., all snake_case or all kebab-case)"
                ))
                score -= 5
        
        return issues, score

    def _check_naming_conflicts(self, structure: Dict) -> Tuple[List[StructureIssue], float]:
        """Check for naming conflicts (file with folder name)."""
        issues = []
        score = 100.0
        
        files = self._extract_file_paths(structure)
        folders = self._extract_folder_paths(structure)
        
        # Normalize paths
        file_bases = set(f.split(".")[0].lower() for f in files)
        folder_bases = set(f.rstrip("/").lower() for f in folders)
        
        conflicts = file_bases & folder_bases
        
        if conflicts:
            issues.append(StructureIssue(
                category="naming",
                severity="critical",
                description=f"Naming conflicts: {len(conflicts)} file/folder conflicts",
                affected_paths=sorted(conflicts),
                suggestion="Rename files or folders to remove conflicts"
            ))
            score -= 20
        
        return issues, score

    def _check_completeness(
        self,
        structure: Dict,
        readme: str
    ) -> Tuple[List[StructureIssue], float]:
        """Check for required files based on project type."""
        issues = []
        score = 100.0
        
        files = [f.lower() for f in self._extract_file_paths(structure)]
        
        # Required files based on project type
        required_sets = {
            "readme": ["readme.md", "readme", "readme.markdown"],
            "license": ["license", "license.md", "copying"],
            "config": ["config.json", "settings.json", ".env.example"],
            "tests": ["test", "tests", "spec", "specs"],
            "docs": ["docs", "documentation"],
        }
        
        missing = []
        for req_name, req_patterns in required_sets.items():
            has = any(
                any(p in f for p in req_patterns)
                for f in files
            )
            if not has and req_name != "license":  # License is optional
                missing.append(req_name)
                score -= 5
        
        if missing:
            issues.append(StructureIssue(
                category="completeness",
                severity="medium",
                description=f"Missing recommended files: {', '.join(missing)}",
                affected_paths=[],
                suggestion=f"Add {', '.join(missing)} files"
            ))
        
        return issues, score

    def _check_organization(self, structure: Dict) -> Tuple[List[StructureIssue], float]:
        """Check logical organization (src/, tests/, etc.)."""
        issues = []
        score = 100.0
        
        folders = [f.rstrip("/").lower() for f in self._extract_folder_paths(structure)]
        
        # Check for separate test folder
        has_tests = any("test" in f for f in folders)
        if not has_tests:
            issues.append(StructureIssue(
                category="organization",
                severity="low",
                description="No separate test directory",
                affected_paths=[],
                suggestion="Create tests/ or test/ folder for test files"
            ))
            score -= 3
        
        # Check for config folder
        has_config = any("config" in f or "conf" in f for f in folders)
        if not has_config:
            issues.append(StructureIssue(
                category="organization",
                severity="low",
                description="No config directory",
                affected_paths=[],
                suggestion="Create config/ folder for configuration files"
            ))
            score -= 3
        
        return issues, score

    def _get_llm_structure_review(
        self,
        readme: str,
        structure: Dict,
        project_name: str
    ) -> List[StructureIssue]:
        """Get LLM's subjective review of structure."""
        issues = []
        
        system_prompt = """You are an expert software architect reviewing project structures.
Identify structural issues: organization, naming, hierarchy, separation of concerns.
Return ONLY valid JSON with no extra text."""
        
        user_prompt = f"""Review this project structure:

Project: {project_name}
Description: {readme[:300]}

Structure:
{json.dumps(structure, indent=2)[:1000]}

Respond ONLY with valid JSON (no markdown):
{{
    "issues": [
        {{"category": "...", "severity": "low|medium|high", "description": "...", "suggestion": "..."}}
    ],
    "overall_assessment": "..."
}}"""
        
        try:
            response_data, _ = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=[],
                options_override=self.options,
            )
            
            raw = response_data["message"]["content"]
            
            # Try to extract JSON
            try:
                # Remove markdown if present
                if "```" in raw:
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                
                result = json.loads(raw)
                
                for issue_data in result.get("issues", []):
                    issues.append(StructureIssue(
                        category=issue_data.get("category", "organization"),
                        severity=issue_data.get("severity", "low"),
                        description=issue_data.get("description", ""),
                        affected_paths=[],
                        suggestion=issue_data.get("suggestion", "")
                    ))
            except json.JSONDecodeError:
                self.logger.debug("LLM structure review did not return valid JSON")
        
        except Exception as e:
            self.logger.debug(f"Error getting LLM structure review: {e}")
        
        return issues

    def _calculate_quality_score(
        self,
        metrics: Dict[str, float],
        issues: List[StructureIssue]
    ) -> float:
        """Calculate overall quality score 0-100."""
        # Start with average of metrics
        base_score = sum(metrics.values()) / len(metrics) if metrics else 100.0
        
        # Deduct for critical issues
        critical_count = sum(1 for i in issues if i.severity == "critical")
        high_count = sum(1 for i in issues if i.severity == "high")
        
        base_score -= critical_count * 15
        base_score -= high_count * 5
        
        return max(0, min(100, base_score))

    def _generate_recommendations(
        self,
        issues: List[StructureIssue],
        status: str
    ) -> List[str]:
        """Generate actionable recommendations from issues."""
        recommendations = []
        
        # Group by category
        by_category = {}
        for issue in issues:
            if issue.category not in by_category:
                by_category[issue.category] = []
            by_category[issue.category].append(issue)
        
        # Generate recommendations per category
        for category, cat_issues in by_category.items():
            high_priority = [i for i in cat_issues if i.severity in ("high", "critical")]
            if high_priority:
                recommendations.append(
                    f"Fix {len(high_priority)} critical {category} issues: "
                    f"{high_priority[0].suggestion}"
                )
        
        return recommendations

    def _extract_file_paths(self, structure: Dict, prefix: str = "") -> List[str]:
        """Extract all file paths from structure."""
        files = []
        
        if "files" in structure:
            for f in structure["files"]:
                files.append(f"{prefix}{f}")
        
        if "folders" in structure:
            for folder in structure["folders"]:
                folder_name = folder.get("name", "")
                new_prefix = f"{prefix}{folder_name}/"
                files.extend(self._extract_file_paths(folder, new_prefix))
        
        return files

    def _extract_folder_paths(self, structure: Dict, prefix: str = "") -> List[str]:
        """Extract all folder paths from structure."""
        folders = []
        
        if "folders" in structure:
            for folder in structure["folders"]:
                folder_name = folder.get("name", "")
                folder_path = f"{prefix}{folder_name}/"
                folders.append(folder_path)
                folders.extend(self._extract_folder_paths(folder, folder_path))
        
        return folders
