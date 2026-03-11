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

        is_nano = bool(self.context._is_small_model())
        stub_count = 0
        for source_path, plan in logic_plan.items():
            exports: List[str] = plan.get("exports", [])
            if not exports:
                continue

            # 1. Generate external stub file (.pyi, .d.ts)
            stub_path = self._stub_path_for(source_path)
            if stub_path:
                stub_content = self._generate_stub(source_path, exports, plan)
                if stub_content:
                    self._write_stub_file(project_root, stub_path, stub_content, generated_files, file_paths)
                    stub_count += 1

            # 2. Skeleton-First (F31): Write stub directly into the source file for nano models
            if is_nano:
                source_stub = self._generate_source_skeleton(source_path, exports, plan)
                if source_stub:
                    # Write directly to the source file (e.g., src/main.py)
                    self._write_stub_file(project_root, source_path, source_stub, generated_files, file_paths)
                    self.context.logger.info(f"  [Nano] Generated source skeleton: {source_path}")

        self.context.logger.info(f"[InterfaceScaffolding] {stub_count} external stub files generated")

        # Fix 2: Extract or Generate DOM contracts for coherence
        is_web = any(p.endswith(".html") for p in file_paths)
        if is_web:
            await self._ensure_dom_contract(logic_plan, project_root, generated_files, is_nano)

        await self.context.event_publisher.publish(
            "phase_complete", phase=self.phase_id, message=f"Generated {stub_count} skeletons"
        )
        return generated_files, initial_structure, file_paths

    async def _ensure_dom_contract(self, logic_plan, project_root, generated_files, is_nano):
        """Ensure a DOM contract exists, generating one via LLM if necessary for nano models."""
        self._extract_dom_contracts(logic_plan, project_root, generated_files)

        # If nano and no IDs found yet, proactively define them to avoid mismatch
        if is_nano and not getattr(self.context, "dom_contracts", {}):
            self.context.logger.info("  [Nano] No DOM IDs found in plan. Defining UI Contract via NanoPlanner...")
            try:
                # We reuse the nano_planner role but with a UI contract focus
                prompt = (
                    f"Define 5-8 essential HTML element IDs for this project: {self.context.project_description}\n"
                    "Output ONLY a JSON map of element_id to its purpose (string). "
                    'Example: {"game-board": "8x8 grid container", "status": "turn indicator"}'
                )

                client = self.context.llm_manager.get_client("nano_planner")
                res, _ = client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    options_override={"temperature": 0.1, "num_predict": 256},
                )
                contract = self.context.response_parser.extract_json(res.get("content", ""))
                if isinstance(contract, dict):
                    # Store as a shared contract for the first HTML file found
                    html_file = next((p for p in logic_plan.keys() if p.endswith(".html")), "index.html")
                    self.context.dom_contracts = {html_file: list(contract.keys())}
                    self.context.logger.info(f"  [Nano] Defined UI Contract with {len(contract)} elements.")
            except Exception as e:
                self.context.logger.warning(f"  [Nano] Failed to define UI contract: {e}")

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

    def _write_stub_file(
        self, project_root: Path, rel_path: str, content: str, generated_files: Dict, file_paths: List
    ):
        """Helper to write a stub/skeleton file and update context."""
        full_path = project_root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            full_path.write_text(content, encoding="utf-8")
            generated_files[rel_path] = content
            if rel_path not in file_paths:
                file_paths.append(rel_path)
        except OSError as exc:
            self.context.logger.warning(f"  Could not write file {rel_path}: {exc}")

    # ------------------------------------------------------------------
    # Source-code skeleton generation (Skeleton-First F31)
    # ------------------------------------------------------------------

    def _generate_source_skeleton(self, source_path: str, exports: List[str], plan: Dict[str, Any]) -> str:
        """Build a runnable skeleton directly in the source file language."""
        ext = Path(source_path).suffix.lower()
        if ext == ".py":
            return self._python_source_skeleton(exports, plan)
        if ext in (".js", ".ts", ".jsx", ".tsx"):
            return self._javascript_source_skeleton(exports, plan)
        return ""

    @staticmethod
    def _python_source_skeleton(exports: List[str], plan: Dict[str, Any]) -> str:
        """Generate a .py skeleton with pass-stubs."""
        lines = [
            f'"""{plan.get("purpose", "Auto-generated module")}"""',
            "",
        ]
        # Basic imports from plan
        for imp in plan.get("imports", []):
            lines.append(imp)
        if plan.get("imports"):
            lines.append("")

        for export in exports:
            name = export.strip()
            if not name:
                continue
            if name[0].isupper():
                lines.append(f"class {name}:")
                lines.append('    """Implementation placeholder."""')
                lines.append("    pass")
            else:
                lines.append(f"def {name}():")
                lines.append('    """Implementation placeholder."""')
                lines.append("    pass")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _javascript_source_skeleton(exports: List[str], plan: Dict[str, Any]) -> str:
        """Generate a .js/.ts skeleton with empty-body stubs."""
        lines = [
            f"/** {plan.get('purpose', 'Auto-generated module')} */",
            "",
        ]
        # Imports
        for imp in plan.get("imports", []):
            lines.append(imp)
        if plan.get("imports"):
            lines.append("")

        for export in exports:
            name = export.strip()
            if not name:
                continue
            if name[0].isupper():
                lines.append(f"export class {name} {{")
                lines.append("  // Implementation placeholder")
                lines.append("}")
            else:
                lines.append(f"export function {name}() {{")
                lines.append("  // Implementation placeholder")
                lines.append("}")
            lines.append("")

        return "\n".join(lines)

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
