"""
Documentation Deploy Phase

Deploys generated documentation to GitHub Wiki and Pages,
and inserts dynamic badges into README.md.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class DocumentationDeployPhase(IAgentPhase):
    """
    Handles documentation deployment:
    - Initializes GitHub Wiki with generated .md files
    - Sets up GitHub Pages deployment workflow
    - Inserts CI/security/license badges into README.md
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
        generated_files: Dict[str, str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        file_paths = kwargs.get("file_paths", [])
        git_token = kwargs.get("git_token", "")
        git_push = kwargs.get("git_push", False)
        enable_wiki = kwargs.get("enable_github_wiki", False)
        enable_pages = kwargs.get("enable_github_pages", False)
        repo_owner = kwargs.get("git_organization", "")
        repo_name = kwargs.get("repo_name", project_name)

        if not git_push:
            self.context.logger.info("Documentation Deploy: Skipped (git_push not enabled)")
            return generated_files, initial_structure, file_paths

        self.context.logger.info("PHASE DOCS: Starting documentation deployment...")
        self.context.event_publisher.publish(
            "phase_start", phase="documentation_deploy", message="Deploying documentation"
        )

        # Collect documentation files
        doc_files = {
            path: content
            for path, content in generated_files.items()
            if path.endswith(".md") and path not in ("README.md", "SECURITY_BLOCKED.md") and content
        }

        # Initialize GitHub Wiki
        if enable_wiki and doc_files and git_token:
            await self._initialize_wiki(project_root, doc_files, repo_owner, repo_name, git_token)

        # Setup GitHub Pages
        if enable_pages:
            pages_workflow = self._generate_pages_workflow()
            workflows_dir = project_root / ".github" / "workflows"
            workflows_dir.mkdir(parents=True, exist_ok=True)
            generated_files[".github/workflows/pages.yml"] = pages_workflow
            self.context.file_manager.write_file(workflows_dir / "pages.yml", pages_workflow)
            if ".github/workflows/pages.yml" not in file_paths:
                file_paths.append(".github/workflows/pages.yml")
            self.context.logger.info("  GitHub Pages workflow created")

        # Insert badges into README
        badges = self._generate_badges(project_name, repo_owner, repo_name, generated_files)
        if badges and "README.md" in generated_files:
            current_readme = generated_files["README.md"]
            # Only insert if badges not already present
            if "![CI]" not in current_readme:
                updated_readme = f"{badges}\n\n{current_readme}"
                generated_files["README.md"] = updated_readme
                self.context.file_manager.write_file(project_root / "README.md", updated_readme)
                self.context.logger.info("  Badges inserted into README.md")

        self.context.event_publisher.publish(
            "phase_complete",
            phase="documentation_deploy",
            message="Documentation deployment complete",
            status="success",
        )

        return generated_files, initial_structure, file_paths

    async def _initialize_wiki(
        self,
        project_root: Path,
        doc_files: Dict[str, str],
        repo_owner: str,
        repo_name: str,
        token: str,
    ) -> None:
        """Initialize GitHub Wiki with documentation files."""
        if not repo_owner or not repo_name:
            self.context.logger.warning("  Wiki: Skipped (missing repo owner/name)")
            return

        self.context.logger.info(f"  Initializing wiki with {len(doc_files)} pages...")

        try:
            # Clone wiki repo
            wiki_url = f"https://{token}@github.com/{repo_owner}/{repo_name}.wiki.git"
            wiki_dir = project_root / ".wiki_temp"

            result = subprocess.run(
                ["git", "clone", wiki_url, str(wiki_dir)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Wiki may not be initialized yet — create initial page via API
                self.context.logger.info("  Wiki not yet initialized, creating Home page...")
                subprocess.run(
                    ["git", "init", str(wiki_dir)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

            # Write doc files as wiki pages
            for doc_path, content in doc_files.items():
                page_name = Path(doc_path).stem.replace("_", "-")
                wiki_file = wiki_dir / f"{page_name}.md"
                wiki_file.write_text(content, encoding="utf-8")

            # Commit and push
            subprocess.run(["git", "add", "-A"], cwd=str(wiki_dir), capture_output=True, timeout=10)
            subprocess.run(
                ["git", "commit", "-m", "docs: Initialize wiki from generated documentation"],
                cwd=str(wiki_dir),
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["git", "remote", "add", "origin", wiki_url],
                cwd=str(wiki_dir),
                capture_output=True,
                timeout=10,
            )
            push_result = subprocess.run(
                ["git", "push", "-u", "origin", "master"],
                cwd=str(wiki_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )

            if push_result.returncode == 0:
                self.context.logger.info("  Wiki initialized successfully")
            else:
                self.context.logger.warning(f"  Wiki push failed: {push_result.stderr}")

            # Cleanup
            import shutil

            shutil.rmtree(wiki_dir, ignore_errors=True)

        except Exception as e:
            self.context.logger.warning(f"  Wiki initialization failed: {e}")

    def _generate_pages_workflow(self) -> str:
        """Generate GitHub Pages deployment workflow."""
        return """name: Deploy Documentation to GitHub Pages

on:
  push:
    branches: [main]
    paths:
      - 'docs/**'
      - '*.md'
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Pages
        uses: actions/configure-pages@v4

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: '.'

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
"""

    def _generate_badges(
        self,
        project_name: str,
        repo_owner: str,
        repo_name: str,
        generated_files: Dict[str, str],
    ) -> str:
        """Generate dynamic badges for README.md."""
        if not repo_owner:
            return ""

        badges = []

        # CI badge
        if any(fp.startswith(".github/workflows/") and "ci" in fp.lower() for fp in generated_files):
            badges.append(f"![CI](https://github.com/{repo_owner}/{repo_name}/actions/workflows/ci.yml/badge.svg)")

        # Deploy badge
        if ".github/workflows/deploy.yml" in generated_files:
            badges.append(
                f"![Deploy](https://github.com/{repo_owner}/{repo_name}/actions/workflows/deploy.yml/badge.svg)"
            )

        # Security badge (if security scan report exists)
        if "SECURITY_SCAN_REPORT.md" in generated_files:
            badges.append("![Security](https://img.shields.io/badge/security-scanned-green)")

        # License badge
        if any("LICENSE" in fp.upper() for fp in generated_files):
            badges.append(f"![License](https://img.shields.io/github/license/{repo_owner}/{repo_name})")

        return " ".join(badges) if badges else ""
