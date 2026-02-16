import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase
from backend.utils.core.git_pr_tool import GitPRTool


class SeniorReviewPhase(IAgentPhase):
    """
    Phase 8: Conducts a senior review of the entire project, with multiple attempts
    to fix issues based on review results.
    """

    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],  # Files to be reviewed and potentially fixed
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        file_paths = kwargs.get("file_paths", [])  # Get from kwargs or assume context has it

        self.context.logger.info("PHASE 8: Starting Senior Review...")
        self.context.event_publisher.publish("phase_start", phase="8", message="Starting Senior Review")

        review_passed = False
        review_attempt = 0
        max_review_attempts = self.context.config.get("senior_review_max_attempts", 3)
        while not review_passed and review_attempt < max_review_attempts:
            review_attempt += 1
            self.context.logger.info(f"PHASE 8: Senior Review Attempt {review_attempt}/{max_review_attempts}...")
            self.context.event_publisher.publish("tool_start", tool_name="senior_review", attempt=review_attempt)

            review_results = self.context.senior_reviewer.perform_review(
                project_description,
                project_name,
                readme_content,
                initial_structure,
                generated_files,
                review_attempt,
            )

            if review_results.get("status") == "passed":
                review_passed = True
                self.context.logger.info("PHASE 8: Senior Review Passed!")
                review_summary_path = "SENIOR_REVIEW_SUMMARY.md"
                generated_files[review_summary_path] = review_results.get("summary", "Senior review passed.")
                self.context.file_manager.write_file(
                    project_root / review_summary_path,
                    generated_files[review_summary_path],
                )
                self.context.event_publisher.publish(
                    "tool_output",
                    tool_name="senior_review",
                    status="passed",
                    summary=review_results.get("summary"),
                )
            else:
                issues = review_results.get("issues", [])
                self.context.logger.warning(f"PHASE 8: Senior Review Failed. Issues found: {len(issues)}")
                self.context.event_publisher.publish(
                    "tool_output",
                    tool_name="senior_review",
                    status="failed",
                    issues=issues,
                )

                # Save detailed issue log
                issue_log = f"""# Senior Review Issues — Attempt {review_attempt}

"""
                issue_log += f"""**Summary:** {review_results.get("summary", "N/A")}

"""
                for i, issue in enumerate(issues, 1):
                    issue_log += f"""## Issue {i}: [{issue.get("severity", "unknown").upper()}]
**File:** {issue.get("file", "N/A")}
**Description:** {issue.get("description", "N/A")}
**Recommendation:** {issue.get("recommendation", "N/A")}

"""
                issue_log_path = f"SENIOR_REVIEW_ISSUES_ATTEMPT_{review_attempt}.md"
                generated_files[issue_log_path] = issue_log
                self.context.file_manager.write_file(project_root / issue_log_path, generated_files[issue_log_path])

                if issues:
                    self.context.logger.info("  Attempting targeted fixes based on senior review issues...")
                    self.context.event_publisher.publish(
                        "tool_start",
                        tool_name="fix_senior_review_issues",
                        count=len(issues),
                    )

                    contingency_plan = self.context.contingency_planner.generate_contingency_plan(
                        issues, project_description, readme_content
                    )
                    if contingency_plan and contingency_plan.get("actions"):
                        self.context.logger.info("  Contingency plan generated. Implementing...")
                        (
                            generated_files,
                            initial_structure,
                            file_paths,
                        ) = self.context.implement_plan(
                            contingency_plan,
                            project_root,
                            readme_content,
                            initial_structure,
                            generated_files,
                            file_paths,
                        )
                    else:
                        # Fallback to simple refinement
                        files_with_issues = set()
                        general_issues = []
                        for issue in issues:
                            file_value = issue.get("file")
                            if file_value:
                                if isinstance(file_value, list):
                                    file_value = str(file_value)
                                    self.context.logger.warning(
                                        f"  Senior Review: 'file' field was a list, converted to string: {file_value}"
                                    )
                                files_with_issues.add(file_value)
                            else:
                                general_issues.append(issue)

                        # Fix files that have specific issues
                        for rel_path in files_with_issues:
                            if (
                                rel_path not in generated_files
                                or not generated_files[rel_path]
                                or len(generated_files[rel_path]) < 10
                            ):
                                continue
                            self.context.logger.info(f"    Fixing {rel_path} (targeted)...")
                            self.context.event_publisher.publish(
                                "tool_start",
                                tool_name="refine_from_senior_review",
                                file=rel_path,
                            )
                            try:
                                file_issues = [iss for iss in issues if iss.get("file") == rel_path]
                                refined = self.context.file_refiner.refine_file(
                                    rel_path,
                                    generated_files[rel_path],
                                    readme_content[:2000],
                                    file_issues,
                                )
                                if refined:
                                    generated_files[rel_path] = refined
                                    self.context.file_manager.write_file(project_root / rel_path, refined)
                                    self.context.event_publisher.publish(
                                        "tool_output",
                                        tool_name="refine_from_senior_review",
                                        file=rel_path,
                                        status="success",
                                    )
                                else:
                                    self.context.logger.warning(f"    Refiner failed to improve {rel_path}.")
                                    self.context.event_publisher.publish(
                                        "tool_output",
                                        tool_name="refine_from_senior_review",
                                        file=rel_path,
                                        status="failed",
                                        message="Refiner failed",
                                    )
                            except Exception as e:
                                self.context.logger.error(f"    Error fixing {rel_path}: {e}")
                                self.context.event_publisher.publish(
                                    "tool_output",
                                    tool_name="refine_from_senior_review",
                                    file=rel_path,
                                    status="error",
                                    message=str(e),
                                )
                            self.context.event_publisher.publish(
                                "tool_end",
                                tool_name="refine_from_senior_review",
                                file=rel_path,
                            )

                        # For general issues without a specific file, refine all non-trivial files
                        if general_issues:
                            self.context.logger.info(
                                f"  Applying {len(general_issues)} general fixes across all files..."
                            )
                            for rel_path, content in list(generated_files.items()):
                                if not content or len(content) < 10 or rel_path in files_with_issues:
                                    continue
                                self.context.event_publisher.publish(
                                    "tool_start",
                                    tool_name="refine_from_senior_review_general",
                                    file=rel_path,
                                )
                                try:
                                    refined = self.context.file_refiner.refine_file(
                                        rel_path,
                                        content,
                                        readme_content[:2000],
                                        general_issues,
                                    )
                                    if refined:
                                        generated_files[rel_path] = refined
                                        self.context.file_manager.write_file(project_root / rel_path, refined)
                                        self.context.event_publisher.publish(
                                            "tool_output",
                                            tool_name="refine_from_senior_review_general",
                                            file=rel_path,
                                            status="success",
                                        )
                                    else:
                                        self.context.logger.warning(f"    Refiner failed to improve {rel_path}.")
                                        self.context.event_publisher.publish(
                                            "tool_output",
                                            tool_name="refine_from_senior_review_general",
                                            file=rel_path,
                                            status="failed",
                                            message="Refiner failed",
                                        )
                                except Exception as e:
                                    self.context.logger.error(f"    Error refining {rel_path}: {e}")
                                    self.context.event_publisher.publish(
                                        "tool_output",
                                        tool_name="refine_from_senior_review_general",
                                        file=rel_path,
                                        status="error",
                                        message=str(e),
                                    )
                                self.context.event_publisher.publish(
                                    "tool_end",
                                    tool_name="refine_from_senior_review_general",
                                    file=rel_path,
                                )
                        self.context.event_publisher.publish("tool_end", tool_name="fix_senior_review_issues")

                    self.context.logger.info("  Re-running verification after senior review fixes...")
                    generated_files = self.context.file_completeness_checker.verify_and_fix(
                        generated_files, readme_content[:2000]
                    )
                    for rel_path, content in generated_files.items():
                        if content:
                            self.context.file_manager.write_file(project_root / rel_path, content)
                else:
                    self.context.logger.warning("  No specific issues provided by senior reviewer to fix.")
            self.context.event_publisher.publish("tool_end", tool_name="senior_review")

        if not review_passed:
            self.context.logger.error(
                "PHASE 8: Senior Review failed after multiple attempts. Manual intervention may be required."
            )

            # NEW: On second failure, attempt aggressive simplification
            if review_attempt >= 2:
                self.context.logger.warning("  PHASE 8: Attempting aggressive simplification to resolve issues...")
                self.context.event_publisher.publish("tool_start", tool_name="aggressive_simplification")

                simplified_count = 0
                for rel_path, content in list(generated_files.items()):
                    if content and len(content) > 100 and not rel_path.endswith((".md", ".json", ".yml", ".yaml")):
                        try:
                            # Use FileRefiner to eliminate redundancy
                            simplified = self.context.file_refiner.simplify_file_content(
                                rel_path, content, remove_redundancy=True
                            )
                            if simplified and len(simplified) < len(content):
                                generated_files[rel_path] = simplified
                                self.context.file_manager.write_file(project_root / rel_path, simplified)
                                simplified_count += 1
                                self.context.logger.info(f"    ✓ Simplified {rel_path}")
                        except Exception as e:
                            self.context.logger.debug(f"    Simplification skipped for {rel_path}: {e}")

                self.context.logger.info(f"  Simplified {simplified_count} files to improve stability")
                self.context.event_publisher.publish(
                    "tool_end",
                    tool_name="aggressive_simplification",
                    files_simplified=simplified_count,
                )

            self.context.file_manager.write_file(
                project_root / "SENIOR_REVIEW_FAILED.md",
                "Senior review failed after multiple attempts.",
            )
            self.context.event_publisher.publish(
                "phase_complete",
                phase="8",
                message="Senior Review failed",
                status="error",
            )
        else:
            self.context.event_publisher.publish(
                "phase_complete",
                phase="8",
                message="Senior Review complete",
                status="success",
            )

        self.context.logger.info(f"Project '{project_name}' completed at {project_root}")
        self.context.event_publisher.publish(
            "project_complete",
            project_name=project_name,
            project_root=str(project_root),
            files_generated=len(file_paths),
        )

        # Log knowledge base statistics
        kb_stats = self.context.error_knowledge_base.get_error_statistics()
        self.context.logger.info(f"Knowledge Base Stats: {kb_stats}")

        # Log fragment cache statistics
        cache_stats = self.context.fragment_cache.stats()
        self.context.logger.info(f"Fragment Cache Stats: {cache_stats}")

        # --- PR-based review (Feature 3) ---
        senior_review_as_pr = kwargs.get("senior_review_as_pr", False)
        git_token = kwargs.get("git_token", "")
        if senior_review_as_pr and git_token and review_passed is not None:
            self._create_review_pr(
                project_root,
                project_name,
                review_results
                if not review_passed
                else {"status": "passed", "summary": "All checks passed", "issues": []},
                generated_files,
            )

        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # PR-based review methods
    # ------------------------------------------------------------------

    def _create_review_pr(
        self,
        project_root: Path,
        project_name: str,
        review_results: Dict[str, Any],
        generated_files: Dict[str, str],
    ) -> None:
        """Create a PR with review findings and post issues as comments."""
        try:
            git_pr = GitPRTool(repo_path=str(project_root), logger=self.context.logger)

            branch_name = "review/senior-review-findings"
            git_pr.create_feature_branch(branch_name)
            git_pr.commit_all("docs: Add senior review findings")
            git_pr.push(branch_name)

            # Build PR body with coherence score and metrics
            pr_body = self._format_pr_body(review_results, generated_files, project_root)

            pr_result = git_pr.create_pr(
                title=f"Senior Review: {project_name}",
                body=pr_body,
                base="main",
                labels=["review", "automated"],
            )

            if pr_result.success and pr_result.pr_number:
                self.context.logger.info(f"  Review PR created: {pr_result.pr_url}")

                # Post individual issues as PR comments
                issues = review_results.get("issues", [])
                if issues:
                    self._post_review_comments(project_root, pr_result.pr_number, issues)

                self.context.event_publisher.publish(
                    "tool_output",
                    tool_name="senior_review_pr",
                    pr_url=pr_result.pr_url,
                    pr_number=pr_result.pr_number,
                )
            else:
                self.context.logger.warning(f"  Review PR creation failed: {pr_result.error}")

            # Switch back to main
            git_pr.switch_branch("main")

        except Exception as e:
            self.context.logger.error(f"  Error creating review PR: {e}")

    def _format_pr_body(
        self,
        review_results: Dict[str, Any],
        generated_files: Dict[str, str],
        project_root: Path,
    ) -> str:
        """Format PR body with coherence score and quality metrics."""
        status = review_results.get("status", "unknown")
        summary = review_results.get("summary", "No summary available")
        issues = review_results.get("issues", [])

        # Calculate coherence score based on review outcome
        if status == "passed":
            coherence_score = 95
        elif len(issues) <= 3:
            coherence_score = 75
        elif len(issues) <= 8:
            coherence_score = 55
        else:
            coherence_score = 35

        # Try to get ruff metrics
        ruff_output = self._run_ruff_metrics(project_root)

        body = f"""## Senior Review Summary

**Status:** {status.upper()}
**Coherence Score:** {coherence_score}/100
**Issues Found:** {len(issues)}

### Summary
{summary}

"""

        if issues:
            body += "### Issues\n\n"
            body += "| # | Severity | File | Description |\n"
            body += "|---|----------|------|-------------|\n"
            for i, issue in enumerate(issues, 1):
                sev = issue.get("severity", "unknown")
                file = issue.get("file", "N/A")
                desc = issue.get("description", "N/A")[:80]
                body += f"| {i} | {sev} | `{file}` | {desc} |\n"
            body += "\n"

        if ruff_output:
            body += f"### Ruff Quality Metrics\n\n```\n{ruff_output}\n```\n\n"

        body += f"---\n*Generated by Ollash AutoAgent Senior Review*\nFiles analyzed: {len(generated_files)}"

        return body

    def _run_ruff_metrics(self, project_root: Path) -> str:
        """Run ruff check and return statistics summary."""
        try:
            result = subprocess.run(
                ["ruff", "check", "--statistics", "."],
                capture_output=True,
                text=True,
                cwd=str(project_root),
                timeout=30,
            )
            return result.stdout.strip() if result.stdout else ""
        except Exception:
            return ""

    def _post_review_comments(self, project_root: Path, pr_number: int, issues: List[Dict]) -> None:
        """Post review issues as individual PR comments."""
        for issue in issues[:10]:  # Limit to 10 comments
            file_path = issue.get("file", "")
            severity = issue.get("severity", "unknown")
            description = issue.get("description", "")
            recommendation = issue.get("recommendation", "")

            comment = (
                f"**[{severity.upper()}]** {description}\n\n"
                f"**File:** `{file_path}`\n"
                f"**Recommendation:** {recommendation}"
            )

            try:
                subprocess.run(
                    ["gh", "pr", "comment", str(pr_number), "--body", comment],
                    capture_output=True,
                    text=True,
                    cwd=str(project_root),
                    timeout=15,
                )
            except Exception as e:
                self.context.logger.debug(f"  Could not post comment: {e}")
