import pytest
from unittest.mock import MagicMock
from backend.utils.domains.auto_generation.generation.infra_generator import InfraGenerator


@pytest.fixture
def infra_gen():
    client = MagicMock()
    logger = MagicMock()
    parser = MagicMock()
    return InfraGenerator(client, logger, parser)


def test_detect_infra_needs_flask(infra_gen):
    readme = "A simple Flask application with postgres"
    structure = {}
    files = {"app.py": "from flask import Flask"}

    needs = infra_gen.detect_infra_needs(readme, structure, files)

    assert needs["has_web_server"] is True
    assert needs["has_api"] is True
    assert "postgresql" in needs["databases"]
    assert "python" in needs["languages"]


def test_generate_dockerfile_python(infra_gen):
    dockerfile = infra_gen.generate_dockerfile("python", "test-app")
    assert "FROM python:3.11-slim" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "main:app" in dockerfile


def test_generate_docker_compose_with_db(infra_gen):
    needs = {"databases": ["postgresql"], "has_web_server": True}
    compose = infra_gen.generate_docker_compose(needs, "test-app")

    assert "postgres:" in compose
    assert "image: postgres:16-alpine" in compose
    assert "app:" in compose
    assert "volumes:" in compose


def test_generate_k8s_deployment(infra_gen):
    needs = {"has_web_server": True}
    k8s = infra_gen.generate_k8s_deployment("test-app", needs)

    assert "kind: Deployment" in k8s
    assert "name: test-app" in k8s
    assert "image: test-app:latest" in k8s
    assert "---" in k8s
    assert "kind: Service" in k8s


def test_generate_terraform_aws(infra_gen):
    needs = {"databases": ["postgresql"], "has_web_server": True}
    tf = infra_gen.generate_terraform_main(needs, cloud="aws")

    assert 'provider "aws"' in tf
    assert 'resource "aws_db_instance" "postgres"' in tf
    assert 'resource "aws_ecs_cluster" "main"' in tf
