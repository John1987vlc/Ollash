"""
LangGraph Swarm Orchestrator — Orchestration powered by LangGraph.

Replaces or wraps the custom blackboard loop with a formal LangGraph StateGraph,
orchestrating:
  - ArchitectNode
  - DeveloperNode (pool)
  - AuditorNode (linter/security scans)
  - DevOpsNode (CI/CD / infra)
  - Self-Healing loop as conditional transitions
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, cast

from langgraph.graph import StateGraph, END

from backend.agents.domain_agents.architect_agent import ArchitectAgent
from backend.agents.domain_agents.auditor_agent import AuditorAgent
from backend.agents.domain_agents.developer_agent import DeveloperAgent
from backend.agents.domain_agents.devops_agent import DevOpsAgent
from backend.agents.orchestrators.blackboard import Blackboard
from backend.agents.orchestrators.task_dag import TaskNode, AgentType, TaskStatus
from backend.utils.core.system.agent_logger import AgentLogger


class SwarmState(TypedDict):
    """The state schema for the LangGraph swarm."""
    project_description: str
    project_name: str
    generated_files: Dict[str, str]  # file_path -> content
    errors: List[Dict[str, Any]]
    tasks_todo: List[Dict[str, Any]]
    tasks_done: List[Dict[str, Any]]
    audit_report: Dict[str, Any]
    project_path: str
    stage: str  # "planning", "coding", "auditing", "infra", "done"


class LangGraphSwarmOrchestrator:
    """Orchestrates domain agents using LangGraph instead of a custom sync loop."""

    def __init__(
        self,
        architect_agent: ArchitectAgent,
        developer_agent: DeveloperAgent,
        devops_agent: DevOpsAgent,
        auditor_agent: AuditorAgent,
        blackboard: Blackboard,
        logger: AgentLogger,
        generated_projects_dir: Optional[Path] = None,
        tester_agent=None,
        ux_designer_agent=None,
        security_agent=None,
        performance_agent=None,
        product_manager_agent=None,
        visual_review_agent=None,
    ) -> None:
        self._architect = architect_agent
        self._developer = developer_agent
        self._devops = devops_agent
        self._auditor = auditor_agent
        self._tester = tester_agent
        self._ux_designer = ux_designer_agent
        self._security = security_agent
        self._performance = performance_agent
        self._product_manager = product_manager_agent
        self._visual_reviewer = visual_review_agent
        self._blackboard = blackboard
        self._logger = logger
        self._generated_projects_dir = generated_projects_dir or Path(".ollash/generated_projects")
        
        # Compile our StateGraph
        self._graph = self._build_graph()

    def _log_info(self, msg: str) -> None:
        self._logger.info(f"[LangGraphSwarm] {msg}")

    def _log_error(self, msg: str) -> None:
        self._logger.error(f"[LangGraphSwarm] {msg}")

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> StateGraph:
        """Construct the LangGraph StateGraph."""
        builder = StateGraph(SwarmState)

        # Register nodes
        builder.add_node("architect", self._node_architect)
        builder.add_node("developer", self._node_developer)
        builder.add_node("auditor", self._node_auditor)
        builder.add_node("devops", self._node_devops)
        
        # Evolution Mode Nodes
        builder.add_node("tester", self._node_tester)
        builder.add_node("ux_designer", self._node_ux_designer)
        builder.add_node("security", self._node_security)
        builder.add_node("performance", self._node_performance)
        builder.add_node("product_manager", self._node_product_manager)
        builder.add_node("visual_reviewer", self._node_visual_reviewer)

        # Set entry point
        builder.set_entry_point("architect")

        # Define transitions
        builder.add_conditional_edges(
            "architect",
            self._route_after_architect,
            {
                "coding": "developer",
                "done": END
            }
        )

        builder.add_conditional_edges(
            "developer",
            self._route_after_developer,
            {
                "coding": "developer",
                "auditing": "auditor"
            }
        )

        builder.add_conditional_edges(
            "auditor",
            self._route_after_auditor,
            {
                "coding": "developer",  # Self-healing loop
                "infra": "devops"
            }
        )

        # Evolution loop routing
        builder.add_edge("devops", "tester")
        builder.add_edge("tester", "ux_designer")
        builder.add_edge("ux_designer", "visual_reviewer")
        builder.add_edge("visual_reviewer", "security")
        builder.add_edge("security", "performance")
        builder.add_edge("performance", "product_manager")
        
        # Product Manager routes back to Architect or END
        def _route_after_pm(state):
            # If the stage is "planning", loop back to architect
            if state.get("stage") == "planning":
                return "architect"
            return "done"

        builder.add_conditional_edges(
            "product_manager",
            _route_after_pm,
            {
                "architect": "architect",
                "done": END
            }
        )

        return builder.compile()

    # ------------------------------------------------------------------
    # Node implementations
    # ------------------------------------------------------------------

    def _node_architect(self, state: SwarmState) -> Dict[str, Any]:
        """Node for natural language blueprint planning."""
        self._log_info("=== Node: Architect ===")
        
        # Publish start event
        if hasattr(self._blackboard, "_event_publisher") and self._blackboard._event_publisher:
            self._blackboard._event_publisher.publish_sync(
                "task_status_changed",
                task_id="planning",
                status="IN_PROGRESS",
                agent_type="ARCHITECT",
            )

        desc = state["project_description"]
        name = state["project_name"]

        # Run Architect agent to generate TaskDAG structure
        self._log_info(f"Planning project layout for '{name}'...")
        dag = self._architect.plan_dag(
            project_description=desc,
            project_name=name,
            blackboard=self._blackboard
        )

        # Extract tasks from TaskDAG
        tasks_todo = []
        for node in dag.all_nodes():
            if node.agent_type == AgentType.DEVELOPER:
                tasks_todo.append({
                    "id": node.id,
                    "file_path": node.task_data.get("file_path", ""),
                    "plan": node.task_data.get("plan", {}),
                    "dependencies": list(node.dependencies)
                })

        self._log_info(f"Architect produced {len(tasks_todo)} developer task(s).")
        
        # Determine output path
        project_path = str(self._generated_projects_dir / name)
        
        # Populate initial blackboard workspace keys
        self._blackboard.write_sync("project_path", project_path, "architect")
        self._blackboard.write_sync("project_name", name, "architect")

        # Publish complete event
        if hasattr(self._blackboard, "_event_publisher") and self._blackboard._event_publisher:
            self._blackboard._event_publisher.publish_sync(
                "task_status_changed",
                task_id="planning",
                status="COMPLETED",
                agent_type="ARCHITECT",
            )

        return {
            "tasks_todo": tasks_todo,
            "project_path": project_path,
            "stage": "coding" if tasks_todo else "done"
        }

    def _node_developer(self, state: SwarmState) -> Dict[str, Any]:
        """Node for file generation."""
        self._log_info("=== Node: Developer ===")
        tasks_todo = list(state["tasks_todo"])
        tasks_done = list(state["tasks_done"])
        generated_files = dict(state["generated_files"])
        errors = list(state["errors"])

        if not tasks_todo:
            self._log_info("No tasks to execute.")
            return {"stage": "auditing"}

        # Find the next task that has all dependencies resolved (or just first for now)
        task = None
        done_ids = {t["id"] for t in tasks_done}
        for t in tasks_todo:
            deps = t.get("dependencies", [])
            # Simple check: dependencies must be done
            if all(d in done_ids for d in deps):
                task = t
                break
        
        if not task:
            # Fallback to the first task if graph dependencies are complex
            task = tasks_todo[0]

        tasks_todo.remove(task)
        file_path = task["file_path"]
        self._log_info(f"Generating file: '{file_path}' ...")

        # Set up a TaskNode for DeveloperAgent to consume
        node = TaskNode(
            id=task["id"],
            agent_type=AgentType.DEVELOPER,
            task_data={
                "file_path": file_path,
                "plan": task["plan"],
                "is_remediation": len(errors) > 0
            }
        )

        # Publish start event
        if hasattr(self._blackboard, "_event_publisher") and self._blackboard._event_publisher:
            self._blackboard._event_publisher.publish_sync(
                "task_status_changed",
                task_id=task["id"],
                status="IN_PROGRESS",
                agent_type="DEVELOPER",
            )

        # Run DeveloperAgent
        res = self._developer.run(node, self._blackboard)
        
        # Read the file content from blackboard/local system (or fallback to DeveloperAgent return dict)
        actual_path = Path(state["project_path"]) / file_path
        content = ""
        if actual_path.exists():
            try:
                content = actual_path.read_text(encoding="utf-8")
            except Exception:
                pass
        
        if not content and isinstance(res, dict):
            content = res.get(file_path, "")

        generated_files[file_path] = content
        tasks_done.append(task)
        self._log_info(f"File '{file_path}' written successfully.")

        # Sync back to blackboard so linter/auditor can find it
        self._blackboard.write_sync(f"generated_files/{file_path}", content, "developer")

        # Determine completion status
        status_val = "FAILED" if node.status.value == "FAILED" else "COMPLETED"

        # Publish end event
        if hasattr(self._blackboard, "_event_publisher") and self._blackboard._event_publisher:
            self._blackboard._event_publisher.publish_sync(
                "task_status_changed",
                task_id=task["id"],
                status=status_val,
                agent_type="DEVELOPER",
            )

        return {
            "tasks_todo": tasks_todo,
            "tasks_done": tasks_done,
            "generated_files": generated_files,
            "errors": [],  # Clear previous errors since we just ran code gen
            "stage": "coding" if tasks_todo else "auditing"
        }

    def _node_auditor(self, state: SwarmState) -> Dict[str, Any]:
        """Node for automated code reviews and vulnerability checks."""
        self._log_info("=== Node: Auditor ===")
        
        # Publish start event
        if hasattr(self._blackboard, "_event_publisher") and self._blackboard._event_publisher:
            self._blackboard._event_publisher.publish_sync(
                "task_status_changed",
                task_id="auditing",
                status="IN_PROGRESS",
                agent_type="AUDITOR",
            )

        generated_files = state["generated_files"]
        project_path = state["project_path"]
        
        self._log_info("Running static analysis, linters and security scan...")
        
        # Run AuditorAgent (uses VulnerabilityScanner, SandboxRunner, etc.)
        node = TaskNode(
            id="__auditor_check__",
            agent_type=AgentType.AUDITOR,
            task_data={"project_path": project_path}
        )
        
        # Run auditor
        self._auditor.run(node, self._blackboard)
        
        # Retrieve validation reports from blackboard (if auditor wrote them)
        audit_report = self._blackboard.read("audit_report") or {}
        
        # Mock/Analyze report for issues (self-healing triggers)
        errors = []
        issues = audit_report.get("issues", [])
        for issue in issues:
            if issue.get("severity") in ["critical", "high"]:
                self._log_error(f"Auditor found {issue.get('severity').upper()} issue in {issue.get('file')}: {issue.get('description')}")
                errors.append(issue)
 
        # Simple manual fallback scans if report empty
        for file_path, content in generated_files.items():
            if "import" in content and "syntax error" in content.lower():
                errors.append({
                    "file": file_path,
                    "description": "Potential syntax error detected in import statements.",
                    "severity": "high"
                })

        # Strict linting enforcement
        import os
        if os.environ.get("OLLASH_STRICT_LINTING") == "1":
            for file_path in generated_files.keys():
                sandbox_errs = self._blackboard.read(f"sandbox_errors/{file_path}")
                if sandbox_errs:
                    self._log_error(f"Strict Linting Error in {file_path}: {sandbox_errs}")
                    errors.append({
                        "file": file_path,
                        "description": f"Strict Linting failed: {sandbox_errs}",
                        "severity": "critical"
                    })
 
        # Determine completion status
        status_val = "FAILED" if errors else "COMPLETED"

        # Publish end event
        if hasattr(self._blackboard, "_event_publisher") and self._blackboard._event_publisher:
            self._blackboard._event_publisher.publish_sync(
                "task_status_changed",
                task_id="auditing",
                status=status_val,
                agent_type="AUDITOR",
            )

        if errors:
            self._log_info(f"Auditor flagged {len(errors)} error(s). Preparing self-healing loop...")
            # Inject a remediation task back to tasks_todo
            tasks_todo = []
            for err in errors:
                err_file = err.get("file", "")
                if err_file:
                    tasks_todo.append({
                        "id": f"heal_{err_file.replace('/', '_').replace('.', '_')}",
                        "file_path": err_file,
                        "plan": {"healing_target": err.get("description", "Fix static errors")},
                        "dependencies": []
                    })
            return {
                "errors": errors,
                "tasks_todo": tasks_todo,
                "stage": "coding"
            }
        
        self._log_info("All static and security checks passed successfully.")
        return {
            "errors": [],
            "stage": "infra"
        }

    def _node_devops(self, state: SwarmState) -> Dict[str, Any]:
        """Node for infrastructure files (Docker, DockerCompose, CI/CD)."""
        self._log_info("=== Node: DevOps ===")
        
        # Publish start event
        if hasattr(self._blackboard, "_event_publisher") and self._blackboard._event_publisher:
            self._blackboard._event_publisher.publish_sync(
                "task_status_changed",
                task_id="devops",
                status="IN_PROGRESS",
                agent_type="DEVOPS",
            )

        project_path = state["project_path"]

        self._log_info("Generating infrastructure files (Docker, CI/CD)...")
        node = TaskNode(
            id="__devops_infra__",
            agent_type=AgentType.DEVOPS,
            task_data={"project_path": project_path}
        )
        
        self._devops.run(node, self._blackboard)
        self._log_info("DevOps infra generated.")
        
        # Publish complete event
        if hasattr(self._blackboard, "_event_publisher") and self._blackboard._event_publisher:
            self._blackboard._event_publisher.publish_sync(
                "task_status_changed",
                task_id="devops",
                status="COMPLETED",
                agent_type="DEVOPS",
            )

        return {
            "stage": "done"
        }

    # ------------------------------------------------------------------
    # Routing edges
    # ------------------------------------------------------------------

    def _route_after_architect(self, state: SwarmState) -> str:
        return "coding" if state["stage"] == "coding" else "done"

    def _route_after_developer(self, state: SwarmState) -> str:
        return "coding" if state["stage"] == "coding" else "auditing"

    def _route_after_auditor(self, state: SwarmState) -> str:
        return "coding" if state["stage"] == "coding" else "infra"

    # ------------------------------------------------------------------
    # Public Execution
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return the status of the orchestrator for web API compatibility."""
        return {
            "running": getattr(self, "_is_running", False),
            "framework": "langgraph"
        }

    def run(self, project_description: str, project_name: str) -> str:
        """Executes the SwarmState graph and returns the project path."""
        self._log_info(f"Starting LangGraph execution for task: {project_description}")
        
        initial_state: SwarmState = {
            "project_description": project_description,
            "project_name": project_name,
            "generated_files": {},
            "errors": [],
            "tasks_todo": [],
            "tasks_done": [],
            "audit_report": {},
            "project_path": "",
            "stage": "planning"
        }

        # Clear blackboard for fresh run
        self._blackboard.clear()

        # Publish starting event
        if hasattr(self._blackboard, "_event_publisher") and self._blackboard._event_publisher:
            self._blackboard._event_publisher.publish_sync(
                "domain_orchestration_started",
                project_name=project_name,
                pool_size=1,
            )

        from backend.agents.orchestrators.active_orchestrators import ActiveOrchestrators
        ActiveOrchestrators.register(project_name, self)
        self._is_running = True

        try:
            # Run StateGraph
            final_state = self._graph.invoke(initial_state)
            

            # Flush all generated files to disk
            project_path = Path(final_state["project_path"])
            project_path.mkdir(parents=True, exist_ok=True)
            for file_path, file_content in final_state.get("generated_files", {}).items():
                if file_content:
                    full_path = project_path / file_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(file_content, encoding="utf-8")
            
            # Publish completion event

            if hasattr(self._blackboard, "_event_publisher") and self._blackboard._event_publisher:
                self._blackboard._event_publisher.publish_sync(
                    "domain_orchestration_completed",
                    project_name=project_name,
                )
            
            self._log_info(f"LangGraph execution completed successfully. Stage: {final_state['stage']}")
            return final_state["project_path"]
        finally:
            self._is_running = False
            ActiveOrchestrators.deregister(project_name)


    def _node_tester(self, state: SwarmState) -> Dict[str, Any]:
        self._log_info("=== Node: Tester ===")
        if self._tester:
            result = self._tester.run(state.get("generated_files", {}))
            if result.get("status") == "success":
                state["generated_files"]["tests.py"] = result.get("test_code", "")
        return state

    def _node_ux_designer(self, state: SwarmState) -> Dict[str, Any]:
        self._log_info("=== Node: UX Designer ===")
        if self._ux_designer:
            result = self._ux_designer.run(state.get("generated_files", {}))
            if result.get("status") == "success":
                self._blackboard.write_sync("ux_feedback", result.get("feedback"), "ux_designer")
        return state

    def _node_security(self, state: SwarmState) -> Dict[str, Any]:
        self._log_info("=== Node: Security Expert ===")
        if self._security:
            result = self._security.run(state.get("generated_files", {}))
            if result.get("status") == "success":
                self._blackboard.write_sync("security_feedback", result.get("feedback"), "security")
        return state

    def _node_performance(self, state: SwarmState) -> Dict[str, Any]:
        self._log_info("=== Node: Performance Optimizer ===")
        if self._performance:
            result = self._performance.run(state.get("generated_files", {}))
            if result.get("status") == "success":
                self._blackboard.write_sync("performance_feedback", result.get("feedback"), "performance")
        return state

    def _node_product_manager(self, state: SwarmState) -> Dict[str, Any]:
        self._log_info("=== Node: Product Manager ===")
        if self._product_manager:
            result = self._product_manager.run(state.get("generated_files", {}), state.get("project_description", ""))
            if result.get("status") == "success":
                new_epic = result.get("epic", "")
                self._log_info(f"PM Proposes: {new_epic}")
                state["project_description"] += f"\n\n[EVOLUTION EPIC]: {new_epic}"
                state["stage"] = "planning"
        return state

    def _node_visual_reviewer(self, state: SwarmState) -> Dict[str, Any]:
        self._log_info("=== Node: Visual Reviewer ===")
        if getattr(self, "_visual_reviewer", None):
            result = self._visual_reviewer.run(state.get("generated_files", {}), state.get("project_path", ""))
            if result.get("status") == "success":
                self._blackboard.write_sync("visual_feedback", result.get("feedback"), "visual_reviewer")
                self._log_info(f"Visual feedback saved. Screenshot: {result.get('screenshot')}")
        return state
