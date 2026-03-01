"""
Architect Agent — Planning & DAG construction.

Responsibilities:
- Analyse the project description and existing files.
- Use DependencyGraph to infer file relationships.
- Produce a TaskDAG where each DEVELOPER node is a file to generate,
  the DEVOPS node depends on all leaf developer nodes, and the AUDITOR
  node has no DAG dependencies (it reacts to events via EventPublisher).

This agent only uses read/analysis tools — it never writes files directly.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from backend.agents.domain_agents.base_domain_agent import BaseDomainAgent
from backend.agents.orchestrators.task_dag import AgentType, TaskDAG, TaskNode
from backend.utils.core.analysis.dependency_graph import DependencyGraph
from backend.utils.core.llm.prompt_loader import PromptLoader
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.domains.auto_generation.structure_generator import StructureGenerator

if TYPE_CHECKING:
    from backend.agents.orchestrators.blackboard import Blackboard
    from backend.agents.orchestrators.tool_dispatcher import ToolDispatcher


class ArchitectAgent(BaseDomainAgent):
    """
    ARCHITECT domain agent.

    Reads project context from Blackboard; produces a TaskDAG and writes it
    back under the key ``task_dag``.

    Output keys written to Blackboard:
        ``task_dag``              — The produced TaskDAG
        ``project_structure``    — The raw structure dict
        ``codebase_stable``      — Initially False (set True by orchestrator
                                   after all DEVELOPER tasks complete)
    """

    REQUIRED_TOOLS: List[str] = ["dependency_graph", "structure_generator"]
    agent_id: str = "architect"

    def __init__(
        self,
        dependency_graph: DependencyGraph,
        structure_generator: StructureGenerator,
        prompt_loader: PromptLoader,
        event_publisher: EventPublisher,
        logger: AgentLogger,
        tool_dispatcher: "ToolDispatcher",
    ) -> None:
        super().__init__(event_publisher, logger, tool_dispatcher)
        self._dep_graph = dependency_graph
        self._structure_gen = structure_generator
        self._prompt_loader = prompt_loader

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def plan_dag(
        self,
        project_description: str,
        project_name: str,
        blackboard: "Blackboard",
        image_paths: Optional[List[Path]] = None,
    ) -> TaskDAG:
        """High-level entry point called by DomainAgentOrchestrator.

        Creates a synthetic ARCHITECT TaskNode, runs it, and returns the
        produced TaskDAG.

        Args:
            project_description: Natural language project request.
            project_name:        Short project identifier.
            blackboard:          Shared state store.
            image_paths:         P7 — Optional list of image Paths (architecture
                                 diagrams, wireframes). Encoded as base64 and
                                 included in the LLM prompt if supported.
        """
        self._log_info(f"Planning DAG for project '{project_name}'")
        self._publish_event("architect_planning_started", project=project_name)

        # P7 — Encode images and store in Blackboard for UI "Visual Context" panel
        encoded_images: List[Dict[str, str]] = []
        if image_paths:
            for img_path in image_paths:
                try:
                    img_bytes = Path(img_path).read_bytes()
                    suffix = Path(img_path).suffix.lower().lstrip(".")
                    media_type = {
                        "jpg": "image/jpeg",
                        "jpeg": "image/jpeg",
                        "png": "image/png",
                        "gif": "image/gif",
                        "webp": "image/webp",
                    }.get(suffix, "image/png")
                    encoded_images.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.b64encode(img_bytes).decode(),
                            },
                            "filename": Path(img_path).name,
                        }
                    )
                    self._log_debug(f"Encoded context image: {img_path}")
                except Exception as exc:
                    self._log_warning(f"Could not encode image '{img_path}': {exc}")

        if encoded_images:
            await blackboard.write("context_images", encoded_images, self.agent_id)
            self._log_info(f"Stored {len(encoded_images)} context image(s) in Blackboard")

        node = TaskNode(
            id="__architect_plan__",
            agent_type=AgentType.ARCHITECT,
            task_data={
                "project_description": project_description,
                "project_name": project_name,
                "context_images": encoded_images,
            },
        )
        dag = await self.run(node, blackboard)
        self._publish_event("architect_planning_completed", project=project_name)
        return dag

    async def run(self, node: TaskNode, blackboard: "Blackboard") -> TaskDAG:
        """Execute the planning task and return the assembled TaskDAG."""
        project_description: str = node.task_data.get("project_description", "")
        project_name: str = node.task_data.get("project_name", "project")
        readme_content: str = blackboard.read("readme_content", "")

        # Step 1 — Retrieve or generate project structure
        structure = blackboard.read("project_structure")
        if structure is None:
            self._log_info("Generating project structure…")
            structure = await self._generate_structure(project_description, project_name, readme_content)
            await blackboard.write("project_structure", structure, self.agent_id)

        # Step 2 — Build dependency graph
        self._dep_graph.build_from_structure(structure, readme_content)
        generation_order: List[str] = self._dep_graph.get_generation_order()
        self._log_debug(f"Dependency graph: {len(generation_order)} files in generation order")

        # Step 3 — Build the DAG
        dag = self._build_dag(generation_order, structure)

        # Step 4 — Write outputs to Blackboard
        await blackboard.write("task_dag", dag, self.agent_id)
        await blackboard.write("codebase_stable", False, self.agent_id)
        self._log_info(
            f"TaskDAG built: {len(dag.all_nodes())} nodes "
            f"({sum(1 for n in dag.all_nodes() if n.agent_type == AgentType.DEVELOPER)} DEVELOPER, "
            f"1 DEVOPS, 1 AUDITOR)"
        )
        return dag

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _generate_structure(
        self,
        project_description: str,
        project_name: str,
        readme_content: str,
    ) -> Dict[str, Any]:
        """Ask StructureGenerator to produce the project structure dict."""
        try:
            # StructureGenerator.generate() is synchronous in the existing codebase
            structure = self._structure_gen.generate(
                project_description=project_description,
                project_name=project_name,
                readme_content=readme_content,
            )
            if isinstance(structure, dict):
                return structure
        except Exception as exc:
            self._log_error(f"StructureGenerator failed: {exc}; using minimal structure")

        # Fallback: minimal structure
        return {
            "folders": [
                {
                    "name": "src",
                    "files": ["main.py", "__init__.py"],
                    "folders": [],
                }
            ],
            "files": ["README.md", "requirements.txt"],
        }

    def _build_dag(
        self,
        generation_order: List[str],
        structure: Dict[str, Any],
    ) -> TaskDAG:
        """Convert a topological file order into a TaskDAG.

        Algorithm:
        1. For each file: create a DEVELOPER TaskNode.
           Dependencies = files in generation_order that appear *before* this
           file AND are listed as context dependencies by the DependencyGraph.
        2. Collect all leaf DEVELOPER nodes (no other DEVELOPER depends on them).
        3. Create a DEVOPS TaskNode that depends on all leaf DEVELOPER nodes.
        4. Create an AUDITOR TaskNode with no DAG dependencies (event-driven JIT).
        """
        dag = TaskDAG()
        dev_node_ids: List[str] = []

        # Create one DEVELOPER node per file
        for file_path in generation_order:
            context_deps = self._dep_graph.get_context_for_file(file_path, max_depth=1)
            # Only add dependencies that are already in the DAG
            valid_deps = [dep for dep in context_deps if dep in generation_order]

            node = TaskNode(
                id=file_path,
                agent_type=AgentType.DEVELOPER,
                task_data={
                    "file_path": file_path,
                    "plan": {},  # Populated later by LogicPlanningPhase if available
                    "context_deps": valid_deps,
                },
                dependencies=valid_deps,
            )
            try:
                dag.add_task(node)
                dev_node_ids.append(file_path)
            except ValueError:
                pass  # Skip duplicates

        # Leaf nodes = DEVELOPER nodes that no other DEVELOPER depends on
        all_deps: set = set()
        for nid in dev_node_ids:
            n = dag.get_node(nid)
            if n:
                all_deps.update(n.dependencies)
        leaf_dev_ids = [nid for nid in dev_node_ids if nid not in all_deps]

        if not leaf_dev_ids:
            leaf_dev_ids = dev_node_ids  # all files are independent

        # DEVOPS node — runs after all leaf developer files are generated
        devops_node = TaskNode(
            id="__devops__",
            agent_type=AgentType.DEVOPS,
            task_data={"trigger": "post_development"},
            dependencies=leaf_dev_ids,
        )
        dag.add_task(devops_node)

        # AUDITOR node — purely event-driven, no DAG dep; added as a final batch pass
        auditor_node = TaskNode(
            id="__auditor_final__",
            agent_type=AgentType.AUDITOR,
            task_data={"mode": "batch_final"},
            dependencies=["__devops__"],
        )
        dag.add_task(auditor_node)

        return dag

    def _extract_file_list_json(self, response_content: str) -> Optional[Dict[str, Any]]:
        """Try to extract JSON from an LLM response for DAG planning."""
        import re

        for tag in ("<dag_json>", "<plan_json>"):
            end_tag = tag.replace("<", "</")
            pattern = re.compile(rf"{re.escape(tag)}(.*?){re.escape(end_tag)}", re.DOTALL)
            match = pattern.search(response_content)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    pass

        # Fallback: try raw JSON
        try:
            return json.loads(response_content)
        except Exception:
            return None
