import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class JavaScriptOptimizationPhase(IAgentPhase):
    """
    Phase 5.2: Project-Wide Functional Coherence & Integration.
    Ensures that files correctly reference each other (e.g., HTML script tags, Python imports).
    Fixes 'hallucinated' file names by comparing them against the actual generated file list.
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

        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 5.2: Checking Project Coherence...")
        await self.context.event_publisher.publish(
            "phase_start", phase="5.2", message="Optimizing project functional coherence"
        )

        # 1. Path Reference Validation (Universal)
        # Check for non-existent files mentioned in HTML or imports
        actual_files = set(generated_files.keys())

        # 2. Entry Point Special Check (HTML/Main)
        html_files = {p: c for p, c in generated_files.items() if p.endswith(".html")}
        for path, content in html_files.items():
            generated_files = await self._validate_html_references(
                path, content, actual_files, generated_files, project_root
            )

        # 3. Cross-File functional coherence (Imports/Exports)
        # Focus on JS and Python for now
        code_files = {p: c for p, c in generated_files.items() if p.endswith((".js", ".py", ".ts"))}
        if code_files:
            generated_files = await self._optimize_cross_file_coherence(code_files, generated_files, project_root)

        await self.context.event_publisher.publish(
            "phase_complete", phase="5.2", message="Project coherence optimization complete"
        )
        return generated_files, initial_structure, file_paths

    async def _validate_html_references(
        self, html_path: str, html_content: str, actual_files: set, all_files: Dict[str, str], root: Path
    ) -> Dict[str, str]:
        """Ensures HTML references like <script src="..."> match actual files."""
        self.context.logger.info(f"  Checking HTML references in {html_path}...")

        # Detect <script src="..."> and <link href="...">
        refs = re.findall(r'<(?:script|link)[^>]*(?:src|href)=["\']([^"\']+)["\']', html_content)

        actual_files_clean = {f.lstrip("./") for f in actual_files}

        mismatches = []
        for ref in refs:
            # Skip absolute or external links
            if ref.startswith(("http", "//", "/")):
                continue

            # Normalise ref to match actual_files_clean
            # Try 1: Relative to HTML (e.g. HTML at src/index.html, ref 'app.js' -> 'src/app.js')
            ref_rel = (Path(html_path).parent / ref).as_posix().lstrip("./")
            # Try 2: Direct match (e.g. ref 'src/app.js')
            ref_direct = ref.lstrip("./")

            if ref_rel not in actual_files_clean and ref_direct not in actual_files_clean:
                mismatches.append({"original": ref, "rel_path": ref_rel})

        if mismatches:
            self.context.logger.warning(
                f"    Found {len(mismatches)} dead references in {html_path}: {[m['original'] for m in mismatches]}"
            )

            # Ask LLM to fix the HTML using the REAL file list
            try:
                available_files = "\n".join(f"- {f}" for f in actual_files)
                prompt = (
                    f"The file '{html_path}' contains non-existent references: {[m['original'] for m in mismatches]}\n"
                    f"ACTUAL FILES CREATED IN PROJECT:\n{available_files}\n\n"
                    "Fix the HTML content so all <script> and <link> tags use the CORRECT paths from the actual files list. "
                    "Output the COMPLETE corrected HTML inside <code_created> tags."
                )

                res = self.context.llm_manager.get_client("coder").chat(
                    messages=[{"role": "user", "content": prompt}], options_override={"temperature": 0.1}
                )

                # Handle both tuple (response_data, usage) and direct response_data
                if isinstance(res, tuple):
                    response_data, _ = res
                else:
                    response_data = res

                new_content = self.context.response_parser.extract_code(response_data.get("content", ""), html_path)
                if new_content and len(new_content) > len(html_content) * 0.5:
                    all_files[html_path] = new_content
                    self.context.file_manager.write_file(root / html_path, new_content)
                    self.context.logger.info(f"    ✓ {html_path} updated with correct file references.")
            except Exception as e:
                self.context.logger.error(f"    Failed to fix HTML references: {e}")

        return all_files

    async def _optimize_cross_file_coherence(
        self, code_files: Dict[str, str], all_files: Dict[str, str], root: Path
    ) -> Dict[str, str]:
        """Ensures imports and function calls between files are consistent."""
        self.context.logger.info("  Checking cross-file functional coherence...")

        # Build a summary of what's available (exports from logic plan)
        api_summary = []
        logic_plan = getattr(self.context, "logic_plan", {})
        for path, plan in logic_plan.items():
            exports = plan.get("exports", [])
            if exports:
                api_summary.append(f"FILE: {path}\nEXPORTS: {', '.join(exports)}")

        if not api_summary:
            return all_files

        api_text = "\n\n".join(api_summary)

        is_nano = bool(self.context._is_small_model())

        # For models nano, we review more files or all since they are micro-tasks
        if is_nano:
            targets = list(code_files.keys())
        else:
            targets = [p for p, c in code_files.items() if len(c.split("\n")) > 20 or "main" in p or "app" in p]

        for idx, file_path in enumerate(targets, 1):
            content = code_files[file_path]
            try:
                prompt = (
                    f"PROJECT API CONTRACT:\n{api_text}\n\n"
                    f"FILE TO REVIEW: {file_path}\n"
                    f"CONTENT:\n{content}\n\n"
                    "Check if this file uses correct variable/function names and import paths as defined in the API contract. "
                    "If there are mismatches, fix them. Output the COMPLETE corrected code inside <code_created> tags. "
                    "If it's already correct, reply with 'ALREADY_COHERENT'."
                )

                res = self.context.llm_manager.get_client("coder").chat(
                    messages=[{"role": "user", "content": prompt}], options_override={"temperature": 0.0}
                )

                # Handle both tuple (response_data, usage) and direct response_data
                if isinstance(res, tuple):
                    response_data, _ = res
                else:
                    response_data = res

                raw_res = response_data.get("content", "")
                if "ALREADY_COHERENT" in raw_res:
                    continue

                corrected_code = self.context.response_parser.extract_code(raw_res, file_path)
                if corrected_code and len(corrected_code) > 20:
                    self.context.logger.info(f"    Applied cross-file fix to {file_path}")
                    all_files[file_path] = corrected_code.strip()
                    self.context.file_manager.write_file(root / file_path, corrected_code.strip())
            except Exception as e:
                self.context.logger.error(f"    Failed coherence check for {file_path}: {e}")

        return all_files
