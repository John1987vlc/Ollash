"""Project Analysis Phase - Analyzes existing code and plans improvements."""

from typing import Dict, Any, List, Tuple
from pathlib import Path
import json
import re

from backend.interfaces.iagent_phase import IAgentPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


class ProjectAnalysisPhase(IAgentPhase):
    """
    Phase 0.5 (executed when project exists):
    Analyzes existing project code and compares it with the project_description
    to identify gaps and generate improvement plans.

    This phase:
    1. Reads the existing codebase
    2. Identifies current structure and patterns
    3. Compares with project_description requirements
    4. Generates logic_plan for enhancements/refactoring
    5. Prioritizes improvements by impact and effort
    """

    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str,
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str],
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        """
        Analyzes the existing project and generates improvement plan.
        """
        file_paths = kwargs.get("file_paths", [])

        self.context.logger.info(
            f"[PROJECT_NAME:{project_name}] PHASE 0.5: Analyzing existing project "
            f"({len(generated_files)} files, {len(file_paths)} paths)..."
        )
        self.context.event_publisher.publish(
            "phase_start",
            phase="0.5",
            message="Analyzing existing project code"
        )

        # Step 1: Analyze current codebase
        codebase_analysis = await self._analyze_codebase(generated_files, file_paths)

        # Step 2: Compare with project description
        gaps = await self._identify_gaps(project_description, codebase_analysis, readme_content)

        # Step 3: Generate improvement plan
        logic_plan = await self._generate_improvement_plan(
            gaps, codebase_analysis, project_description, generated_files
        )

        # Step 4: Save analysis reports
        analysis_report = {
            "timestamp": str(Path(__file__).stat().st_mtime),
            "files_analyzed": len(generated_files),
            "codebase_analysis": codebase_analysis,
            "identified_gaps": gaps,
            "improvement_plan": logic_plan,
        }

        analysis_file = project_root / "ANALYSIS_REPORT.json"
        self.context.file_manager.write_file(analysis_file, json.dumps(analysis_report, indent=2))
        generated_files["ANALYSIS_REPORT.json"] = json.dumps(analysis_report, indent=2)

        # Store in context for use by subsequent phases
        self.context.logic_plan = logic_plan
        self.context.codebase_analysis = codebase_analysis
        self.context.improvement_gaps = gaps

        improvement_count = len(gaps.get("improvements", []))
        refactor_count = len(gaps.get("refactoring_opportunities", []))

        self.context.event_publisher.publish(
            "phase_complete",
            phase="0.5",
            message=f"Analysis complete: {improvement_count} improvements, {refactor_count} refactoring opportunities"
        )
        self.context.logger.info(
            f"[PROJECT_NAME:{project_name}] PHASE 0.5 complete: "
            f"{improvement_count} improvements identified, {refactor_count} refactoring opportunities"
        )

        return generated_files, initial_structure, file_paths

    async def _analyze_codebase(self, generated_files: Dict[str, str],
                               file_paths: List[str]) -> Dict[str, Any]:
        """
        Analyzes the existing codebase to understand structure and patterns.

        Returns:
            Dictionary with analysis results including:
            - files_by_type: Files grouped by language/type
            - total_lines_of_code: Total lines across all files
            - code_patterns: Identified patterns and conventions
            - dependencies: Detected dependencies and imports
            - test_coverage: Information about test files
        """
        self.context.logger.info("  Analyzing codebase structure...")

        analysis = {
            "files_by_type": {},
            "total_lines_of_code": 0,
            "code_patterns": [],
            "dependencies": [],
            "test_coverage": {
                "has_tests": False,
                "test_files": [],
                "source_files": []
            },
            "file_details": []
        }

        # Group files by language
        files_by_language = self.context.group_files_by_language(generated_files)
        analysis["files_by_type"] = {
            lang: len(files) for lang, files in files_by_language.items()
        }

        # Analyze each file
        test_files = []
        source_files = []

        for file_path, content in generated_files.items():
            lines = len(content.splitlines())
            analysis["total_lines_of_code"] += lines

            file_info = {
                "path": file_path,
                "lines": lines,
                "language": self.context.infer_language(file_path),
                "is_test": "test" in file_path.lower(),
            }
            analysis["file_details"].append(file_info)

            if file_info["is_test"]:
                test_files.append(file_path)
            else:
                source_files.append(file_path)

            # Detect imports/dependencies
            imports = self._detect_imports(file_path, content)
            analysis["dependencies"].extend(imports)

            # Detect code patterns
            patterns = self._detect_patterns(file_path, content)
            analysis["code_patterns"].extend(patterns)

        analysis["test_coverage"]["has_tests"] = len(test_files) > 0
        analysis["test_coverage"]["test_files"] = test_files
        analysis["test_coverage"]["source_files"] = source_files

        return analysis

    async def _identify_gaps(self, project_description: str,
                            codebase_analysis: Dict[str, Any],
                            readme_content: str) -> Dict[str, Any]:
        """
        Compares the existing codebase with the project description
        to identify gaps and missing features.

        Returns:
            Dictionary with identified gaps, missing features, and improvement opportunities
        """
        self.context.logger.info("  Identifying gaps between current state and requirements...")

        # Prepare context for LLM
        analysis_context = f"""
## Current Project State
- Total files: {len(codebase_analysis['file_details'])}
- Total lines of code: {codebase_analysis['total_lines_of_code']}
- Languages used: {', '.join(codebase_analysis['files_by_type'].keys())}
- Has tests: {codebase_analysis['test_coverage']['has_tests']}
- Test files: {len(codebase_analysis['test_coverage']['test_files'])}

## Required Project Description
{project_description}

## Current README
{readme_content[:1000] if readme_content else 'No README found'}

## Analysis Task
1. Compare the current codebase with the requirements in the project description
2. Identify missing features, modules, or functionality
3. Identify code quality improvements needed
4. Identify refactoring opportunities
5. Identify test coverage gaps
6. Prioritize improvements by impact and effort

Respond with a JSON structure containing:
{{
    "completeness_score": <0-100>,
    "improvements": [
        {{"category": "feature|quality|refactor|testing", "title": "", "description": "", "effort": "low|medium|high", "impact": "low|medium|high"}}
    ],
    "refactoring_opportunities": [
        {{"file": "", "current_pattern": "", "suggested_pattern": "", "reason": ""}}
    ],
    "missing_features": ["feature1", "feature2", ...],
    "test_gaps": ["gap1", "gap2", ...],
    "summary": ""
}}
"""

        system_prompt = (
            "You are an expert code reviewer and architect. Analyze the given codebase "
            "against the project requirements and identify gaps, improvements, and refactoring opportunities. "
            "Provide actionable, prioritized recommendations."
        )

        try:
            response_data, _ = self.context.llm_manager.get_client("generalist").chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": analysis_context},
                ],
                options_override={"temperature": 0.3},
            )

            response_text = response_data.get("content", "")

            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                gaps = json.loads(json_match.group())
            else:
                # Fallback structure if JSON extraction fails
                gaps = {
                    "completeness_score": 50,
                    "improvements": [],
                    "refactoring_opportunities": [],
                    "missing_features": [],
                    "test_gaps": [],
                    "summary": response_text
                }

            return gaps

        except Exception as e:
            self.context.logger.error(f"Error identifying gaps: {e}")
            return {
                "completeness_score": 50,
                "improvements": [],
                "refactoring_opportunities": [],
                "missing_features": [],
                "test_gaps": [],
                "summary": f"Error during analysis: {str(e)}"
            }

    async def _generate_improvement_plan(self, gaps: Dict[str, Any],
                                        codebase_analysis: Dict[str, Any],
                                        project_description: str,
                                        generated_files: Dict[str, str]) -> Dict[str, Any]:
        """
        Generates a detailed improvement plan based on identified gaps.

        Returns:
            Dictionary with logic_plan for improvements
        """
        self.context.logger.info("  Generating improvement plan...")

        improvements = gaps.get("improvements", [])

        # Group improvements by priority and effort
        improvement_plan = {
            "high_impact_quick_wins": [],
            "medium_impact_improvements": [],
            "refactoring_needed": [],
            "testing_improvements": [],
            "future_enhancements": [],
        }

        for improvement in improvements:
            category = improvement.get("category", "quality")
            impact = improvement.get("impact", "medium")
            effort = improvement.get("effort", "medium")

            # Classify improvement
            if impact == "high" and effort in ["low", "medium"]:
                improvement_plan["high_impact_quick_wins"].append(improvement)
            elif category == "refactor":
                improvement_plan["refactoring_needed"].append(improvement)
            elif category == "testing":
                improvement_plan["testing_improvements"].append(improvement)
            elif impact == "medium":
                improvement_plan["medium_impact_improvements"].append(improvement)
            else:
                improvement_plan["future_enhancements"].append(improvement)

        # Add file-specific improvement plans
        improvement_plan["file_improvements"] = {}
        for refactor_opp in gaps.get("refactoring_opportunities", []):
            file_path = refactor_opp.get("file", "")
            if file_path and file_path in generated_files:
                if file_path not in improvement_plan["file_improvements"]:
                    improvement_plan["file_improvements"][file_path] = {
                        "current_pattern": refactor_opp.get("current_pattern", ""),
                        "suggested_pattern": refactor_opp.get("suggested_pattern", ""),
                        "reason": refactor_opp.get("reason", ""),
                    }

        return improvement_plan

    def _detect_imports(self, file_path: str, content: str) -> List[str]:
        """Detects imports and dependencies from file content."""
        imports = []

        # Python imports
        if file_path.endswith(".py"):
            import_patterns = [
                r'^import\s+(\S+)',
                r'^from\s+(\S+)\s+import',
            ]
            for pattern in import_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.extend(matches)

        # JavaScript/TypeScript imports
        elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
            import_patterns = [
                r"^import\s+.*?from\s+['\"]([^'\"]+)['\"]",
                r"^require\(['\"]([^'\"]+)['\"]\)",
            ]
            for pattern in import_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.extend(matches)

        return list(set(imports))

    def _detect_patterns(self, file_path: str, content: str) -> List[str]:
        """Detects code patterns and conventions used in the file."""
        patterns = []

        # Check for async/await
        if "async def " in content or "async function" in content:
            patterns.append("async_patterns")

        # Check for documentation
        if '"""' in content or "'''" in content or "/**" in content:
            patterns.append("documented")

        # Check for error handling
        if "try:" in content or "except" in content or "catch" in content:
            patterns.append("error_handling")

        # Check for type hints
        if "->" in content or ": str" in content or ": int" in content:
            patterns.append("type_hints")

        # Check for tests
        if "test" in file_path.lower() or "assert" in content:
            patterns.append("testing")

        # Check for configuration
        if "config" in file_path.lower() or ".env" in file_path.lower():
            patterns.append("configuration")

        return patterns
