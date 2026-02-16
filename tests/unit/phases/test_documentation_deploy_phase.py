"""Tests for DocumentationDeployPhase."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.auto_agent_phases.documentation_deploy_phase import (
    DocumentationDeployPhase,
)


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.file_manager = MagicMock()
    ctx.export_manager = MagicMock()
    ctx.export_manager.initialize_wiki = AsyncMock(return_value=True)
    return ctx


@pytest.fixture
def phase(mock_context):
    return DocumentationDeployPhase(context=mock_context)


class TestDocumentationDeployPhase:
    @pytest.mark.asyncio
    async def test_skips_when_git_push_not_enabled(self, phase):
        files = {"README.md": "# Test"}
        result, _, _ = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=Path("/tmp/test"),
            readme_content="# Test",
            initial_structure={},
            generated_files=files,
            git_push=False,
            file_paths=[],
        )
        assert result == files
        phase.context.logger.info.assert_any_call("Documentation Deploy: Skipped (git_push not enabled)")

    @pytest.mark.asyncio
    async def test_creates_pages_workflow(self, phase, tmp_path):
        files = {"README.md": "# Test", "docs/API.md": "# API Docs"}
        result, _, paths = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=tmp_path,
            readme_content="# Test",
            initial_structure={},
            generated_files=files,
            git_push=True,
            git_token="ghp_test",
            enable_github_pages=True,
            file_paths=[],
        )
        assert ".github/workflows/pages.yml" in result
        assert "Deploy Documentation to GitHub Pages" in result[".github/workflows/pages.yml"]

    @pytest.mark.asyncio
    async def test_inserts_badges_into_readme(self, phase, tmp_path):
        files = {
            "README.md": "# My Project\n\nDescription here.",
            ".github/workflows/deploy.yml": "name: Deploy",
            "SECURITY_SCAN_REPORT.md": "# Scan",
            "LICENSE": "MIT",
        }
        result, _, _ = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=tmp_path,
            readme_content="# My Project",
            initial_structure={},
            generated_files=files,
            git_push=True,
            git_token="ghp_test",
            git_organization="myorg",
            repo_name="test_project",
            file_paths=[],
        )
        readme = result["README.md"]
        assert "![Deploy]" in readme
        assert "![Security]" in readme

    @pytest.mark.asyncio
    async def test_does_not_duplicate_badges(self, phase, tmp_path):
        files = {
            "README.md": "![CI](badge) # My Project",
            ".github/workflows/deploy.yml": "name: Deploy",
        }
        result, _, _ = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=tmp_path,
            readme_content="# My Project",
            initial_structure={},
            generated_files=files,
            git_push=True,
            git_token="ghp_test",
            git_organization="myorg",
            file_paths=[],
        )
        # README should not have been modified since badges already present
        assert result["README.md"].startswith("![CI]")

    @pytest.mark.asyncio
    async def test_initializes_wiki_when_enabled(self, phase, tmp_path):
        files = {
            "README.md": "# Test",
            "docs/ARCHITECTURE.md": "# Architecture",
            "CONTRIBUTING.md": "# Contributing",
        }
        with patch.object(phase, "_initialize_wiki", new_callable=AsyncMock) as mock_wiki:
            await phase.execute(
                project_description="test",
                project_name="test_project",
                project_root=tmp_path,
                readme_content="# Test",
                initial_structure={},
                generated_files=files,
                git_push=True,
                git_token="ghp_test",
                git_organization="myorg",
                repo_name="test_project",
                enable_github_wiki=True,
                file_paths=[],
            )
            mock_wiki.assert_called_once()

    def test_generate_badges_empty_owner(self, phase):
        result = phase._generate_badges("proj", "", "proj", {})
        assert result == ""

    def test_generate_badges_with_workflows(self, phase):
        files = {
            ".github/workflows/ci.yml": "name: CI",
            ".github/workflows/deploy.yml": "name: Deploy",
            "SECURITY_SCAN_REPORT.md": "# Scan",
            "LICENSE": "MIT",
        }
        result = phase._generate_badges("myproject", "myorg", "myproject", files)
        assert "![CI]" in result
        assert "![Deploy]" in result
        assert "![Security]" in result
        assert "![License]" in result

    def test_generate_pages_workflow(self, phase):
        workflow = phase._generate_pages_workflow()
        assert "Deploy Documentation to GitHub Pages" in workflow
        assert "actions/checkout@v4" in workflow
        assert "actions/deploy-pages@v4" in workflow
