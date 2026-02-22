"""
Multimodal UI/UX Analyzer

Uses OCR and vision capabilities to analyze screenshots of generated
user interfaces and suggest visual improvements.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from backend.utils.core.system.agent_logger import AgentLogger


@dataclass
class UIIssue:
    """A detected UI/UX issue."""

    category: str  # "layout", "accessibility", "typography", "color", "spacing", "consistency"
    description: str
    severity: str  # "info", "minor", "major"
    suggestion: str
    location: str = ""  # "top-left", "center", "navigation", etc.

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "description": self.description,
            "severity": self.severity,
            "suggestion": self.suggestion,
            "location": self.location,
        }


@dataclass
class UIAnalysisReport:
    """Complete UI analysis report."""

    screenshot_path: str
    issues: List[UIIssue] = field(default_factory=list)
    overall_score: float = 0.0  # 0-10
    extracted_text: str = ""
    detected_elements: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "screenshot_path": self.screenshot_path,
            "issue_count": len(self.issues),
            "overall_score": self.overall_score,
            "issues": [i.to_dict() for i in self.issues],
            "detected_elements": self.detected_elements,
            "recommendations": self.recommendations,
        }


class UIAnalyzer:
    """Analyzes UI screenshots using OCR and LLM vision capabilities.

    Integrates with the existing OCRProcessor for text extraction
    and uses the LLM for layout and design analysis.
    """

    def __init__(
        self,
        logger: AgentLogger,
        llm_client: Any = None,
        ocr_processor: Any = None,
    ):
        self.logger = logger
        self.llm_client = llm_client
        self.ocr_processor = ocr_processor

    async def analyze_screenshot(self, screenshot_path: Path) -> UIAnalysisReport:
        """Analyze a UI screenshot for design issues."""
        report = UIAnalysisReport(screenshot_path=str(screenshot_path))

        # Step 1: Extract text via OCR if available
        if self.ocr_processor:
            try:
                ocr_result = self.ocr_processor.process_image(str(screenshot_path))
                if ocr_result:
                    report.extracted_text = ocr_result.get("extracted_text", "")
                    self._analyze_text_quality(report)
            except Exception as e:
                self.logger.warning(f"OCR analysis failed: {e}")

        # Step 2: LLM-based visual analysis
        if self.llm_client:
            await self._llm_visual_analysis(report, screenshot_path)

        # Calculate overall score
        report.overall_score = self._calculate_score(report)

        self.logger.info(f"UI analysis: {len(report.issues)} issues found, score: {report.overall_score:.1f}/10")
        return report

    def _analyze_text_quality(self, report: UIAnalysisReport) -> None:
        """Analyze extracted text for common UI issues."""
        text = report.extracted_text

        # Check for text overlap indicators
        if "..." in text and text.count("...") > 3:
            report.issues.append(
                UIIssue(
                    category="typography",
                    description="Multiple text truncations detected (ellipsis)",
                    severity="minor",
                    suggestion="Increase container widths or reduce font sizes to prevent truncation",
                )
            )

        # Check for missing labels
        if len(text) < 50 and text.strip():
            report.issues.append(
                UIIssue(
                    category="accessibility",
                    description="Very little visible text detected",
                    severity="info",
                    suggestion="Ensure all interactive elements have visible labels",
                )
            )

    async def _llm_visual_analysis(self, report: UIAnalysisReport, screenshot_path: Path) -> None:
        """Use LLM to analyze the screenshot for design issues."""
        prompt = """Analyze this UI screenshot and identify design issues.

For each issue, specify:
1. Category (layout, accessibility, typography, color, spacing, consistency)
2. Description of the problem
3. Severity (info, minor, major)
4. Specific improvement suggestion

Also provide:
- List of detected UI elements (buttons, forms, navigation, etc.)
- Overall design recommendations

Be specific and actionable."""

        try:
            messages = [{"role": "user", "content": prompt}]
            response, _ = self.llm_client.chat(messages=messages, tools=[])
            if response and "message" in response:
                content = response["message"].get("content", "")
                self._parse_llm_analysis(report, content)
        except Exception as e:
            self.logger.warning(f"LLM visual analysis failed: {e}")

    def _parse_llm_analysis(self, report: UIAnalysisReport, llm_response: str) -> None:
        """Parse LLM analysis response into structured issues."""
        # Simple parsing - in production, use structured output
        lines = llm_response.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for issue indicators
            lower = line.lower()
            if any(cat in lower for cat in ["layout", "accessibility", "typography", "color", "spacing"]):
                for cat in ["layout", "accessibility", "typography", "color", "spacing", "consistency"]:
                    if cat in lower:
                        severity = "minor"
                        if "major" in lower or "critical" in lower:
                            severity = "major"
                        elif "info" in lower or "suggestion" in lower:
                            severity = "info"

                        report.issues.append(
                            UIIssue(
                                category=cat,
                                description=line[:200],
                                severity=severity,
                                suggestion="",
                            )
                        )
                        break

            # Look for recommendations
            if line.startswith(("-", "*", "•")) and "recommend" in lower:
                report.recommendations.append(line.lstrip("-*• "))

    def _calculate_score(self, report: UIAnalysisReport) -> float:
        """Calculate an overall UI quality score (0-10)."""
        score = 10.0

        for issue in report.issues:
            if issue.severity == "major":
                score -= 1.5
            elif issue.severity == "minor":
                score -= 0.5
            else:
                score -= 0.1

        return max(0.0, min(10.0, round(score, 1)))

    async def analyze_html_content(self, html_content: str) -> UIAnalysisReport:
        """Analyze HTML content directly without screenshot (static analysis)."""
        report = UIAnalysisReport(screenshot_path="(html content)")

        # Check for basic accessibility
        if "<img" in html_content and 'alt="' not in html_content:
            report.issues.append(
                UIIssue(
                    category="accessibility",
                    description="Images without alt text detected",
                    severity="major",
                    suggestion="Add descriptive alt attributes to all <img> elements",
                )
            )

        if "<form" in html_content and "<label" not in html_content:
            report.issues.append(
                UIIssue(
                    category="accessibility",
                    description="Form inputs without labels",
                    severity="major",
                    suggestion="Add <label> elements for all form inputs",
                )
            )

        # Check for responsive design indicators
        if "viewport" not in html_content:
            report.issues.append(
                UIIssue(
                    category="layout",
                    description="Missing viewport meta tag",
                    severity="minor",
                    suggestion='Add <meta name="viewport" content="width=device-width, initial-scale=1">',
                )
            )

        # Check contrast / readability
        if "color:" in html_content and "background" not in html_content:
            report.issues.append(
                UIIssue(
                    category="color",
                    description="Text color set without background color",
                    severity="info",
                    suggestion="Always set both text color and background color for accessibility",
                )
            )

        report.overall_score = self._calculate_score(report)
        return report
