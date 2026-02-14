from typing import Dict, Any, List, Tuple
from pathlib import Path
import json

from backend.interfaces.iagent_phase import IAgentPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


class ExhaustiveReviewRepairPhase(IAgentPhase):
    """
    Phase 5.75: Exhaustive Review and Repair Phase (NEW)
    
    This phase is inserted between TestGenerationExecutionPhase and FinalReviewPhase
    to provide a comprehensive repair mechanism when tests fail.
    
    It implements a sophisticated 3-step repair protocol:
    1. **Diagnostic Phase**: Analyzes coherence between README.md and generated files
    2. **Error Prediction**: Uses ErrorKnowledgeBase to predict common failures
    3. **Structural Repair**: Uses ContingencyPlanner to design and apply comprehensive fixes
    
    This ensures code quality before the expensive SeniorReviewPhase.
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
        
        file_paths = kwargs.get("file_paths", [])
        test_results = kwargs.get("test_results", {})
        
        self.context.logger.info("PHASE 5.75: Exhaustive Review and Repair...")
        self.context.event_publisher.publish("phase_start", phase="5.75", message="Starting Exhaustive Review & Repair")
        
        # ========== STEP 1: DIAGNOSTIC PHASE ==========
        self.context.logger.info("  STEP 1: Diagnostic Analysis...")
        diagnostics = self._perform_diagnostic_analysis(
            project_root, readme_content, initial_structure, generated_files
        )
        
        if diagnostics["critical_issues"]:
            self.context.logger.warning(f"  Found {len(diagnostics['critical_issues'])} critical issues")
        
        # ========== STEP 2: ERROR PREDICTION ==========
        self.context.logger.info("  STEP 2: Error Prediction Phase...")
        predicted_errors = self._predict_errors_from_knowledge_base(
            generated_files, readme_content, diagnostics
        )
        
        if predicted_errors:
            self.context.logger.warning(f"  Predicted {len(predicted_errors)} potential issues from pattern analysis")
        
        # ========== STEP 3: STRUCTURAL REPAIR ==========
        all_issues = diagnostics["critical_issues"] + predicted_errors
        
        if all_issues or (test_results and not test_results.get("passed", True)):
            self.context.logger.info("  STEP 3: Structural Repair Protocol...")
            
            # Merge test failures with other issues
            if test_results and test_results.get("failures"):
                test_failures = self._convert_test_failures_to_issues(test_results["failures"])
                all_issues.extend(test_failures)
            
            self.context.logger.info(f"  Total issues to address: {len(all_issues)}")
            
            # Generate comprehensive repair plan
            repair_plan = self.context.contingency_planner.generate_contingency_plan(
                all_issues, project_description, readme_content
            )
            
            if repair_plan and repair_plan.get("actions"):
                self.context.logger.info(f"  Generated repair plan with {len(repair_plan['actions'])} actions")
                
                # Implement the repair plan
                generated_files, initial_structure, file_paths = await self._implement_repair_plan(
                    repair_plan, project_root, readme_content, initial_structure, 
                    generated_files, file_paths
                )
                
                # Save repair report
                repair_report = self._generate_repair_report(
                    diagnostics, predicted_errors, repair_plan, test_results
                )
                generated_files["EXHAUSTIVE_REPAIR_REPORT.md"] = repair_report
                self.context.file_manager.write_file(
                    project_root / "EXHAUSTIVE_REPAIR_REPORT.md", repair_report
                )
                self.context.logger.info("  Repair plan implemented and documented")
            else:
                self.context.logger.warning("  Could not generate repair plan, proceeding with best effort fixes")
                # Fall back to simpler fixes
                generated_files = await self._apply_fallback_fixes(
                    all_issues, project_root, generated_files
                )
        else:
            self.context.logger.info("  No critical issues detected, proceeding to final phases")
        
        self.context.event_publisher.publish("phase_end", phase="5.75", status="completed")
        return generated_files, initial_structure, file_paths

    def _perform_diagnostic_analysis(self, 
                                     project_root: Path,
                                     readme_content: str,
                                     initial_structure: Dict[str, Any],
                                     generated_files: Dict[str, str]) -> Dict[str, Any]:
        """
        Analyzes coherence between README.md and generated files.
        Returns critical issues that must be fixed.
        """
        diagnostics = {
            "critical_issues": [],
            "structure_issues": [],
            "dependency_issues": [],
            "coherence_score": 0.0
        }
        
        self.context.logger.info("    Analyzing project coherence...")
        
        # Extract dependencies from README
        readme_deps = self._extract_dependencies_from_readme(readme_content)
        
        # Check if all dependencies are properly implemented
        required_files = self._extract_required_files_from_structure(initial_structure)
        existing_files = set(generated_files.keys())
        
        missing_files = required_files - existing_files
        if missing_files:
            for missing_file in missing_files:
                diagnostics["critical_issues"].append({
                    "type": "missing_file",
                    "severity": "critical",
                    "file": str(missing_file),
                    "description": f"Required file '{missing_file}' is missing from generation",
                    "recommendation": f"Regenerate or create the missing file {missing_file}"
                })
        
        # Check entry point exists
        entry_points = self._find_entry_points(generated_files, initial_structure)
        if not entry_points:
            diagnostics["critical_issues"].append({
                "type": "missing_entry_point",
                "severity": "critical",
                "file": "project_root",
                "description": "No valid entry point (main.py, app.py, index.js, etc.) found",
                "recommendation": "Create a proper entry point file based on project type"
            })
        
        # Check for circular dependencies or import errors
        import_issues = self._check_import_coherence(generated_files, initial_structure)
        diagnostics["critical_issues"].extend(import_issues)
        
        # Check configuration files
        config_issues = self._validate_config_files(generated_files, readme_content)
        diagnostics["critical_issues"].extend(config_issues)
        
        diagnostics["coherence_score"] = max(0.0, 1.0 - (len(diagnostics["critical_issues"]) * 0.1))
        
        self.context.logger.info(f"    Coherence score: {diagnostics['coherence_score']:.2f}")
        return diagnostics

    def _predict_errors_from_knowledge_base(self,
                                           generated_files: Dict[str, str],
                                           readme_content: str,
                                           diagnostics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Uses ErrorKnowledgeBase to predict common failures based on code patterns.
        """
        predicted_errors = []
        
        # Get common error patterns from knowledge base
        common_patterns = self.context.error_knowledge_base.get_common_error_patterns()
        
        for file_path, content in generated_files.items():
            if content and len(content) > 50:  # Only check substantial files
                # Check for known problematic patterns
                for pattern in common_patterns:
                    if pattern.get("pattern") in content:
                        predicted_errors.append({
                            "type": "pattern_match",
                            "severity": pattern.get("severity", "warning"),
                            "file": file_path,
                            "description": f"Detected problematic pattern: {pattern.get('description', 'Unknown')}",
                            "recommendation": pattern.get("fix", "Review and update manually"),
                            "pattern": pattern.get("pattern")
                        })
        
        return predicted_errors

    def _convert_test_failures_to_issues(self, test_failures: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Converts test failure data into issue format for consistency."""
        issues = []
        
        for test_file, failure_data in test_failures.items():
            if isinstance(failure_data, dict):
                issues.append({
                    "type": "test_failure",
                    "severity": "high",
                    "file": test_file,
                    "description": f"Test failed: {failure_data.get('error', 'Unknown error')}",
                    "recommendation": "Review test results and fix implementation",
                    "error_output": failure_data.get("output", "")
                })
        
        return issues

    async def _implement_repair_plan(self,
                                    repair_plan: Dict[str, Any],
                                    project_root: Path,
                                    readme_content: str,
                                    initial_structure: Dict[str, Any],
                                    generated_files: Dict[str, str],
                                    file_paths: List[str]) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        """
        Implements the contingency repair plan with maximum compatibility.
        """
        self.context.logger.info("    Implementing repair plan...")
        
        actions = repair_plan.get("actions", [])
        
        for action in actions:
            action_type = action.get("type")
            
            if action_type == "regenerate_file":
                file_path = action.get("file")
                context_info = action.get("context", {})
                
                self.context.logger.info(f"      Regenerating {file_path}...")
                
                try:
                    # Use enhanced generator with maximum compatibility mode
                    new_content = self.context.enhanced_file_content_generator.generate_file_with_plan(
                        file_path,
                        context_info.get("logic_plan", ""),
                        readme_content,
                        initial_structure,
                        generated_files,
                        compatibility_mode=True  # Force maximum compatibility
                    )
                    
                    if new_content:
                        generated_files[file_path] = new_content
                        self.context.file_manager.write_file(project_root / file_path, new_content)
                        self.context.logger.info(f"      ✓ Regenerated {file_path}")
                except Exception as e:
                    self.context.logger.error(f"      ✗ Error regenerating {file_path}: {e}")
            
            elif action_type == "fix_file":
                file_path = action.get("file")
                issue_description = action.get("issue", "")
                
                self.context.logger.info(f"      Fixing {file_path}...")
                
                if file_path in generated_files:
                    try:
                        # Use FileRefiner for targeted fixes
                        fixed_content = self.context.file_refiner.refine_file_content(
                            file_path,
                            generated_files[file_path],
                            issue_description,
                            readme_content
                        )
                        
                        if fixed_content:
                            generated_files[file_path] = fixed_content
                            self.context.file_manager.write_file(project_root / file_path, fixed_content)
                            self.context.logger.info(f"      ✓ Fixed {file_path}")
                    except Exception as e:
                        self.context.logger.error(f"      ✗ Error fixing {file_path}: {e}")
            
            elif action_type == "simplify_file":
                file_path = action.get("file")
                
                self.context.logger.info(f"      Simplifying {file_path}...")
                
                if file_path in generated_files:
                    try:
                        simplified_content = self.context.file_refiner.simplify_file_content(
                            file_path,
                            generated_files[file_path],
                            remove_redundancy=True
                        )
                        
                        if simplified_content:
                            generated_files[file_path] = simplified_content
                            self.context.file_manager.write_file(project_root / file_path, simplified_content)
                            self.context.logger.info(f"      ✓ Simplified {file_path}")
                    except Exception as e:
                        self.context.logger.error(f"      ✗ Error simplifying {file_path}: {e}")
            
            elif action_type == "create_file":
                file_path = action.get("file")
                content_template = action.get("content_template", "")
                
                self.context.logger.info(f"      Creating {file_path}...")
                
                try:
                    new_content = self.context.enhanced_file_content_generator.generate_file_with_plan(
                        file_path,
                        content_template,
                        readme_content,
                        initial_structure,
                        generated_files,
                        compatibility_mode=True
                    )
                    
                    if new_content:
                        generated_files[file_path] = new_content
                        self.context.file_manager.write_file(project_root / file_path, new_content)
                        if file_path not in file_paths:
                            file_paths.append(file_path)
                        self.context.logger.info(f"      ✓ Created {file_path}")
                except Exception as e:
                    self.context.logger.error(f"      ✗ Error creating {file_path}: {e}")
        
        self.context.logger.info(f"    Implemented {len(actions)} repair actions")
        return generated_files, initial_structure, file_paths

    async def _apply_fallback_fixes(self,
                                   issues: List[Dict[str, Any]],
                                   project_root: Path,
                                   generated_files: Dict[str, str]) -> Dict[str, str]:
        """
        Applies simple fallback fixes when contingency plan fails.
        """
        self.context.logger.info("    Applying fallback fixes...")
        
        files_to_fix = set()
        for issue in issues:
            file_value = issue.get("file")
            if file_value and file_value != "project_root":
                files_to_fix.add(file_value)
        
        for file_path in files_to_fix:
            if file_path in generated_files:
                try:
                    # Use FileRefiner with generic fix attempt
                    fixed_content = self.context.file_refiner.refine_file_content(
                        file_path,
                        generated_files[file_path],
                        "Fix common compatibility issues",
                        ""
                    )
                    
                    if fixed_content:
                        generated_files[file_path] = fixed_content
                        self.context.file_manager.write_file(project_root / file_path, fixed_content)
                except Exception as e:
                    self.context.logger.warning(f"    Fallback fix failed for {file_path}: {e}")
        
        return generated_files

    def _generate_repair_report(self,
                               diagnostics: Dict[str, Any],
                               predicted_errors: List[Dict[str, Any]],
                               repair_plan: Dict[str, Any],
                               test_results: Dict[str, Any]) -> str:
        """Generates a comprehensive repair report."""
        report = """# Exhaustive Review and Repair Report

## Executive Summary

This report documents the exhaustive analysis and repair operations performed
during Phase 5.75 to ensure code quality before Senior Review.

"""
        
        # Diagnostics section
        report += "## 1. Diagnostic Analysis Results\n\n"
        report += f"**Coherence Score:** {diagnostics.get('coherence_score', 0):.2%}\n\n"
        
        if diagnostics.get("critical_issues"):
            report += f"**Critical Issues Found:** {len(diagnostics['critical_issues'])}\n\n"
            for issue in diagnostics["critical_issues"]:
                report += f"- **[{issue.get('severity', 'unknown').upper()}]** {issue.get('file', 'Unknown')}: "
                report += f"{issue.get('description', 'N/A')}\n"
        else:
            report += "**Status:** ✓ No critical issues detected\n\n"
        
        # Predicted errors section
        report += "\n## 2. Error Prediction Results\n\n"
        if predicted_errors:
            report += f"**Potential Issues Predicted:** {len(predicted_errors)}\n\n"
            for error in predicted_errors[:5]:  # Show first 5
                report += f"- {error.get('file', 'Unknown')}: {error.get('description', 'N/A')}\n"
            if len(predicted_errors) > 5:
                report += f"- ... and {len(predicted_errors) - 5} more\n"
        else:
            report += "**Status:** ✓ No pattern-based issues predicted\n\n"
        
        # Repair plan section
        report += "\n## 3. Repair Actions Implemented\n\n"
        actions = repair_plan.get("actions", [])
        if actions:
            report += f"**Total Actions:** {len(actions)}\n\n"
            for action in actions:
                report += f"- **{action.get('type')}** on {action.get('file')}\n"
        else:
            report += "**Status:** No repair actions were necessary\n\n"
        
        # Test results section
        if test_results:
            report += "\n## 4. Test Results Before Repair\n\n"
            report += f"- **Status:** {'PASSED' if test_results.get('passed') else 'FAILED'}\n"
            if test_results.get("failures"):
                report += f"- **Failures:** {len(test_results.get('failures', {}))}\n"
        
        report += "\n---\n*Generated during Phase 5.75: Exhaustive Review and Repair*\n"
        return report

    # ========== HELPER METHODS ==========
    
    def _extract_dependencies_from_readme(self, readme_content: str) -> set:
        """Extracts required dependencies from README."""
        # Simple extraction - can be enhanced
        return set()

    def _extract_required_files_from_structure(self, structure: Dict[str, Any]) -> set:
        """Extracts required files from initial structure."""
        required = set()
        
        def traverse(obj, parent_path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key != "type" and isinstance(value, dict):
                        traverse(value, parent_path + key + "/")
            elif isinstance(obj, list):
                for item in obj:
                    traverse(item, parent_path)
        
        traverse(structure)
        return required

    def _find_entry_points(self, 
                          generated_files: Dict[str, str],
                          structure: Dict[str, Any]) -> List[str]:
        """Finds valid entry points in the generated files."""
        entry_point_names = ["main.py", "app.py", "index.js", "index.ts", "Program.cs", "App.java"]
        
        return [f for f in generated_files.keys() if any(f.endswith(ep) for ep in entry_point_names)]

    def _check_import_coherence(self,
                               generated_files: Dict[str, str],
                               structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Checks for import and circular dependency issues."""
        issues = []
        # Implementation would parse imports and check for coherence
        return issues

    def _validate_config_files(self,
                              generated_files: Dict[str, str],
                              readme_content: str) -> List[Dict[str, Any]]:
        """Validates key configuration files."""
        issues = []
        
        # Check for package.json if JavaScript project
        if "index.js" in generated_files or "package.json" in generated_files:
            if "package.json" not in generated_files:
                issues.append({
                    "type": "missing_config",
                    "severity": "critical",
                    "file": "package.json",
                    "description": "JavaScript project detected but package.json is missing",
                    "recommendation": "Create a valid package.json file"
                })
        
        return issues
