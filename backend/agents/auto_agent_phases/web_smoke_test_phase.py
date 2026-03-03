"""Web Smoke Test Phase — spins up a temporary HTTP server and uses Playwright
to verify that the generated web project actually loads in a browser.

Skips gracefully when:
- The project has no ``.html`` files (non-web project).
- ``playwright`` is not installed in the environment.

When a browser console error is detected the phase passes the error log to
``file_refiner.refine_file()`` for the relevant JS file (same repair path used
by SeniorReviewPhase) and retries once more — but never blocks the pipeline.
"""

import json
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase

# Minimal Playwright Python script injected as a subprocess — self-contained,
# no imports from Ollash internals so it's safe to run in a clean subprocess.
_SMOKE_SCRIPT_TEMPLATE = """\
import sys, json
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        try:
            page.goto("http://localhost:{port}/{index}", timeout=10000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
        except Exception as nav_err:
            console_errors.append(f"Navigation error: {{nav_err}}")
        visible = page.locator("button, canvas, input, [id]").count()
        browser.close()
        print(json.dumps({{"errors": console_errors, "visible_elements": visible}}))
except ImportError:
    print(json.dumps({{"errors": ["playwright not available"], "visible_elements": 0}}))
except Exception as e:
    print(json.dumps({{"errors": [str(e)], "visible_elements": 0}}))
"""

_JS_FILE_IN_TRACE = re.compile(r"([\w./]+\.(?:js|ts|jsx|tsx))")


class WebSmokeTestPhase(BasePhase):
    """Phase (after TestGenerationExecution): browser smoke test for web projects.

    Inserts itself only when ``playwright`` is available and the project has at
    least one HTML file. On test failure triggers a single repair pass via the
    existing file_refiner, then continues — never blocks the pipeline.
    """

    phase_id: str = "web_smoke_test"
    phase_label: str = "Web Browser Smoke Test"
    category: str = "verification"
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

        # Guard 1: playwright must be installed
        if not shutil.which("playwright") and not _playwright_importable():
            self.context.logger.info(
                "[WebSmokeTest] playwright not installed — skipping. Run `playwright install chromium` to enable."
            )
            return generated_files, initial_structure, file_paths

        # Guard 2: project must contain at least one HTML file
        html_files = [p for p in generated_files if p.endswith(".html")]
        if not html_files:
            self.context.logger.info("[WebSmokeTest] No HTML files detected — skipping (non-web project).")
            return generated_files, initial_structure, file_paths

        index_html = self._pick_index_html(html_files)
        port = _free_port()

        self.context.logger.info(f"[WebSmokeTest] Starting HTTP server on :{port}, testing {index_html}...")
        await self.context.event_publisher.publish(
            "phase_start",
            phase=self.phase_id,
            message=f"Browser smoke test on port {port}",
        )

        server_proc: Optional[subprocess.Popen] = None
        try:
            server_proc = subprocess.Popen(
                ["python", "-m", "http.server", str(port), "--directory", str(project_root)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1.5)  # Give server time to start

            result = self._run_playwright(port, index_html)
        finally:
            if server_proc is not None:
                server_proc.terminate()
                try:
                    server_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server_proc.kill()

        errors: List[str] = result.get("errors", [])
        visible: int = result.get("visible_elements", 0)

        if not errors and visible > 0:
            self.context.logger.info(
                f"[WebSmokeTest] ✓ Page loaded successfully — {visible} interactive element(s) visible."
            )
            await self.context.event_publisher.publish(
                "phase_complete",
                phase=self.phase_id,
                message=f"Smoke test passed ({visible} elements visible)",
            )
            return generated_files, initial_structure, file_paths

        # Smoke test found issues — attempt a single repair pass
        self.context.logger.warning(f"[WebSmokeTest] Browser console errors detected ({len(errors)}): {errors[:3]}")
        if errors:
            generated_files = await self._repair_from_errors(errors, generated_files, project_root, readme_content)

        await self.context.event_publisher.publish(
            "phase_complete",
            phase=self.phase_id,
            message=f"Smoke test finished with {len(errors)} error(s) — repair attempted",
        )
        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pick_index_html(self, html_files: List[str]) -> str:
        """Return the most likely entry-point HTML file."""
        for candidate in ("index.html", "app.html", "main.html"):
            if any(p.endswith(candidate) or p == candidate for p in html_files):
                return candidate
        return Path(html_files[0]).name

    def _run_playwright(self, port: int, index_html: str) -> Dict[str, Any]:
        """Run the inline Playwright smoke script as a subprocess and return results."""
        script = _SMOKE_SCRIPT_TEMPLATE.format(port=port, index=index_html)
        try:
            result = subprocess.run(
                ["python", "-c", script],
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
            )
            output = result.stdout.strip()
            if output:
                return json.loads(output)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as exc:
            self.context.logger.warning(f"[WebSmokeTest] Playwright run error: {exc}")
        return {"errors": [], "visible_elements": 0}

    async def _repair_from_errors(
        self,
        errors: List[str],
        generated_files: Dict[str, str],
        project_root: Path,
        readme_content: str,
    ) -> Dict[str, str]:
        """Attempt to repair JS files mentioned in browser console errors."""
        error_text = "\n".join(errors)
        js_candidates = _JS_FILE_IN_TRACE.findall(error_text)

        repaired = 0
        for raw_path in dict.fromkeys(js_candidates):  # deduplicate, preserve order
            # Normalise to relative path
            rel_path = raw_path.lstrip("/")
            content = generated_files.get(rel_path, "")
            if not content:
                continue

            try:
                issues = [{"description": f"Browser console error: {e}", "severity": "high"} for e in errors[:3]]
                refined = await self.context.file_refiner.refine_file(
                    rel_path, content, readme_content[:300], issues=issues
                )
                if refined and refined != content:
                    generated_files[rel_path] = refined
                    self.context.file_manager.write_file(project_root / rel_path, refined)
                    self.context.logger.info(f"  [WebSmokeTest] Repaired {rel_path}")
                    repaired += 1
            except Exception as exc:
                self.context.logger.warning(f"  [WebSmokeTest] Repair failed for {rel_path}: {exc}")

            if repaired >= 3:  # limit repair scope
                break

        return generated_files


# ------------------------------------------------------------------
# Module-level helpers (no class access needed)
# ------------------------------------------------------------------


def _playwright_importable() -> bool:
    """Return True if playwright Python package is importable."""
    try:
        import importlib.util

        return importlib.util.find_spec("playwright") is not None
    except Exception:
        return False


def _free_port() -> int:
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]
