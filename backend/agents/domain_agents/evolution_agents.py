"""
Evolution Agents - Deep Refinement Mode.

This module contains specialized agents for long-running autonomous project evolution:
- TesterAgent: Writes tests and runs them.
- UXDesignerAgent: Proposes visual/CSS improvements.
- SecurityAgent: Audits for vulnerabilities.
- PerformanceAgent: Audits for algorithmic/structural performance.
- ProductManagerAgent: Expands the project scope autonomously.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class EvolutionBaseAgent:
    def __init__(self, llm_client_manager, config, logger):
        self.llm_client = llm_client_manager.get_client("coder")
        self.config = config
        self._logger = logger

    def _log_info(self, msg):
        self._logger.info(msg)
        
    def _log_error(self, msg):
        self._logger.error(msg)
        
    def _llm_call(self, system_prompt, user_prompt, max_tokens=2048):
        response, _ = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            tools=[],
        )
        return response.get("content", "") or response.get("message", {}).get("content", "")


from backend.utils.core.llm.llm_response_parser import LLMResponseParser


# Schemas for structured output
class AgentFeedback(BaseModel):
    issues: List[Dict[str, str]] = Field(default_factory=list, description="List of issues found with 'description', 'file', and 'recommendation'")

class ProductManagerBacklog(BaseModel):
    epics: List[Dict[str, str]] = Field(default_factory=list, description="List of epics to implement with 'title' and 'description'")


class UXDesignerAgent(EvolutionBaseAgent):
    """Focuses purely on UI/UX, aesthetics, layout, colors, and accessibility."""
    
    def run(self, files: Dict[str, str]) -> Dict[str, Any]:
        self._log_info("UX Designer analyzing interface...")
        system_prompt = (
            "You are an expert UX/UI Designer. Review the provided frontend files (HTML/CSS/JS/TS). "
            "Suggest visually stunning layout improvements, color palettes, micro-interactions, "
            "and accessibility (a11y) fixes. Do NOT invent problems if the UI is already great."
        )
        user_prompt = f"Files:\n{self._format_files(files)}"
        
        try:
            raw_response = self._llm_call(system_prompt, user_prompt, max_tokens=2048)
            return {"status": "success", "feedback": raw_response}
        except Exception as e:
            self._log_error(f"UXDesigner failed: {e}")
            return {"status": "error", "error": str(e)}

    def _format_files(self, files: Dict[str, str]) -> str:
        out = ""
        for name, content in files.items():
            out += f"--- {name} ---\n{content}\n\n"
        return out


class SecurityAgent(EvolutionBaseAgent):
    """Focuses on OWASP vulnerabilities, XSS, CSRF, auth flaws, and injection."""
    
    def run(self, files: Dict[str, str]) -> Dict[str, Any]:
        self._log_info("Security Expert analyzing attack vectors...")
        system_prompt = (
            "You are a Cybersecurity Expert. Audit the following files for vulnerabilities "
            "(SQLi, XSS, CSRF, insecure auth, data leaks, path traversal). "
            "Focus ONLY on critical and high-severity security flaws."
        )
        user_prompt = f"Files:\n{self._format_files(files)}"
        
        try:
            raw_response = self._llm_call(system_prompt, user_prompt, max_tokens=2048)
            return {"status": "success", "feedback": raw_response}
        except Exception as e:
            self._log_error(f"SecurityAgent failed: {e}")
            return {"status": "error", "error": str(e)}

    def _format_files(self, files: Dict[str, str]) -> str:
        out = ""
        for name, content in files.items():
            out += f"--- {name} ---\n{content}\n\n"
        return out


class PerformanceAgent(EvolutionBaseAgent):
    """Focuses on algorithmic complexity, database N+1 queries, memory leaks, and bundle size."""
    
    def run(self, files: Dict[str, str]) -> Dict[str, Any]:
        self._log_info("Performance Optimizer analyzing algorithmic complexity...")
        system_prompt = (
            "You are a Performance Engineer. Review the code for algorithmic inefficiencies (O(N^2) loops), "
            "memory leaks, missing caching, N+1 query problems, and heavy DOM manipulations. "
            "Provide concrete refactoring recommendations."
        )
        user_prompt = f"Files:\n{self._format_files(files)}"
        
        try:
            raw_response = self._llm_call(system_prompt, user_prompt, max_tokens=2048)
            return {"status": "success", "feedback": raw_response}
        except Exception as e:
            self._log_error(f"PerformanceAgent failed: {e}")
            return {"status": "error", "error": str(e)}

    def _format_files(self, files: Dict[str, str]) -> str:
        out = ""
        for name, content in files.items():
            out += f"--- {name} ---\n{content}\n\n"
        return out


class ProductManagerAgent(EvolutionBaseAgent):
    """Expands the project scope by proposing new Epics and Features autonomously."""
    
    def run(self, files: Dict[str, str], project_description: str) -> Dict[str, Any]:
        self._log_info("Product Manager analyzing evolution opportunities...")
        system_prompt = (
            "You are a visionary Product Manager. Based on the current project code and its original description, "
            "propose EXACTLY ONE new logical epic/feature to implement next to make the product more complete "
            "and professional. The feature must be achievable."
        )
        user_prompt = f"Original Project: {project_description}\n\nCurrent Files:\n{self._format_files(files)}"
        
        try:
            raw_response = self._llm_call(system_prompt, user_prompt, max_tokens=1024)
            return {"status": "success", "epic": raw_response}
        except Exception as e:
            self._log_error(f"ProductManagerAgent failed: {e}")
            return {"status": "error", "error": str(e)}

    def _format_files(self, files: Dict[str, str]) -> str:
        out = ""
        for name, content in files.items():
            out += f"--- {name} ---\n{content}\n\n"
        return out


class TesterAgent(EvolutionBaseAgent):
    """Generates tests for the code, preparing it for the SandboxRunner dynamic loop."""
    
    def run(self, files: Dict[str, str]) -> Dict[str, Any]:
        self._log_info("TesterAgent generating unit tests...")
        system_prompt = (
            "You are an automated SDET. Review the following files and write a comprehensive "
            "test suite (e.g., pytest for Python, Jest for JS). Return ONLY the test code without explanations."
        )
        user_prompt = f"Files:\n{self._format_files(files)}"
        
        try:
            raw_response = self._llm_call(system_prompt, user_prompt, max_tokens=4096)
            return {"status": "success", "test_code": raw_response}
        except Exception as e:
            self._log_error(f"TesterAgent failed: {e}")
            return {"status": "error", "error": str(e)}

    def _format_files(self, files: Dict[str, str]) -> str:
        out = ""
        for name, content in files.items():
            out += f"--- {name} ---\n{content}\n\n"
        return out

class VisualReviewAgent(EvolutionBaseAgent):
    """Takes screenshots using Playwright and evaluates UI using a Vision LLM (e.g., llava)."""
    
    def run(self, files: Dict[str, str], project_path: str) -> Dict[str, Any]:
        self._log_info("Visual Reviewer capturing and analyzing screenshots with llava:13b...")
        
        # 1. Look for index.html
        index_html = None
        for name in files:
            if name.endswith("index.html"):
                index_html = name
                break
                
        if not index_html:
            return {"status": "skipped", "reason": "No index.html found to render."}
            
        import tempfile
        import os
        from pathlib import Path
        
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self._log_error("Playwright not installed. Run: pip install playwright && playwright install")
            return {"status": "error", "error": "Playwright not installed."}

        screenshot_path = ""
        # Write files temporarily to render them
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            for fname, fcontent in files.items():
                target_file = temp_path / fname
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_text(fcontent, encoding="utf-8")
                
            main_url = f"file://{temp_path / index_html}"
            screenshot_path = str(Path(project_path) / ".ollash" / "visual_screenshot.png")
            
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(main_url, wait_until="networkidle")
                    page.screenshot(path=screenshot_path, full_page=True)
                    browser.close()
            except Exception as e:
                self._log_error(f"Playwright rendering failed: {e}")
                return {"status": "error", "error": f"Playwright failed: {e}"}
                
        # 2. Analyze with LLaVA
        system_prompt = (
            "You are a Senior UI/UX QA Tester. You are provided with a screenshot of a generated web application. "
            "Identify any visual defects, misalignments, overlapping text, poor contrast, or unstyled elements. "
            "Return a concise list of concrete CSS/HTML fixes needed. If it looks perfect, explicitly say 'UI Looks Great'."
        )
        
        try:
            # We must use base64 encoding or pass the file path depending on Ollama python client support
            # For Ollama python client, we can pass paths to images
            response, _ = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user", 
                        "content": "Please review this UI screenshot.",
                        "images": [screenshot_path]
                    }
                ],
                tools=[],
                # Force the model to llava:13b for vision
                model_override="llava:13b" 
            )
            raw_response = response.get("content", "") or response.get("message", {}).get("content", "")
            return {"status": "success", "feedback": raw_response, "screenshot": screenshot_path}
        except Exception as e:
            self._log_error(f"LLaVA vision analysis failed: {e}")
            return {"status": "error", "error": str(e)}
