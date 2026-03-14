"""Dependency Precheck Phase — early conflict detection before code generation.

Runs after all planning phases and before EmptyFileScaffolding. Collects the
declared dependencies from ``context.logic_plan`` import lists and any existing
manifest files (``requirements.txt``, ``package.json``), then asks the LLM to
check for:
  • Version conflicts (e.g. incompatible peer dependencies)
  • Deprecated packages
  • Runtime version incompatibilities (Node LTS, Python range)
  • Circular/duplicated dependency declarations

If conflicts are found the phase auto-generates corrected manifest content and
writes ``dependency_precheck_report.json``.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase

_MANIFEST_FILES = (
    "requirements.txt",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "pyproject.toml",
    "setup.cfg",
)


class DependencyPrecheckPhase(BasePhase):
    """Phase 2.95: Predictive dependency conflict detection."""

    phase_id = "2.95"
    phase_label = "Dependency Conflict Pre-Check"

    def run(
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
        declared_deps = self._collect_declared_deps(generated_files, file_paths, project_root)

        if not declared_deps:
            self.context.logger.info("[DepPrecheck] No dependency declarations found — skipping.")
            return generated_files, initial_structure, file_paths

        tech = getattr(self.context, "tech_stack_info", None)
        runtime_info = {
            "primary_language": getattr(tech, "primary_language", "") if tech else "",
            "runtime_version": getattr(tech, "runtime_version", "") if tech else "",
            "framework": getattr(tech, "framework", "") if tech else "",
        }

        self.context.logger.info(f"[DepPrecheck] Checking {len(declared_deps)} dependency declaration(s)...")

        report = self._check_conflicts(declared_deps, runtime_info, project_description)

        conflicts: List[Dict] = [c for c in report.get("conflicts", []) if c.get("severity") in ("HIGH", "MEDIUM")]

        if conflicts:
            self.context.logger.warning(f"[DepPrecheck] {len(conflicts)} conflict(s) detected — attempting auto-fix.")
            generated_files = self._auto_fix_manifests(
                conflicts, generated_files, file_paths, project_root, runtime_info
            )
        else:
            self.context.logger.info("[DepPrecheck] No significant conflicts detected.")

        report_json = json.dumps(report, indent=2)
        self._write_file(
            project_root,
            "dependency_precheck_report.json",
            report_json,
            generated_files,
            file_paths,
        )
        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_declared_deps(
        self,
        generated_files: Dict[str, str],
        file_paths: List[str],
        project_root: Path,
    ) -> Dict[str, str]:
        """Return {manifest_filename: raw_content} for all found manifests."""
        result: Dict[str, str] = {}

        # 1. From already-generated files
        for fp in file_paths:
            name = Path(fp).name
            if name in _MANIFEST_FILES and fp in generated_files:
                result[name] = generated_files[fp]

        # 2. From disk (existing project)
        for manifest in _MANIFEST_FILES:
            if manifest not in result:
                disk_path = project_root / manifest
                if disk_path.exists():
                    try:
                        result[manifest] = disk_path.read_text(encoding="utf-8")
                    except Exception:
                        pass

        # 3. Inferred from logic_plan imports
        all_imports: List[str] = []
        for plan in self.context.logic_plan.values():
            all_imports.extend(plan.get("imports", []) or [])
        if all_imports and not result:
            result["__inferred_imports__"] = "\n".join(sorted(set(all_imports)))

        return result

    def _check_conflicts(
        self,
        declared_deps: Dict[str, str],
        runtime_info: Dict[str, str],
        project_description: str,
    ) -> Dict[str, Any]:
        """Ask LLM to detect conflicts in the collected manifests."""
        deps_summary = "\n\n".join(f"### {name}\n```\n{content[:1500]}\n```" for name, content in declared_deps.items())
        system_prompt = (
            "You are a senior DevOps engineer specializing in dependency management. "
            "Analyse the dependency manifests below and detect: "
            "version conflicts, deprecated packages, peer-dependency mismatches, "
            "and runtime version incompatibilities. "
            'Return JSON: {"conflicts": [{"severity": "HIGH"|"MEDIUM"|"LOW", '
            '"package": "...", "description": "...", "fix_suggestion": "..."}]}. '
            "Return an EMPTY conflicts array if no issues are found. Output JSON only."
        )
        user_prompt = (
            f"## Runtime: {json.dumps(runtime_info)}\n"
            f"## Project: {project_description[:500]}\n\n"
            f"## Dependency Manifests:\n{deps_summary}"
        )

        default: Dict[str, Any] = {"conflicts": []}
        try:
            response_data, _ = self.context.llm_manager.get_client("planner").chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options_override={"temperature": 0.1},
            )
            parsed = self.context.response_parser.extract_json(response_data.get("content", ""))
            if isinstance(parsed, dict):
                return parsed
        except Exception as exc:
            self.context.logger.warning(f"[DepPrecheck] LLM check failed: {exc}")
        return default

    def _auto_fix_manifests(
        self,
        conflicts: List[Dict[str, Any]],
        generated_files: Dict[str, str],
        file_paths: List[str],
        project_root: Path,
        runtime_info: Dict[str, str],
    ) -> Dict[str, str]:
        """Ask the LLM to produce corrected manifest content."""
        conflicts_json = json.dumps(conflicts, indent=2)
        system_prompt = (
            "You are a senior DevOps engineer. Given the list of dependency conflicts "
            "and the existing manifests, produce corrected manifest content that resolves "
            "all conflicts. Return JSON: "
            '{"fixed_manifests": {"<filename>": "<corrected content>"}}. '
            "Only include manifests that need changes. Output JSON only."
        )
        existing = {name: content for name, content in generated_files.items() if Path(name).name in _MANIFEST_FILES}
        user_prompt = (
            f"## Conflicts:\n{conflicts_json}\n\n"
            f"## Runtime: {json.dumps(runtime_info)}\n\n"
            f"## Existing manifests:\n{json.dumps(existing, indent=2)[:3000]}"
        )

        try:
            response_data, _ = self.context.llm_manager.get_client("planner").chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options_override={"temperature": 0.1},
            )
            parsed = self.context.response_parser.extract_json(response_data.get("content", ""))
            fixed: Dict[str, str] = (parsed or {}).get("fixed_manifests", {})
            for filename, content in fixed.items():
                self._write_file(project_root, filename, content, generated_files, file_paths)
                self.context.logger.info(f"  ✓ Auto-fixed manifest: {filename}")
        except Exception as exc:
            self.context.logger.warning(f"[DepPrecheck] Auto-fix failed: {exc}")

        return generated_files
