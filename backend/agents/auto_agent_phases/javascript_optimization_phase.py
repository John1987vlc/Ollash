import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class JavaScriptOptimizationPhase(IAgentPhase):
    """
    Phase 5.2: Specialized Semantic Optimization for JavaScript projects.
    Executes after file generation but before final verification.
    Focuses on cross-file consistency and HTML-JS integration.
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

        # Only run if there are significant JS files
        js_files = {path: content for path, content in generated_files.items() if path.endswith('.js')}
        if not js_files:
            return generated_files, initial_structure, file_paths

        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 5.2: Optimizing JavaScript Integration...")
        self.context.event_publisher.publish("phase_start", phase="5.2", message="Optimizing JS semantic coherence")

        # 1. HTML-JS Integration Check
        html_content = generated_files.get("src/index.html") or generated_files.get("index.html")
        if html_content:
            generated_files = await self._optimize_html_js_integration(html_content, js_files, generated_files, project_root)

        # 2. Cross-JS Function Consistency
        generated_files = await self._optimize_cross_js_coherence(js_files, generated_files, project_root)

        self.context.event_publisher.publish("phase_complete", phase="5.2", message="JavaScript optimization complete")
        return generated_files, initial_structure, file_paths

    async def _optimize_html_js_integration(self, html: str, js_files: Dict[str, str], all_files: Dict[str, str], root: Path) -> Dict[str, str]:
        """Ensures index.html has the necessary IDs and script tags."""
        self.context.logger.info("  Checking HTML-JS DOM coherence...")
        
        # Find all document.getElementById calls in all JS files
        required_ids = set()
        for content in js_files.values():
            # Use triple quotes for regex to avoid escaping issues
            ids = re.findall(r'''document\.getElementById\(['"]([^'"]+)['"]\)''', content)
            required_ids.update(ids)

        missing_ids = [id for id in required_ids if f'id="{id}"' not in html and f"id='{id}'" not in html]
        
        if missing_ids:
            self.context.logger.warning(f"    Found {len(missing_ids)} missing IDs in HTML: {missing_ids}")
            # Request LLM to fix index.html
            fix_prompt = (f"The following IDs are required by JavaScript but missing in HTML: {missing_ids}. "
                          f"Please update the HTML structure to include these IDs logically.")
            
            # Simplified fix call (would normally use a specialized method)
            system = "You are a web developer. Fix HTML to match JS requirements. Return ONLY the full corrected HTML code."
            response, _ = self.context.llm_manager.get_client("coder").chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"HTML:\n{html}\n\nTask: {fix_prompt}"}
                ]
            )
            new_html = self.context.response_parser.extract_code(response.get("content", ""))
            if new_html:
                html_path = "src/index.html" if "src/index.html" in all_files else "index.html"
                all_files[html_path] = new_html
                self.context.file_manager.write_file(root / html_path, new_html)
                self.context.logger.info("    ✓ index.html updated with missing IDs.")

        return all_files

    async def _optimize_cross_js_coherence(self, js_files: Dict[str, str], all_files: Dict[str, str], root: Path) -> Dict[str, str]:
        """Ensures functions called in one file exist in another."""
        # This is a complex check, we'll use a specific LLM overview
        self.context.logger.info("  Checking Cross-JS functional coherence...")
        
        # Use a list comprehension and join to build the summary
        file_summaries = [f"--- FILE: {p} ---\n{c[:1000]}" for p, c in js_files.items()]
        project_summary = "\n".join(file_summaries)
        
        system = ("You are a lead developer. Review the interaction between these JavaScript files. "
                  "Look for mismatched function names, missing exports, or logical disconnects. "
                  "If you find an error, provide a FIX for the specific file. Respond in XML <fix file='path'>code</fix> format.")
        
        response, _ = self.context.llm_manager.get_client("coder").chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"JS Files Overview:\n{project_summary}"}
            ]
        )
        
        raw_res = response.get("content", "")
        # Robust regex for fix extraction
        fixes = re.findall(r'''<fix file=['"]([^'"]+)['"]>([\s\S]*?)</fix>''', raw_res)
        
        for file_path, corrected_code in fixes:
            if file_path in all_files:
                self.context.logger.info(f"    Applied cross-file fix to {file_path}")
                all_files[file_path] = corrected_code.strip()
                self.context.file_manager.write_file(root / file_path, corrected_code.strip())
                
        return all_files
