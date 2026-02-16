"""
Infrastructure Generation Phase

Generates Docker, Kubernetes, Terraform, GitHub Actions workflows,
Dependabot configuration, and optionally sets up GitHub Secrets.
"""

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class InfrastructureGenerationPhase(IAgentPhase):
    """
    Generates infrastructure-as-code and CI/CD configuration:
    - Dockerfile, docker-compose.yml
    - Kubernetes deployment manifests
    - Terraform configurations
    - .github/workflows/deploy.yml
    - .github/dependabot.yml
    - GitHub Secrets setup (via gh secret set)
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
        include_docker = kwargs.get("include_docker", False)

        if not self.context.infra_generator:
            self.context.logger.warning("Infrastructure phase: Skipped (InfraGenerator not available)")
            return generated_files, initial_structure, file_paths

        self.context.logger.info("PHASE INFRA: Starting infrastructure generation...")
        self.context.event_publisher.publish(
            "phase_start", phase="infrastructure", message="Generating infrastructure files"
        )

        # Detect needs
        needs = self.context.infra_generator.detect_infra_needs(
            readme_content, initial_structure, generated_files
        )
        primary_lang = needs["languages"][0] if needs.get("languages") else "python"

        self.context.logger.info(
            f"  Detected: languages={needs['languages']}, "
            f"databases={needs['databases']}, "
            f"web={needs['has_web_server']}, api={needs['has_api']}"
        )

        # Generate Dockerfile
        if include_docker or needs.get("has_web_server") or needs.get("has_api"):
            dockerfile = self.context.infra_generator.generate_dockerfile(primary_lang, project_name)
            generated_files["Dockerfile"] = dockerfile
            self.context.file_manager.write_file(project_root / "Dockerfile", dockerfile)
            self._track_file("Dockerfile", file_paths)

            # Docker Compose
            compose = self.context.infra_generator.generate_docker_compose(needs, project_name)
            generated_files["docker-compose.yml"] = compose
            self.context.file_manager.write_file(project_root / "docker-compose.yml", compose)
            self._track_file("docker-compose.yml", file_paths)

        # Kubernetes manifests
        k8s = self.context.infra_generator.generate_k8s_deployment(project_name, needs)
        (project_root / "k8s").mkdir(parents=True, exist_ok=True)
        generated_files["k8s/deployment.yml"] = k8s
        self.context.file_manager.write_file(project_root / "k8s" / "deployment.yml", k8s)
        self._track_file("k8s/deployment.yml", file_paths)

        # Terraform
        terraform = self.context.infra_generator.generate_terraform_main(needs, cloud="aws")
        (project_root / "terraform").mkdir(parents=True, exist_ok=True)
        generated_files["terraform/main.tf"] = terraform
        self.context.file_manager.write_file(project_root / "terraform" / "main.tf", terraform)
        self._track_file("terraform/main.tf", file_paths)

        # GitHub deploy workflow
        deploy_workflow = self._generate_deploy_workflow(needs, primary_lang, project_name)
        workflows_dir = project_root / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        generated_files[".github/workflows/deploy.yml"] = deploy_workflow
        self.context.file_manager.write_file(workflows_dir / "deploy.yml", deploy_workflow)
        self._track_file(".github/workflows/deploy.yml", file_paths)

        # Dependabot config
        dependabot = self._generate_dependabot_config(needs, generated_files)
        github_dir = project_root / ".github"
        github_dir.mkdir(parents=True, exist_ok=True)
        generated_files[".github/dependabot.yml"] = dependabot
        self.context.file_manager.write_file(github_dir / "dependabot.yml", dependabot)
        self._track_file(".github/dependabot.yml", file_paths)

        # Setup GitHub Secrets (if git_push enabled)
        git_push = kwargs.get("git_push", False)
        git_token = kwargs.get("git_token", "")
        if git_push and git_token:
            await self._setup_github_secrets(project_root, needs, generated_files, git_token)

        self.context.event_publisher.publish(
            "phase_complete",
            phase="infrastructure",
            message="Infrastructure generation complete",
            status="success",
        )

        return generated_files, initial_structure, file_paths

    def _track_file(self, path: str, file_paths: List[str]) -> None:
        """Add file to tracked paths if not already present."""
        if path not in file_paths:
            file_paths.append(path)

    def _generate_deploy_workflow(
        self, needs: Dict[str, Any], language: str, project_name: str
    ) -> str:
        """Generate GitHub Actions deploy workflow based on detected stack."""
        install_step = {
            "python": """      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt""",
            "node": """      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci""",
            "go": """      - uses: actions/setup-go@v5
        with:
          go-version: '1.22'
      - run: go mod download""",
        }.get(language, """      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt""")

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
{install_step}

      - name: Build Docker image
        run: docker build -t {project_name}:${{{{ github.sha }}}} .

      - name: Push to registry
        if: github.ref == 'refs/heads/main'
        run: |
          echo "Deploy step — configure your registry and deployment target here."
          echo "Image: {project_name}:${{{{ github.sha }}}}"
"""

    def _generate_dependabot_config(
        self, needs: Dict[str, Any], generated_files: Dict[str, str]
    ) -> str:
        """Generate .github/dependabot.yml based on detected package ecosystems."""
        ecosystems = []

        # Detect ecosystems from files
        file_names = set(Path(fp).name for fp in generated_files)

        if "requirements.txt" in file_names or "pyproject.toml" in file_names:
            ecosystems.append(("pip", "/"))
        if "package.json" in file_names:
            ecosystems.append(("npm", "/"))
        if "go.mod" in file_names:
            ecosystems.append(("gomod", "/"))
        if "Cargo.toml" in file_names:
            ecosystems.append(("cargo", "/"))
        if "Gemfile" in file_names:
            ecosystems.append(("bundler", "/"))
        if "Dockerfile" in file_names or "docker-compose.yml" in file_names:
            ecosystems.append(("docker", "/"))

        # Always add GitHub Actions
        if any(fp.startswith(".github/workflows/") for fp in generated_files):
            ecosystems.append(("github-actions", "/"))

        if not ecosystems:
            ecosystems.append(("pip", "/"))

        updates = []
        for eco, directory in ecosystems:
            updates.append(f"""  - package-ecosystem: "{eco}"
    directory: "{directory}"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 10""")

        return f"""version: 2
updates:
{chr(10).join(updates)}
"""

    async def _setup_github_secrets(
        self,
        project_root: Path,
        needs: Dict[str, Any],
        generated_files: Dict[str, str],
        token: str,
    ) -> None:
        """Detect required secrets and set them via gh CLI."""
        required_secrets = self._detect_required_secrets(generated_files)

        if not required_secrets:
            return

        self.context.logger.info(f"  Setting up {len(required_secrets)} GitHub secrets...")
        env = {"GH_TOKEN": token}

        for secret_name in required_secrets:
            try:
                # Set placeholder secret — user will need to update with real values
                result = subprocess.run(
                    ["gh", "secret", "set", secret_name, "--body", f"PLACEHOLDER_{secret_name}"],
                    capture_output=True,
                    text=True,
                    cwd=str(project_root),
                    env={**__import__("os").environ, **env},
                    timeout=15,
                )
                if result.returncode == 0:
                    self.context.logger.info(f"    Secret set: {secret_name} (placeholder)")
                else:
                    self.context.logger.debug(f"    Secret set failed: {secret_name}: {result.stderr}")
            except Exception as e:
                self.context.logger.debug(f"    Could not set secret {secret_name}: {e}")

    def _detect_required_secrets(self, generated_files: Dict[str, str]) -> List[str]:
        """Scan code for environment variable references that may need GitHub Secrets."""
        secret_patterns = [
            r'os\.environ\[[\"\'](\w+)[\"\']\]',
            r'os\.getenv\([\"\'](\w+)[\"\']\)',
            r'process\.env\.(\w+)',
            r'\$\{\{\s*secrets\.(\w+)\s*\}\}',
        ]

        found_secrets = set()
        skip_vars = {
            "PATH", "HOME", "USER", "LANG", "SHELL", "TERM",
            "PYTHONPATH", "NODE_ENV", "DEBUG", "PORT", "HOST",
        }

        for content in generated_files.values():
            if not content:
                continue
            for pattern in secret_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if match not in skip_vars and len(match) > 2:
                        found_secrets.add(match)

        return sorted(found_secrets)
