"""Phase grouping and parallel execution support for AutoAgent pipeline.

Defines PhaseGroup for organizing phases by category and enabling
parallel execution of independent phases via asyncio.gather().
"""

import asyncio
import copy
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.interfaces.iagent_phase import IAgentPhase
from backend.utils.core.exceptions import ParallelPhaseError


class PhaseGroup:
    """A group of phases that can execute sequentially or in parallel.

    Attributes:
        name: Human-readable group name.
        phases: List of phases in this group.
        parallel: If True, phases run concurrently via asyncio.gather().
        category: Logical category (generation, review, validation, infrastructure).
    """

    def __init__(
        self,
        name: str,
        phases: List[IAgentPhase],
        parallel: bool = False,
        category: str = "generation",
    ):
        self.name = name
        self.phases = phases
        self.parallel = parallel
        self.category = category

    async def execute(
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
        """Execute all phases in the group, either sequentially or in parallel."""
        if self.parallel and len(self.phases) > 1:
            return await self._execute_parallel(
                project_description,
                project_name,
                project_root,
                readme_content,
                initial_structure,
                generated_files,
                file_paths,
                **kwargs,
            )
        return await self._execute_sequential(
            project_description,
            project_name,
            project_root,
            readme_content,
            initial_structure,
            generated_files,
            file_paths,
            **kwargs,
        )

    async def _execute_sequential(
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
        """Execute phases one after another, passing state forward."""
        for phase in self.phases:
            generated_files, initial_structure, file_paths = await phase.execute(
                project_description=project_description,
                project_name=project_name,
                project_root=project_root,
                readme_content=readme_content,
                initial_structure=initial_structure,
                generated_files=generated_files,
                file_paths=file_paths,
                **kwargs,
            )
            readme_content = generated_files.get("README.md", readme_content)
        return generated_files, initial_structure, file_paths

    async def _execute_parallel(
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
        """Execute independent phases concurrently and merge results."""
        tasks = []
        for phase in self.phases:
            phase_files = copy.copy(generated_files)
            phase_paths = list(file_paths)
            phase_structure = copy.copy(initial_structure)

            tasks.append(
                phase.execute(
                    project_description=project_description,
                    project_name=project_name,
                    project_root=project_root,
                    readme_content=readme_content,
                    initial_structure=phase_structure,
                    generated_files=phase_files,
                    file_paths=phase_paths,
                    **kwargs,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results and collect errors
        failed_phases: Dict[str, str] = {}
        merged_files = dict(generated_files)
        merged_paths = list(file_paths)
        merged_structure = dict(initial_structure)

        for phase, result in zip(self.phases, results):
            phase_name = phase.__class__.__name__
            if isinstance(result, Exception):
                failed_phases[phase_name] = str(result)
                continue
            r_files, r_structure, r_paths = result
            merged_files.update(r_files)
            merged_structure.update(r_structure)
            for p in r_paths:
                if p not in merged_paths:
                    merged_paths.append(p)

        if failed_phases:
            raise ParallelPhaseError(failed_phases)

        return merged_files, merged_structure, merged_paths


# --------------- Predefined Parallel Groups ---------------

PARALLEL_VALIDATION_PHASES = {
    "SecurityScanPhase",
    "LicenseCompliancePhase",
}

PARALLEL_INFRA_PHASES = {
    "InfrastructureGenerationPhase",
    "DocumentationDeployPhase",
}


def build_phase_groups(phases: List[IAgentPhase]) -> List:
    """Convert a flat phase list into groups, detecting parallelizable sets.

    Returns a mixed list of IAgentPhase (sequential) and PhaseGroup (parallel).
    """
    result: list = []
    i = 0
    phase_names = [p.__class__.__name__ for p in phases]

    while i < len(phases):
        name = phase_names[i]

        # Check for validation parallel group
        if name in PARALLEL_VALIDATION_PHASES:
            group_phases = [phases[i]]
            j = i + 1
            while j < len(phases) and phase_names[j] in PARALLEL_VALIDATION_PHASES:
                group_phases.append(phases[j])
                j += 1
            if len(group_phases) > 1:
                result.append(PhaseGroup("Validation", group_phases, parallel=True, category="validation"))
                i = j
                continue

        # Check for infra parallel group
        if name in PARALLEL_INFRA_PHASES:
            group_phases = [phases[i]]
            j = i + 1
            while j < len(phases) and phase_names[j] in PARALLEL_INFRA_PHASES:
                group_phases.append(phases[j])
                j += 1
            if len(group_phases) > 1:
                result.append(PhaseGroup("Infrastructure", group_phases, parallel=True, category="infrastructure"))
                i = j
                continue

        # Single phase
        result.append(phases[i])
        i += 1

    return result
