"""API Contract Phase — generates an OpenAPI 3.0 spec before code generation.

For backend and full-stack projects (detected via TechStackDetector /
ProjectTypeDetector) this phase produces an ``openapi.yaml`` file that acts as
the single source of truth for routes, request/response schemas, and HTTP verbs.
Subsequent phases (especially FileContentGenerationPhase) can read
``PhaseContext.api_contract`` to stay in sync with the agreed contract.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml  # PyYAML — already a transitive dependency via several packages

from backend.agents.auto_agent_phases.base_phase import BasePhase

# Frameworks that indicate a backend or full-stack project
_BACKEND_FRAMEWORKS = frozenset(
    {
        "flask",
        "django",
        "fastapi",
        "express",
        "nestjs",
        "next",
        "nuxt",
        "spring",
        "laravel",
        "rails",
        "gin",
        "fiber",
        "actix",
        "hapi",
        "koa",
        "sanic",
        "litestar",
        "starlette",
    }
)

_BACKEND_PROJECT_TYPES = frozenset({"backend", "fullstack", "api", "microservice", "web"})


class ApiContractPhase(BasePhase):
    """Phase 2.8: API-First contract generation.

    Skipped automatically for:
    - Pure frontend / CLI / library / data-science projects
    - nano model tier (too expensive)

    On success writes ``openapi.yaml`` to project root and stores the raw YAML
    string in ``PhaseContext.api_contract``.
    """

    phase_id = "2.8"
    phase_label = "API Contract Generation"
    _MAX_RETRIES = 3

    async def run(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],
        file_paths: List[str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        if not self._is_backend_project():
            self.context.logger.info(
                "[ApiContract] Not a backend/fullstack project — skipping."
            )
            return generated_files, initial_structure, file_paths

        self.context.logger.info(
            "[ApiContract] Generating OpenAPI 3.0 contract..."
        )

        openapi_yaml = await self._generate_contract(
            project_description, project_name, initial_structure
        )

        if not openapi_yaml:
            self.context.logger.warning(
                "[ApiContract] Failed to generate valid OpenAPI spec — skipping."
            )
            return generated_files, initial_structure, file_paths

        # Persist to disk
        self._write_file(project_root, "openapi.yaml", openapi_yaml, generated_files, file_paths)

        # Store in context for downstream phases
        self.context.api_contract = openapi_yaml
        self.context.api_endpoints = self._extract_endpoints(openapi_yaml)

        self.context.logger.info(
            f"[ApiContract] openapi.yaml written ({len(self.context.api_endpoints)} endpoint(s) detected)."
        )
        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_backend_project(self) -> bool:
        """Return True if the project warrants an API contract."""
        tech = getattr(self.context, "tech_stack_info", None)
        if tech is not None:
            framework = (getattr(tech, "framework", "") or "").lower()
            if any(f in framework for f in _BACKEND_FRAMEWORKS):
                return True

        ptype = getattr(self.context, "project_type_info", None)
        if ptype is not None:
            if ptype.project_type.lower() in _BACKEND_PROJECT_TYPES:
                return True

        return False

    async def _generate_contract(
        self,
        project_description: str,
        project_name: str,
        initial_structure: Dict[str, Any],
    ) -> str:
        """Ask the LLM for a valid OpenAPI 3.0 YAML. Retries up to 3×."""
        logic_plan_summary = json.dumps(
            {k: {"purpose": v.get("purpose", ""), "exports": v.get("exports", [])}
             for k, v in list(self.context.logic_plan.items())[:20]},
            indent=2,
        )

        system_prompt = (
            "You are a senior API architect. Generate a complete, valid OpenAPI 3.0.3 "
            "YAML specification for the project described below. "
            "Include: openapi, info, servers, paths (with HTTP verbs, summaries, "
            "requestBody, responses), and components/schemas. "
            "Output ONLY valid YAML — no prose, no markdown fences."
        )

        for attempt in range(1, self._MAX_RETRIES + 1):
            user_prompt = (
                f"## Project: {project_name}\n"
                f"## Description:\n{project_description[:3000]}\n\n"
                f"## Implementation Plan (excerpt):\n{logic_plan_summary[:2000]}\n\n"
                "Generate the openapi.yaml content:"
            )
            try:
                response_data, _ = self.context.llm_manager.get_client("planner").chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    options_override={"temperature": 0.2},
                )
                raw = response_data.get("content", "").strip()
                # Strip markdown fences if present
                if raw.startswith("```"):
                    lines = raw.splitlines()
                    raw = "\n".join(
                        line for line in lines if not line.startswith("```")
                    ).strip()

                # Validate YAML
                parsed = yaml.safe_load(raw)
                if isinstance(parsed, dict) and "openapi" in parsed and "paths" in parsed:
                    return raw
                self.context.logger.warning(
                    f"[ApiContract] Attempt {attempt}: missing required OAS fields."
                )
            except Exception as exc:
                self.context.logger.warning(
                    f"[ApiContract] Attempt {attempt} failed: {exc}"
                )

        return ""

    @staticmethod
    def _extract_endpoints(openapi_yaml: str) -> List[Dict[str, Any]]:
        """Parse the YAML and return a flat list of {path, method, summary} dicts."""
        try:
            spec = yaml.safe_load(openapi_yaml)
            endpoints: List[Dict[str, Any]] = []
            for path, methods in (spec.get("paths") or {}).items():
                for method, operation in methods.items():
                    if method.lower() in {"get", "post", "put", "patch", "delete", "options"}:
                        endpoints.append(
                            {
                                "path": path,
                                "method": method.upper(),
                                "summary": (operation or {}).get("summary", ""),
                            }
                        )
            return endpoints
        except Exception:
            return []
