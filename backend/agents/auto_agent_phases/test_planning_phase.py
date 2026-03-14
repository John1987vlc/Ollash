"""Test Planning Phase — writes test skeletons before source code is generated (TDD).

Runs after LogicPlanningPhase and before FileContentGenerationPhase.
For every source file described in ``context.logic_plan`` it generates a
skeleton test file (empty functions with descriptive docstrings and ``pass``
bodies) and writes it to disk. The skeletons give
GenerationExecutionPhase a concrete starting point and ensure every module
has at least one test from day one.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.utils.core.language_utils import LanguageUtils

# File extensions that should NOT get a test skeleton
_NON_SOURCE_EXTS = frozenset(
    {
        ".md",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".env",
        ".lock",
        ".gitignore",
        ".dockerignore",
        ".sh",
        ".bat",
        ".html",
        ".css",
        ".scss",
        ".less",
        ".svg",
        ".png",
        ".ico",
    }
)

# Files that are already tests or config — skip them
_SKIP_PATTERNS = ("test_", "spec_", "_test.", ".spec.", "_spec.", "conftest", "setup.py", "setup.cfg")


class TestPlanningPhase(BasePhase):
    """Phase 2.6: TDD — generate test skeletons from the logic plan.

    Runs for slim and full tiers. On nano models the phase is skipped by
    ``_build_adaptive_phases()`` in AutoAgent to save tokens.
    """

    phase_id = "2.6"
    phase_label = "Test-Driven Planning"

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
        logic_plan = self.context.logic_plan
        if not logic_plan:
            self.context.logger.info("[TestPlanning] No logic plan available — skipping test skeleton generation.")
            return generated_files, initial_structure, file_paths

        source_files = self._filter_source_files(list(logic_plan.keys()))
        self.context.logger.info(f"[TestPlanning] Generating test skeletons for {len(source_files)} source file(s).")

        for source_path in source_files:
            plan = logic_plan.get(source_path, {})
            test_path = LanguageUtils.get_test_file_path(source_path, LanguageUtils.infer_language(source_path))

            # Don't overwrite an existing test file
            if test_path in generated_files and generated_files[test_path].strip():
                continue

            skeleton = self._generate_skeleton(source_path, plan, project_description)
            if skeleton:
                self._write_file(project_root, test_path, skeleton, generated_files, file_paths)
                self.context.test_skeletons[source_path] = skeleton
                self.context.logger.info(f"  ✓ skeleton → {test_path}")

        self.context.logger.info(f"[TestPlanning] {len(self.context.test_skeletons)} skeleton(s) written.")
        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_source_files(file_paths: List[str]) -> List[str]:
        result = []
        for fp in file_paths:
            ext = Path(fp).suffix.lower()
            if ext in _NON_SOURCE_EXTS:
                continue
            name = Path(fp).name.lower()
            if any(name.startswith(p) or p in name for p in _SKIP_PATTERNS):
                continue
            result.append(fp)
        return result

    def _generate_skeleton(self, source_path: str, plan: Dict[str, Any], project_description: str) -> str:
        """Ask the LLM for a test skeleton for *source_path*."""
        exports = plan.get("exports", [])
        purpose = plan.get("purpose", "")
        language = LanguageUtils.infer_language(source_path)

        system_prompt = (
            f"You are a senior {language} engineer writing test skeletons following TDD. "
            "Generate a complete test file with EMPTY test functions (body = pass / placeholder). "
            "Each function must have a descriptive docstring explaining what it will test. "
            "Do NOT implement any logic — only write the skeleton structure. "
            "Import the module under test correctly. "
            "Output ONLY the raw code, no markdown fences."
        )
        user_prompt = (
            f"## Source file: {source_path}\n"
            f"## Purpose: {purpose}\n"
            f"## Public API / exports: {json.dumps(exports)}\n"
            f"## Project context: {project_description[:500]}\n\n"
            "Generate the test skeleton:"
        )

        try:
            response_data, _ = self.context.llm_manager.get_client("planner").chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options_override={"temperature": 0.1},
            )
            raw = response_data.get("content", "").strip()
            # Strip markdown fences
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(line for line in lines if not line.startswith("```")).strip()
            return raw
        except Exception as exc:
            self.context.logger.warning(f"[TestPlanning] Skeleton generation failed for {source_path}: {exc}")
            return self._minimal_skeleton(source_path, exports, language)

    @staticmethod
    def _minimal_skeleton(source_path: str, exports: List[str], language: str) -> str:
        """Deterministic fallback skeleton — no LLM required."""
        module = Path(source_path).stem
        if language == "python":
            funcs = "\n\n".join(
                f'def test_{exp.lower().replace("-", "_")}():\n    """Test that {exp} works correctly."""\n    pass'
                for exp in (exports or [module])
            ) or (f'def test_{module}():\n    """Placeholder test for {module}."""\n    pass')
            return f"# Test skeleton for {source_path}\n\n{funcs}\n"
        elif language in ("javascript", "typescript"):
            funcs = "\n\n".join(
                f"  test('{exp} works correctly', () => {{\n    // TODO: implement\n  }});"
                for exp in (exports or [module])
            )
            return f"// Test skeleton for {source_path}\n\ndescribe('{module}', () => {{\n{funcs}\n}});\n"
        return f"// Test skeleton for {source_path} — fill in test cases\n"
