"""Tests for InfrastructureGenerationPhase."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.infrastructure_generation_phase import (
    InfrastructureGenerationPhase,
)


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.file_manager = MagicMock()

    ctx.infra_generator = MagicMock()
    ctx.infra_generator.detect_infra_needs.return_value = {
        "has_web_server": True,
        "has_database": True,
        "has_api": True,
        "has_frontend": False,
        "has_worker": False,
        "languages": ["python"],
        "frameworks": ["flask"],
        "databases": ["postgresql"],
        "ports": [8000],
    }
    ctx.infra_generator.generate_dockerfile.return_value = "FROM python:3.11-slim\n"
    ctx.infra_generator.generate_docker_compose.return_value = "version: '3.8'\n"
    ctx.infra_generator.generate_k8s_deployment.return_value = "apiVersion: apps/v1\n"
    ctx.infra_generator.generate_terraform_main.return_value = "terraform {}\n"
    return ctx


@pytest.fixture
def phase(mock_context):
    return InfrastructureGenerationPhase(context=mock_context)


class TestInfrastructureGenerationPhase:
    @pytest.mark.asyncio
    async def test_skips_when_infra_generator_not_available(self, phase):
        phase.context.infra_generator = None
        files = {"main.py": "print('hello')"}
        result, _, _ = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=Path("/tmp/test"),
            readme_content="# Flask App with PostgreSQL",
            initial_structure={},
            generated_files=files,
            file_paths=[],
        )
        assert result == files

    @pytest.mark.asyncio
    async def test_generates_dockerfile(self, phase, tmp_path):
        files = {"main.py": "from flask import Flask\n", "requirements.txt": "flask\n"}
        result, _, paths = await phase.execute(
            project_description="Flask web app",
            project_name="test_project",
            project_root=tmp_path,
            readme_content="# Flask App",
            initial_structure={},
            generated_files=files,
            file_paths=[],
            include_docker=True,
        )
        assert "Dockerfile" in result
        assert "docker-compose.yml" in result
        phase.context.infra_generator.generate_dockerfile.assert_called_once()

    @pytest.mark.asyncio
    async def test_generates_k8s_manifests(self, phase, tmp_path):
        files = {"main.py": "app = Flask(__name__)\n"}
        result, _, paths = await phase.execute(
            project_description="test",
            project_name="myapp",
            project_root=tmp_path,
            readme_content="# App",
            initial_structure={},
            generated_files=files,
            file_paths=[],
        )
        assert "k8s/deployment.yml" in result
        phase.context.infra_generator.generate_k8s_deployment.assert_called_once()

    @pytest.mark.asyncio
    async def test_generates_terraform(self, phase, tmp_path):
        files = {"main.py": ""}
        result, _, _ = await phase.execute(
            project_description="test",
            project_name="myapp",
            project_root=tmp_path,
            readme_content="# App",
            initial_structure={},
            generated_files=files,
            file_paths=[],
        )
        assert "terraform/main.tf" in result

    @pytest.mark.asyncio
    async def test_generates_deploy_workflow(self, phase, tmp_path):
        files = {"main.py": ""}
        result, _, _ = await phase.execute(
            project_description="test",
            project_name="myapp",
            project_root=tmp_path,
            readme_content="# App",
            initial_structure={},
            generated_files=files,
            file_paths=[],
        )
        assert ".github/workflows/deploy.yml" in result

    @pytest.mark.asyncio
    async def test_generates_dependabot_config(self, phase, tmp_path):
        files = {"requirements.txt": "flask\n", "main.py": ""}
        result, _, _ = await phase.execute(
            project_description="test",
            project_name="myapp",
            project_root=tmp_path,
            readme_content="# App",
            initial_structure={},
            generated_files=files,
            file_paths=[],
        )
        assert ".github/dependabot.yml" in result
        dependabot = result[".github/dependabot.yml"]
        assert "pip" in dependabot

    @pytest.mark.asyncio
    async def test_publishes_events(self, phase, tmp_path):
        files = {"main.py": ""}
        await phase.execute(
            project_description="test",
            project_name="myapp",
            project_root=tmp_path,
            readme_content="# App",
            initial_structure={},
            generated_files=files,
            file_paths=[],
        )
        phase.context.event_publisher.publish.assert_any_call(
            "phase_start", phase="infrastructure", message="Generating infrastructure files"
        )

    def test_detect_required_secrets(self, phase):
        files = {
            "main.py": 'db_url = os.environ["DATABASE_URL"]\n',
            "config.py": 'api_key = os.getenv("API_KEY")\n',
        }
        secrets = phase._detect_required_secrets(files)
        assert "DATABASE_URL" in secrets
        assert "API_KEY" in secrets

    def test_detect_required_secrets_skips_common_vars(self, phase):
        files = {"main.py": 'path = os.environ["PATH"]\nhome = os.getenv("HOME")\n'}
        secrets = phase._detect_required_secrets(files)
        assert "PATH" not in secrets
        assert "HOME" not in secrets

    def test_generate_dependabot_config_multiple_ecosystems(self, phase):
        files = {
            "requirements.txt": "flask\n",
            "package.json": "{}",
            "go.mod": "module app",
            ".github/workflows/ci.yml": "name: CI",
        }
        result = phase._generate_dependabot_config({"languages": ["python", "node", "go"]}, files)
        assert "pip" in result
        assert "npm" in result
        assert "gomod" in result
        assert "github-actions" in result

    def test_track_file_no_duplicates(self, phase):
        paths = ["main.py"]
        phase._track_file("main.py", paths)
        assert paths.count("main.py") == 1

    def test_track_file_adds_new(self, phase):
        paths = ["main.py"]
        phase._track_file("Dockerfile", paths)
        assert "Dockerfile" in paths
