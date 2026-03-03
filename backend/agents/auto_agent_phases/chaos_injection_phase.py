"""Chaos Engineering — Fault Injection Phase.

An optional pipeline phase that corrupts a random subset of generated files
to verify that ShadowEvaluator and supervisor phases detect and repair faults.

Controlled by agent_features.json:
    "chaos_engineering": {"enabled": false, "injection_rate": 0.2}

The phase is registered in the pipeline directly after FileContentGenerationPhase.
When ``enabled`` is ``false`` (the default) the phase is a transparent pass-through
and adds zero overhead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase


class ChaosInjectionPhase(BasePhase):
    """Optional chaos engineering phase — injects structural faults into files.

    Fault types (see ChaosInjector):
    - ``remove_import``: delete one import/include line at random
    - ``rename_variable``: rename the first local variable to a nonsense name

    A ``chaos_fault_injected`` event is published per corrupted file so that
    the frontend can display a notification and testers can track injections.
    """

    phase_id = "chaos_injection"
    phase_label = "Chaos Engineering — Fault Injection"
    category = "validation"
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
        chaos_cfg = self.context.config.get("chaos_engineering", {})
        if not chaos_cfg.get("enabled", False):
            self.context.logger.info("[Chaos] Chaos injection disabled — skipping phase")
            return generated_files, initial_structure, file_paths

        from backend.utils.core.analysis.chaos_injector import ChaosInjector

        rate = float(chaos_cfg.get("injection_rate", 0.2))
        injector = ChaosInjector(injection_rate=rate, logger=self.context.logger)

        injected_count = 0
        for file_path, content in list(generated_files.items()):
            if not content:
                continue
            language = self.context.infer_language(file_path)
            if language == "unknown":
                continue
            corrupted, description = injector.inject_fault(content, language)
            if description:
                generated_files[file_path] = corrupted
                try:
                    self.context.file_manager.write_file(project_root / file_path, corrupted)
                except Exception:
                    pass
                self.context.logger.info(f"[Chaos] Injected fault into '{file_path}': {description}")
                await self.context.event_publisher.publish(
                    "chaos_fault_injected",
                    file_path=file_path,
                    fault_description=description,
                )
                injected_count += 1

        self.context.logger.info(
            f"[Chaos] Injection complete: {injected_count} file(s) corrupted out of {len(generated_files)} total"
        )
        return generated_files, initial_structure, file_paths
