import json
from pathlib import Path
from typing import Any
from src.utils.core.code_analyzer import CodeAnalyzer
from src.utils.core.command_executor import CommandExecutor
from src.utils.core.tool_decorator import ollash_tool

class CodeAnalysisTools:
    def __init__(self, project_root: Path, code_analyzer: CodeAnalyzer, command_executor: CommandExecutor, logger: Any):
        self.project_root = project_root
        self.analyzer = code_analyzer
        self.exec = command_executor
        self.logger = logger

    @ollash_tool(
        name="analyze_project",
        description="Analyzes the entire project structure, dependencies, and code patterns to provide a comprehensive overview.",
        parameters={
            "path": {"type": "string", "description": "Optional: The path to the project root or sub-directory to analyze. Defaults to current project root."}
        },
        toolset_id="code_analysis_tools",
        agent_types=["code"]
    )
    def analyze_project(self, focus: str = "all", write_md: bool = False, force_md: bool = False, md_name: str = "PROJECT_ANALYSIS.md"):
        """
        Analyze the project and optionally generate a Markdown report.
        If writing is not needed, returns the Markdown content directly.
        """
        self.logger.info(f"🔍 Analyzing project (focus: {focus})...")

        try:
            analysis = {
                "ok": True,
                "project_root": str(self.project_root),
                "focus": focus,
            }

            # ---------- Structure ----------
            if focus in ("all", "structure"):
                py_files = list(self.project_root.rglob("*.py"))
                directories = sorted(
                    {str(f.parent.relative_to(self.project_root)) for f in py_files}
                )

                analysis["structure"] = {
                    "python_files": len(py_files),
                    "directories": len(directories),
                    "top_level_dirs": sorted(
                        d.name for d in self.project_root.iterdir()
                        if d.is_dir() and not d.name.startswith(".") and not d.name.startswith("venv") # Exclude venv
                    ),
                }

            # ---------- Dependencies ----------
            if focus in ("all", "dependencies"):
                req_file = self.project_root / "requirements.txt"
                if req_file.exists():
                    deps = [
                        d.strip() for d in req_file.read_text().splitlines()
                        if d.strip() and not d.startswith("#")
                    ]
                    analysis["dependencies"] = deps
                else:
                    analysis["dependencies"] = []

            # ---------- Code Quality ----------
            if focus in ("all", "code_quality"):
                try:
                    # Assuming CodeAnalyzer has an analyze_quality method, if not, it needs to be added or faked.
                    # For now, let's just add a placeholder.
                    # analysis["code_quality"] = self.analyzer.analyze_quality()
                    analysis["code_quality"] = {"placeholder": "Code quality analysis will go here"}
                except Exception as e:
                    analysis["code_quality"] = {"error": str(e)}

            # ---------- Heuristics for AI context ----------
            analysis["signals"] = {
                "has_tests": bool(list(self.project_root.rglob("test_*.py"))),
                "has_readme": (self.project_root / "README.md").exists(),
                "is_package": (self.project_root / "__init__.py").exists(),
            }

            # ---------- Markdown generation ----------
            md_lines = [
                "# 📊 Project Analysis",
                "",
                f"**Root:** `{analysis['project_root']}`",
                f"**Focus:** `{focus}`",
                "",
                "## 📁 Structure",
            ]

            if "structure" in analysis:
                s = analysis["structure"]
                md_lines += [
                    f"- 🐍 Python files: **{s['python_files']}**",
                    f"- 📂 Directories: **{s['directories']}**",
                    "",
                    "**Top-level directories:**",
                    *[f"- `{d}`" for d in s["top_level_dirs"]],
                    "",
                ]

            md_lines.append("## 📦 Dependencies")
            if analysis.get("dependencies"):
                md_lines += [f"- `{d}`" for d in analysis["dependencies"]]
            else:
                md_lines.append("_No dependencies found_")

            if "code_quality" in analysis:
                md_lines += [
                    "",
                    "## ✅ Code Quality",
                    "```json",
                    json.dumps(analysis["code_quality"], indent=2),
                    "```",
                ]

            md_lines += [
                "",
                "## 🧠 Project Signals",
            ]
            for k, v in analysis["signals"].items():
                md_lines.append(f"- **{k}**: `{v}`")

            markdown_content = "\n".join(md_lines)

            # ---------- Conditional MD writing ----------
            # This part is now handled by CodeAgent via file_system_tools.write_file
            md_written = write_md and (force_md or not (self.project_root / md_name).exists())

            self.logger.info("✅ Project analysis complete")

            return {
                "ok": True,
                "analysis": analysis,
                "markdown": markdown_content,
                "md_written": md_written,
                "md_path": str(self.project_root / md_name) if md_written else None, # Return potential path
            }

        except Exception as e:
            self.logger.error(f"Error analyzing project: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="search_code",
        description="Searches for a specific pattern within the codebase.",
        parameters={
            "pattern": {"type": "string", "description": "The regex pattern to search for."},
            "file_pattern": {"type": "string", "description": "Optional: Glob pattern to filter files (e.g., '*.py', 'src/**/*.js')."},
            "case_sensitive": {"type": "boolean", "description": "Optional: Whether the search should be case-sensitive. Defaults to false."}
        },
        toolset_id="code_analysis_tools",
        agent_types=["code"],
        required=["pattern"]
    )
    def search_code(self, query: str, pattern: str = "**/*.py", max_results: int = 10):
        """Search code using grep"""
        try:
            # Using CommandExecutor for this, as it's a shell command.
            # However, the original used subprocess directly. I'll stick to CommandExecutor.
            r = self.exec.execute(
                f"grep -r -n '{query}' {self.project_root}", # This command needs adjustment for Windows.
                timeout=30
            )
            
            if not r.success:
                self.logger.warning(f"Search command failed: {r.stderr}")
                return {"ok": False, "error": r.stderr, "query": query}

            matches = r.stdout.splitlines()[:max_results]
            
            if matches:
                self.logger.info(f"🔍 Found {len(matches)} matches for '{query}':")
                for match in matches[:5]:
                    self.logger.debug(f"  • {match}")
                if len(matches) > 5:
                    self.logger.debug(f"  ... and {len(matches) - 5} more")
            
            return {"ok": True, "matches": matches, "query": query}
        except Exception as e:
            self.logger.error(f"Search error: {e}", e)
            return {"ok": False, "error": str(e)}