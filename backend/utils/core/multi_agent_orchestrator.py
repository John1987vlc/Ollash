"""
Multi-Agent Parallel Orchestration

Enables multiple LLM agent instances to work simultaneously on different
module groups during the file content generation phase.
"""

import asyncio
from typing import Any, Callable, Dict, List

from backend.interfaces.imodel_provider import IModelProvider
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.dependency_graph import DependencyGraph
from backend.utils.core.parallel_generator import ParallelFileGenerator


class MultiAgentOrchestrator:
    """Orchestrates multiple LLM agent instances for parallel file generation.

    Splits files into independent module groups based on the dependency graph,
    then assigns each group to a separate LLM agent instance for concurrent generation.
    """

    def __init__(
        self,
        agents: List[IModelProvider],
        parallel_gen: ParallelFileGenerator,
        dep_graph: DependencyGraph,
        logger: AgentLogger,
    ):
        self.agents = agents
        self.parallel_gen = parallel_gen
        self.dep_graph = dep_graph
        self.logger = logger

    def split_into_groups(self, file_paths: List[str], generated_files: Dict[str, str]) -> List[List[str]]:
        """Split files into independent groups using the dependency graph.

        Files with no cross-group dependencies are grouped together so they
        can be generated in parallel by different agents.
        """
        if not file_paths:
            return []

        # Build adjacency from dependency graph
        adjacency: Dict[str, set] = {}
        for fp in file_paths:
            adjacency[fp] = set()
            deps = self.dep_graph.get_dependencies(fp)
            if deps:
                adjacency[fp] = set(deps) & set(file_paths)

        # Find connected components (files that depend on each other)
        visited = set()
        groups: List[List[str]] = []

        def dfs(node: str, component: List[str]):
            visited.add(node)
            component.append(node)
            for neighbor in adjacency.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, component)
            # Also check reverse dependencies
            for other, deps in adjacency.items():
                if node in deps and other not in visited:
                    dfs(other, component)

        for fp in file_paths:
            if fp not in visited:
                component: List[str] = []
                dfs(fp, component)
                if component:
                    groups.append(component)

        # Balance groups across available agents
        num_agents = len(self.agents)
        if len(groups) > num_agents:
            # Merge smallest groups to match agent count
            groups.sort(key=len)
            while len(groups) > num_agents:
                smallest = groups.pop(0)
                groups[0] = smallest + groups[0]

        self.logger.info(f"Split {len(file_paths)} files into {len(groups)} groups for {num_agents} agents")
        return groups

    async def orchestrate(
        self,
        file_paths: List[str],
        generated_files: Dict[str, str],
        generation_fn: Callable,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """Orchestrate parallel generation across multiple agents.

        Args:
            file_paths: Files to generate content for.
            generated_files: Existing files for context.
            generation_fn: Async function(agent, file_path, context, **kwargs) -> str
            **kwargs: Additional arguments passed to generation_fn.

        Returns:
            Dictionary of {file_path: generated_content}.
        """
        groups = self.split_into_groups(file_paths, generated_files)

        if not groups:
            return {}

        results: Dict[str, str] = {}
        tasks = []

        for i, group in enumerate(groups):
            agent = self.agents[i % len(self.agents)]
            task = self._generate_group(agent, group, generated_files, generation_fn, **kwargs)
            tasks.append(task)

        group_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(group_results):
            if isinstance(result, Exception):
                self.logger.error(f"Agent group {i} failed: {result}")
                continue
            results.update(result)

        self.logger.info(f"Multi-agent orchestration complete: {len(results)}/{len(file_paths)} files generated")
        return results

    async def _generate_group(
        self,
        agent: IModelProvider,
        file_paths: List[str],
        context_files: Dict[str, str],
        generation_fn: Callable,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """Generate content for a group of files using a specific agent."""
        results: Dict[str, str] = {}

        for fp in file_paths:
            try:
                content = await generation_fn(
                    agent=agent,
                    file_path=fp,
                    context_files=context_files,
                    **kwargs,
                )
                if content:
                    results[fp] = content
                    # Add to context for subsequent files in same group
                    context_files[fp] = content
            except Exception as e:
                self.logger.error(f"Failed to generate {fp}: {e}")

        return results
