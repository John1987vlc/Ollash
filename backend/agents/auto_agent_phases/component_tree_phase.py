"""Component Tree Phase — frontend component hierarchy blueprinting.

When TechStackDetector or the module system detects a React / Vue / Angular /
Svelte project, this phase generates:
  • A hierarchical component tree (parent → children → props)
  • A state management plan (Redux slices / Pinia stores / Context providers)
  • Component responsibilities and shared state contracts

The result is written to ``component_tree.md`` and stored in
``PhaseContext.component_tree`` for downstream phases to consume.

Only active for slim and full tiers on frontend projects.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase

_FRONTEND_FRAMEWORKS = frozenset({"react", "next", "vue", "nuxt", "angular", "svelte", "solid", "preact", "qwik"})


class ComponentTreePhase(BasePhase):
    """Phase 2.7: Frontend component hierarchy blueprinting."""

    phase_id = "2.7"
    phase_label = "Component Tree Blueprinting"

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
        framework = self._detect_frontend_framework()
        if not framework:
            self.context.logger.info("[ComponentTree] No frontend framework detected — skipping.")
            return generated_files, initial_structure, file_paths

        self.context.logger.info(f"[ComponentTree] {framework} project detected — generating component tree.")

        tree_data = await self._generate_tree(
            project_description, project_name, framework, initial_structure, file_paths
        )

        if not tree_data:
            self.context.logger.warning("[ComponentTree] Generation failed — skipping.")
            return generated_files, initial_structure, file_paths

        self.context.component_tree = tree_data
        md_content = self._render_markdown(tree_data, project_name, framework)

        self._write_file(project_root, "component_tree.md", md_content, generated_files, file_paths)

        self.context.logger.info("[ComponentTree] component_tree.md written successfully.")
        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_frontend_framework(self) -> Optional[str]:
        """Return the detected frontend framework name or None."""
        tech = getattr(self.context, "tech_stack_info", None)
        if tech is not None:
            fw = (getattr(tech, "framework", "") or "").lower()
            for name in _FRONTEND_FRAMEWORKS:
                if name in fw:
                    return name

        # Fallback: check module_system + file extensions
        ms = getattr(self.context, "module_system", "")
        if ms == "esm":
            ptype = getattr(self.context, "project_type_info", None)
            if ptype is not None and ptype.project_type in ("frontend", "fullstack"):
                return "react"  # generic ESM frontend

        return None

    async def _generate_tree(
        self,
        project_description: str,
        project_name: str,
        framework: str,
        initial_structure: Dict[str, Any],
        file_paths: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Ask the LLM to produce the component hierarchy as JSON."""
        # Collect UI-related file hints
        ui_files = [
            fp for fp in file_paths if any(fp.endswith(ext) for ext in (".jsx", ".tsx", ".vue", ".svelte", ".html"))
        ][:20]

        system_prompt = (
            f"You are a senior {framework} architect. "
            "Design the component tree for the application described below. "
            "Return a JSON object with these keys: "
            '{"components": [{"name": "str", "parent": "str|null", "props": [...], '
            '"state": [...], "responsibility": "str"}], '
            '"state_management": {"type": "Redux|Pinia|Context|Zustand|Signals", '
            '"stores": [{"name": "str", "state_keys": [...]}]}}. '
            "Output ONLY the JSON, no prose."
        )
        user_prompt = (
            f"## Project: {project_name}\n"
            f"## Description: {project_description[:1500]}\n"
            f"## UI files detected: {json.dumps(ui_files)}\n\n"
            "Generate the component tree JSON:"
        )

        try:
            response_data, _ = self.context.llm_manager.get_client("planner").chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options_override={"temperature": 0.2},
            )
            parsed = self.context.response_parser.extract_json(response_data.get("content", ""))
            if isinstance(parsed, dict) and "components" in parsed:
                return parsed
        except Exception as exc:
            self.context.logger.warning(f"[ComponentTree] LLM call failed: {exc}")
        return None

    @staticmethod
    def _render_markdown(tree: Dict[str, Any], project_name: str, framework: str) -> str:
        """Convert the tree dict to a human-readable Markdown document."""
        lines = [
            f"# Component Tree — {project_name}",
            "",
            f"> Framework: **{framework.capitalize()}**",
            "",
            "## Component Hierarchy",
            "",
        ]

        components: List[Dict] = tree.get("components", [])

        # Build a simple parent → children map
        children_map: Dict[str, List[str]] = {}
        for comp in components:
            parent = comp.get("parent") or "ROOT"
            children_map.setdefault(parent, []).append(comp.get("name", "?"))

        def render_node(name: str, indent: int = 0) -> None:
            prefix = "  " * indent + ("- " if indent else "")
            lines.append(f"{prefix}**{name}**")
            for child in children_map.get(name, []):
                render_node(child, indent + 1)

        roots = [c.get("name", "?") for c in components if not c.get("parent")]
        for root in roots:
            render_node(root)

        lines += ["", "## Component Details", ""]
        for comp in components:
            name = comp.get("name", "?")
            props = comp.get("props", [])
            state = comp.get("state", [])
            resp = comp.get("responsibility", "")
            lines += [
                f"### `{name}`",
                f"- **Responsibility**: {resp}",
                f"- **Props**: {', '.join(props) if props else '—'}",
                f"- **Local state**: {', '.join(state) if state else '—'}",
                "",
            ]

        sm = tree.get("state_management", {})
        if sm:
            lines += [
                "## State Management",
                "",
                f"**Type**: {sm.get('type', '?')}",
                "",
                "| Store | State Keys |",
                "|-------|-----------|",
            ]
            for store in sm.get("stores", []):
                keys = ", ".join(store.get("state_keys", []))
                lines.append(f"| {store.get('name', '?')} | {keys} |")

        return "\n".join(lines) + "\n"
