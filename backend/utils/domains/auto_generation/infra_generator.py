"""
Infrastructure as Code Generator

Generates Terraform and Kubernetes configuration files based on
project requirements detected from README and structure.
"""

from typing import Any, Dict

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.llm_response_parser import LLMResponseParser


class InfraGenerator:
    """Generates IaC files (Terraform, Kubernetes, Docker) for generated projects."""

    def __init__(
        self,
        llm_client: Any,
        logger: AgentLogger,
        response_parser: LLMResponseParser,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.response_parser = response_parser

    def detect_infra_needs(self, readme: str, structure: Dict, generated_files: Dict[str, str]) -> Dict[str, Any]:
        """Detect infrastructure requirements from project content."""
        needs = {
            "has_web_server": False,
            "has_database": False,
            "has_api": False,
            "has_frontend": False,
            "has_worker": False,
            "languages": set(),
            "frameworks": set(),
            "databases": set(),
            "ports": [],
        }

        readme_lower = readme.lower()

        # Detect web server / API
        if any(kw in readme_lower for kw in ["flask", "fastapi", "django", "express", "nest", "gin"]):
            needs["has_web_server"] = True
            needs["has_api"] = True
        if any(kw in readme_lower for kw in ["react", "vue", "angular", "svelte", "next"]):
            needs["has_frontend"] = True

        # Detect databases
        db_map = {
            "postgres": "postgresql",
            "mysql": "mysql",
            "mongodb": "mongodb",
            "redis": "redis",
            "sqlite": "sqlite",
            "dynamodb": "dynamodb",
        }
        for keyword, db_name in db_map.items():
            if keyword in readme_lower:
                needs["databases"].add(db_name)
                needs["has_database"] = True

        # Detect from files
        for fp in generated_files:
            if fp.endswith(".py"):
                needs["languages"].add("python")
            elif fp.endswith((".js", ".ts")):
                needs["languages"].add("node")
            elif fp.endswith(".go"):
                needs["languages"].add("go")
            elif fp.endswith(".rs"):
                needs["languages"].add("rust")

        # Detect worker/queue
        if any(kw in readme_lower for kw in ["celery", "worker", "queue", "rabbitmq", "kafka"]):
            needs["has_worker"] = True

        # Convert sets to lists for serialization
        needs["languages"] = list(needs["languages"])
        needs["frameworks"] = list(needs["frameworks"])
        needs["databases"] = list(needs["databases"])

        return needs

    def generate_dockerfile(self, language: str, project_name: str) -> str:
        """Generate a basic Dockerfile for the primary language."""
        templates = {
            "python": """FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
            "node": """FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --production

COPY . .

EXPOSE 3000

CMD ["node", "src/index.js"]
""",
            "go": """FROM golang:1.22-alpine AS builder

WORKDIR /app
COPY go.* ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 go build -o /bin/app .

FROM alpine:3.19
COPY --from=builder /bin/app /bin/app
EXPOSE 8080
CMD ["/bin/app"]
""",
        }

        return templates.get(language, templates["python"])

    def generate_docker_compose(self, needs: Dict[str, Any], project_name: str) -> str:
        """Generate docker-compose.yml based on detected needs."""
        services = []
        services.append("""  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL:-sqlite:///db.sqlite3}
    depends_on: []""")

        if "postgresql" in needs.get("databases", []):
            services.append("""  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: app_db
      POSTGRES_USER: app_user
      POSTGRES_PASSWORD: app_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data""")

        if "redis" in needs.get("databases", []):
            services.append("""  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379" """)

        if "mongodb" in needs.get("databases", []):
            services.append("""  mongodb:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db""")

        if needs.get("has_worker"):
            services.append("""  worker:
    build: .
    command: celery -A app.celery worker --loglevel=info
    depends_on:
      - redis""")

        volumes = []
        if "postgresql" in needs.get("databases", []):
            volumes.append("  postgres_data:")
        if "mongodb" in needs.get("databases", []):
            volumes.append("  mongo_data:")

        compose = f"""version: '3.8'

services:
{chr(10).join(services)}
"""
        if volumes:
            compose += f"""
volumes:
{chr(10).join(volumes)}
"""
        return compose

    def generate_terraform_main(self, needs: Dict[str, Any], cloud: str = "aws") -> str:
        """Generate main.tf based on infrastructure needs."""
        if cloud == "aws":
            return self._generate_terraform_aws(needs)
        return self._generate_terraform_generic(needs)

    def _generate_terraform_aws(self, needs: Dict[str, Any]) -> str:
        resources = [
            """terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "app"
}
"""
        ]

        if needs.get("has_web_server") or needs.get("has_api"):
            resources.append("""
# ECS Fargate for application
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${var.project_name}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"

  container_definitions = jsonencode([{
    name  = "app"
    image = "${var.project_name}:latest"
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
    }]
  }])
}
""")

        if "postgresql" in needs.get("databases", []):
            resources.append("""
# RDS PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier           = "${var.project_name}-db"
  engine               = "postgres"
  engine_version       = "16"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  db_name              = "app_db"
  username             = "app_user"
  skip_final_snapshot  = true

  tags = {
    Name = "${var.project_name}-database"
  }
}
""")

        if "redis" in needs.get("databases", []):
            resources.append("""
# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.project_name}-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  port                 = 6379
}
""")

        return "\n".join(resources)

    def _generate_terraform_generic(self, needs: Dict[str, Any]) -> str:
        return """# Generic Terraform configuration
# Adapt to your cloud provider

terraform {
  required_version = ">= 1.5"
}

variable "project_name" {
  default = "app"
}

# Add your provider and resource configurations here
"""

    def generate_deploy_workflow(self, language: str, project_name: str, cloud_provider: str = "generic") -> str:
        """Generate a GitHub Actions deploy workflow for detected stack."""
        install_steps = {
            "python": "      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.11'\n      - run: pip install -r requirements.txt",
            "node": "      - uses: actions/setup-node@v4\n        with:\n          node-version: '20'\n      - run: npm ci",
            "go": "      - uses: actions/setup-go@v5\n        with:\n          go-version: '1.22'\n      - run: go mod download",
        }
        install = install_steps.get(language, install_steps["python"])

        return f"""name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
{install}
      - name: Build Docker image
        run: docker build -t {project_name}:${{{{ github.sha }}}} .
      - name: Push to registry
        if: github.ref == 'refs/heads/main'
        run: |
          echo "Deploy step — configure your registry and deployment target here."
          echo "Image: {project_name}:${{{{ github.sha }}}}"
"""

    def generate_dependabot_config(self, ecosystems: list) -> str:
        """Generate .github/dependabot.yml for detected package ecosystems."""
        if not ecosystems:
            ecosystems = ["pip"]

        updates = []
        for eco in ecosystems:
            updates.append(
                f'  - package-ecosystem: "{eco}"\n'
                f'    directory: "/"\n'
                f"    schedule:\n"
                f'      interval: "weekly"\n'
                f"    open-pull-requests-limit: 10"
            )

        return f"version: 2\nupdates:\n{chr(10).join(updates)}\n"

    def detect_required_secrets(self, generated_files: Dict[str, str]) -> list:
        """Scan code for environment variable references that may need GitHub Secrets."""
        import re

        patterns = [
            r"os\.environ\[[\"\'](\w+)[\"\']\]",
            r"os\.getenv\([\"\'](\w+)[\"\']\)",
            r"process\.env\.(\w+)",
        ]
        skip_vars = {
            "PATH",
            "HOME",
            "USER",
            "LANG",
            "SHELL",
            "TERM",
            "PYTHONPATH",
            "NODE_ENV",
            "DEBUG",
            "PORT",
            "HOST",
        }

        found = set()
        for content in generated_files.values():
            if not content:
                continue
            for pat in patterns:
                for match in re.findall(pat, content):
                    if match not in skip_vars and len(match) > 2:
                        found.add(match)

        return sorted(found)

    def generate_k8s_deployment(self, project_name: str, needs: Dict[str, Any]) -> str:
        """Generate Kubernetes deployment manifest."""
        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {project_name}
  labels:
    app: {project_name}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {project_name}
  template:
    metadata:
      labels:
        app: {project_name}
    spec:
      containers:
        - name: {project_name}
          image: {project_name}:latest
          ports:
            - containerPort: 8000
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: {project_name}
spec:
  selector:
    app: {project_name}
  ports:
    - port: 80
      targetPort: 8000
  type: LoadBalancer
"""
