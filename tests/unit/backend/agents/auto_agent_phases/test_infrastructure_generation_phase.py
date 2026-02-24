import pytest
from unittest.mock import MagicMock
from pathlib import Path
from backend.agents.auto_agent_phases.infrastructure_generation_phase import InfrastructureGenerationPhase

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.infra_generator = MagicMock()
    ctx.file_manager = MagicMock()
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    return ctx

@pytest.fixture
def phase(mock_context):
    return InfrastructureGenerationPhase(mock_context)

@pytest.mark.asyncio
async def test_infrastructure_generation_all_disabled(phase, mock_context):
    """If flags are False, only CI and Dependabot should be generated."""
    project_root = Path("/tmp/test")
    generated_files = {}
    file_paths = []

    # Needs detection mock
    mock_context.infra_generator.detect_infra_needs.return_value = {
        "languages": ["python"], "databases": [], "has_web_server": False
    }

    result_files, _, _ = await phase.execute(
        "desc", "project", project_root, "readme", {}, generated_files,
        include_docker=False, include_terraform=False, file_paths=file_paths
    )

    # Should have CI and Dependabot but NOT Docker or Terraform
    assert "Dockerfile" not in result_files
    assert "docker-compose.yml" not in result_files
    assert "terraform/main.tf" not in result_files
    assert "k8s/deployment.yml" not in result_files
    assert ".github/workflows/ci.yml" in result_files
    assert ".github/dependabot.yml" in result_files
    assert ".github/workflows/deploy.yml" not in result_files

@pytest.mark.asyncio
async def test_infrastructure_generation_docker_enabled(phase, mock_context):
    """If include_docker=True, Docker and K8s files should be generated."""
    project_root = Path("/tmp/test")
    generated_files = {}
    file_paths = []

    mock_context.infra_generator.detect_infra_needs.return_value = {
        "languages": ["python"], "databases": [], "has_web_server": True
    }
    mock_context.infra_generator.generate_dockerfile.return_value = "FROM python"
    mock_context.infra_generator.generate_docker_compose.return_value = "version: 3"
    mock_context.infra_generator.generate_k8s_deployment.return_value = "apiVersion: apps/v1"

    result_files, _, _ = await phase.execute(
        "desc", "project", project_root, "readme", {}, generated_files,
        include_docker=True, include_terraform=False, file_paths=file_paths
    )

    assert "Dockerfile" in result_files
    assert "docker-compose.yml" in result_files
    assert "k8s/deployment.yml" in result_files
    assert ".github/workflows/deploy.yml" in result_files
    assert "terraform/main.tf" not in result_files

@pytest.mark.asyncio
async def test_infrastructure_generation_terraform_enabled(phase, mock_context):
    """If include_terraform=True, Terraform files should be generated."""
    project_root = Path("/tmp/test")
    generated_files = {}
    file_paths = []

    mock_context.infra_generator.detect_infra_needs.return_value = {
        "languages": ["python"], "databases": [], "has_web_server": True
    }
    mock_context.infra_generator.generate_terraform_main.return_value = "resource aws_s3_bucket"

    result_files, _, _ = await phase.execute(
        "desc", "project", project_root, "readme", {}, generated_files,
        include_docker=False, include_terraform=True, file_paths=file_paths
    )

    assert "terraform/main.tf" in result_files
    assert ".github/workflows/deploy.yml" in result_files
    assert "Dockerfile" not in result_files
