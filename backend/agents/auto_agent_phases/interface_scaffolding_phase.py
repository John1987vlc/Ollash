"""Interface Scaffolding Phase — generates .pyi and .d.ts stub files deterministically.

Runs between LogicPlanningPhase and FileContentGenerationPhase.
Creates stub files from logic_plan exports WITHOUT any LLM calls, so that
subsequent RAG context selection includes these contracts and the LLM only
needs to "fill in the blanks" when generating actual implementations.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase


class InterfaceScaffoldingPhase(BasePhase):
    """Generate stub files (.pyi / .d.ts) from logic_plan exports.

    Benefits for small (<=4B) models:
    - Reduces structural hallucinations: the contract is already defined.
    - Provides explicit function signatures as RAG context.
    - Zero LLM calls — fully deterministic and instant.
    """

    phase_id: str = "interface_scaffolding"
    phase_label: str = "Interface Skeleton Generation"
    category: str = "generation"
    REQUIRED_TOOLS: List[str] = []

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
        await self.context.event_publisher.publish(
            "phase_start", phase=self.phase_id, message="Generating interface skeletons"
        )

        logic_plan = getattr(self.context, "logic_plan", {})
        if not logic_plan:
            self.context.logger.info("[InterfaceScaffolding] No logic plan found — skipping")
            await self.context.event_publisher.publish(
                "phase_complete", phase=self.phase_id, message="Skipped (no logic plan)"
            )
            return generated_files, initial_structure, file_paths

        stub_count = 0
        for source_path, plan in logic_plan.items():
            stub_path = self._stub_path_for(source_path)
            if stub_path is None:
                continue
            exports: List[str] = plan.get("exports", [])
            if not exports:
                continue
            stub_content = self._generate_stub(source_path, exports, plan)
            if stub_content:
                full_stub = project_root / stub_path
                full_stub.parent.mkdir(parents=True, exist_ok=True)
                try:
                    full_stub.write_text(stub_content, encoding="utf-8")
                except OSError as exc:
                    self.context.logger.warning(f"  Could not write stub {stub_path}: {exc}")
                    continue
                generated_files[stub_path] = stub_content
                if stub_path not in file_paths:
                    file_paths = list(file_paths) + [stub_path]
                stub_count += 1
                self.context.logger.info(f"  Generated stub: {stub_path}")

        self.context.logger.info(f"[InterfaceScaffolding] {stub_count} stub files generated")

        # Fix 2: Extract DOM contracts from HTML-related logic plan entries
        self._extract_dom_contracts(logic_plan, project_root, generated_files)

        await self.context.event_publisher.publish(
            "phase_complete", phase=self.phase_id, message=f"Generated {stub_count} skeletons"
        )
        return generated_files, initial_structure, file_paths

    def _extract_dom_contracts(
        self,
        logic_plan: Dict[str, Any],
        project_root: Path,
        generated_files: Dict[str, str],
    ) -> None:
        """Scan logic_plan for HTML files and extract element IDs as a shared DOM contract.

        Results are stored in ``context.dom_contracts`` as ``{html_path: [id, ...]}``.
        A ``DOM_CONTRACTS.json`` file is also written to the project root for traceability.

        Scans:
        1. Logic plan ``main_logic`` and ``purpose`` text for ``id="..."`` patterns.
        2. Any already-generated ``.html`` file content in ``generated_files``.
        """
        _ID_PATTERN = re.compile(r'id=["\']([^"\']+)["\']')
        contracts: Dict[str, List[str]] = {}

        for file_path, plan in logic_plan.items():
            if not file_path.endswith(".html"):
                continue
            ids_found: List[str] = []
            # Scan plan text fields for id="..." mentions
            for field in ("purpose", "main_logic", "exports"):
                value = plan.get(field, "")
                text = " ".join(value) if isinstance(value, list) else str(value)
                ids_found.extend(_ID_PATTERN.findall(text))
            # Also scan already-generated HTML content (if any)
            html_content = generated_files.get(file_path, "")
            if html_content:
                ids_found.extend(_ID_PATTERN.findall(html_content))

            if ids_found:
                contracts[file_path] = list(dict.fromkeys(ids_found))  # deduplicate, preserve order

        if contracts:
            self.context.dom_contracts = contracts
            self.context.logger.info(
                "[InterfaceScaffolding] DOM contracts extracted: "
                + ", ".join(f"{k}: {len(v)} IDs" for k, v in contracts.items())
            )
            try:
                contracts_path = project_root / "DOM_CONTRACTS.json"
                contracts_path.parent.mkdir(parents=True, exist_ok=True)
                contracts_path.write_text(json.dumps(contracts, indent=2), encoding="utf-8")
            except OSError as exc:
                self.context.logger.warning(f"  Could not write DOM_CONTRACTS.json: {exc}")

    # ------------------------------------------------------------------
    # Stub path resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _stub_path_for(source_path: str) -> Optional[str]:
        """Return the stub file path for *source_path*, or None if unsupported.

        Always uses forward slashes so the result is consistent across OS.
        """
        p = Path(source_path)
        if p.suffix == ".py":
            return p.with_suffix(".pyi").as_posix()
        if p.suffix in (".ts", ".tsx"):
            return p.with_suffix(".d.ts").as_posix()
        return None

    def _generate_stub(self, source_path: str, exports: List[str], plan: Dict[str, Any]) -> str:
        """Deterministically build a stub from the exports list."""
        ext = Path(source_path).suffix
        if ext == ".py":
            return self._python_stub(exports, plan)
        if ext in (".ts", ".tsx"):
            return self._typescript_stub(exports, plan)
        return ""

    # ------------------------------------------------------------------
    # Language-specific stub generators
    # ------------------------------------------------------------------

    @staticmethod
    def _python_stub(exports: List[str], plan: Dict[str, Any]) -> str:
        """Generate a .pyi stub for a Python module."""
        lines = [
            "# Auto-generated stub file — DO NOT EDIT",
            "# Generated by InterfaceScaffoldingPhase",
            "from typing import Any, Optional, List, Dict",
            "",
        ]
        for imp in plan.get("imports", [])[:5]:
            lines.append(f"# import hint: {imp}")
        if plan.get("imports"):
            lines.append("")

        for export in exports:
            name = export.strip()
            if not name:
                continue
            if name[0].isupper():
                lines.append(f"class {name}:")
                lines.append("    ...")
            else:
                lines.append(f"def {name}(*args: Any, **kwargs: Any) -> Any: ...")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _typescript_stub(exports: List[str], plan: Dict[str, Any]) -> str:
        """Generate a .d.ts declaration file for a TypeScript module."""
        lines = [
            "// Auto-generated type declaration — DO NOT EDIT",
            "// Generated by InterfaceScaffoldingPhase",
            "",
        ]
        for export in exports:
            name = export.strip()
            if not name:
                continue
            if name[0].isupper():
                lines.append(f"export declare class {name} {{")
                lines.append("  [key: string]: any;")
                lines.append("}")
            else:
                lines.append(f"export declare function {name}(...args: any[]): any;")
            lines.append("")
        return "\n".join(lines)
