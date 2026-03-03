import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class VerificationPhase(IAgentPhase):
    """
    Phase 5.5: Performs a verification loop to validate and fix generated files.
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
        generated_files: Dict[str, str],  # This will be verified and potentially fixed
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        file_paths = kwargs.get("file_paths", [])  # Get from kwargs or assume context has it

        self.context.logger.info("PHASE 5.5: Verification loop...")
        await self.context.event_publisher.publish("phase_start", phase="5.5", message="Starting verification loop")

        generated_files = await self.context.file_completeness_checker.verify_and_fix(
            generated_files, readme_content[:1000]
        )

        for rel_path, content in generated_files.items():
            if content:
                self.context.file_manager.write_file(project_root / rel_path, content)

        # Fix 2: DOM contract consistency check (warning only — non-blocking)
        self._check_dom_id_consistency(generated_files)

        await self.context.event_publisher.publish("phase_complete", phase="5.5", message="Verification loop complete")
        self.context.logger.info("PHASE 5.5 complete.")

        return generated_files, initial_structure, file_paths

    def _check_dom_id_consistency(self, generated_files: Dict[str, str]) -> None:
        """Warn when JS files reference IDs that are not declared in any HTML file.

        This is a non-blocking check — it only emits warnings so the pipeline
        never stalls on a false positive.  Useful as a quality signal for the
        SeniorReviewPhase.
        """
        html_files = {p: c for p, c in generated_files.items() if p.endswith(".html")}
        js_files = {p: c for p, c in generated_files.items() if p.endswith((".js", ".ts", ".jsx", ".tsx"))}
        if not html_files or not js_files:
            return

        _ID_DECL = re.compile(r'id=["\']([^"\']+)["\']')
        _ID_REF = re.compile(r'(?:getElementById|querySelector(?:All)?)\(["\']#?([^"\'()]+)["\']')

        declared_ids: Set[str] = set()
        for content in html_files.values():
            declared_ids.update(_ID_DECL.findall(content))

        unmatched_refs = []
        for js_path, js_content in js_files.items():
            for ref in _ID_REF.findall(js_content):
                ref_clean = ref.lstrip("#")
                if ref_clean and ref_clean not in declared_ids:
                    unmatched_refs.append(f"{js_path}: #{ref_clean}")

        if unmatched_refs:
            self.context.logger.warning(
                f"[Fix2/DOMContract] {len(unmatched_refs)} JS element reference(s) not found in any HTML id= attribute:"
            )
            for ref in unmatched_refs[:10]:  # limit log spam
                self.context.logger.warning(f"  - {ref}")
        else:
            self.context.logger.info(
                f"[Fix2/DOMContract] DOM contract OK — {len(declared_ids)} IDs declared, all JS references matched."
            )
