"""
Phase 4: Refinement Orchestrator
Orchestrates multi-step refinement workflows and coordinates managers
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from .feedback_refinement_manager import FeedbackRefinementManager, ParagraphContext
from .source_validator import SourceValidator


@dataclass
class RefinementWorkflow:
    """Represents a complete refinement workflow"""
    workflow_id: str
    source_id: str
    document_text: str
    created_at: str
    status: str  # "created", "analyzing", "refining", "validating", "completed"
    current_step: int = 0
    total_steps: int = 0
    paragraphs: List[Dict] = field(default_factory=list)
    refinements_applied: List[Dict] = field(default_factory=list)
    validations: List[Dict] = field(default_factory=list)
    metrics: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return asdict(self)


@dataclass
class RefinementStrategy:
    """Configuration for a refinement strategy"""
    name: str
    description: str
    critique_types: List[str]  # ['clarity', 'conciseness', 'accuracy', 'structure']
    validation_threshold: float = 0.7  # 0-1, must pass this score
    auto_apply: bool = False  # Auto-apply refinements
    iteration_limit: int = 3
    target_readability: Optional[float] = None


class RefinementOrchestrator:
    """
    Orchestrates complex refinement workflows
    
    Manages:
    1. Multi-paragraph refinements
    2. Iterative improvement cycles
    3. Validation against sources
    4. Workflow state and history
    """
    
    # Pre-defined strategies
    STRATEGIES = {
        "quick_polish": RefinementStrategy(
            name="quick_polish",
            description="Quick pass for clarity only",
            critique_types=["clarity"],
            validation_threshold=0.8,
            auto_apply=True,
            iteration_limit=1
        ),
        "comprehensive": RefinementStrategy(
            name="comprehensive",
            description="Full refinement with all checks",
            critique_types=["clarity", "conciseness", "structure"],
            validation_threshold=0.75,
            auto_apply=False,
            iteration_limit=3
        ),
        "accuracy_focused": RefinementStrategy(
            name="accuracy_focused",
            description="Emphasize accuracy and factual consistency",
            critique_types=["accuracy"],
            validation_threshold=0.85,
            auto_apply=False,
            iteration_limit=2
        ),
        "aggressive_rewrite": RefinementStrategy(
            name="aggressive_rewrite",
            description="Substantial improvements with manual review required",
            critique_types=["clarity", "conciseness", "structure"],
            validation_threshold=0.7,
            auto_apply=False,
            iteration_limit=5,
            target_readability=80.0
        )
    }
    
    def __init__(self, workspace_path: str = "knowledge_workspace"):
        self.workspace = Path(workspace_path)
        self.workflows_dir = self.workspace / "workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        
        self.refinement_manager = FeedbackRefinementManager(workspace_path)
        self.validator = SourceValidator(workspace_path)
        
        self.active_workflows: Dict[str, RefinementWorkflow] = {}
        self._load_active_workflows()
    
    def _load_active_workflows(self):
        """Load any active workflows from disk"""
        if self.workflows_dir.exists():
            for workflow_file in self.workflows_dir.glob("*.json"):
                try:
                    with open(workflow_file) as f:
                        data = json.load(f)
                        # Simple deserialization (full version would handle nested objects)
                        self.active_workflows[data["workflow_id"]] = data
                except Exception as e:
                    print(f"Error loading workflow: {e}")
    
    def _save_workflow(self, workflow: RefinementWorkflow):
        """Persist workflow state"""
        workflow_file = self.workflows_dir / f"{workflow.workflow_id}.json"
        with open(workflow_file, 'w') as f:
            json.dump(workflow.to_dict(), f, indent=2)
        self.active_workflows[workflow.workflow_id] = workflow
    
    def create_workflow(
        self,
        workflow_id: str,
        source_id: str,
        document_text: str,
        strategy: str = "comprehensive"
    ) -> RefinementWorkflow:
        """
        Create a new refinement workflow
        
        Args:
            workflow_id: Unique identifier for workflow
            source_id: Source document ID
            document_text: Full text to refine
            strategy: Name of refinement strategy to use
        
        Returns:
            RefinementWorkflow object
        """
        if workflow_id in self.active_workflows:
            raise ValueError(f"Workflow {workflow_id} already exists")
        
        # Register source
        self.validator.register_source(source_id, document_text)
        
        # Extract paragraphs
        paragraphs = self.refinement_manager.extract_paragraphs(document_text, source_id)
        
        # Create workflow
        workflow = RefinementWorkflow(
            workflow_id=workflow_id,
            source_id=source_id,
            document_text=document_text,
            created_at=datetime.now().isoformat(),
            status="created",
            total_steps=len(paragraphs) * 3,  # analyze, critique, validate for each
            paragraphs=[{
                "index": p.index,
                "text": p.text,
                "original_text": p.original_text,
                "readability": p.readability_score,
                "word_count": p.word_count
            } for p in paragraphs]
        )
        
        self._save_workflow(workflow)
        return workflow
    
    def analyze_document(self, workflow_id: str) -> Dict:
        """
        Analyze document and identify refinement candidates
        
        Returns:
            Dict with analysis results and paragraph recommendations
        """
        workflow = self.active_workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        analysis = {
            "total_paragraphs": len(workflow.paragraphs),
            "paragraphs_needing_improvement": [],
            "readability_distribution": self._calculate_distribution(workflow),
            "average_readability": self._calculate_average_readability(workflow)
        }
        
        # Identify low-readability paragraphs
        for para in workflow.paragraphs:
            if para["readability"] < 50:
                analysis["paragraphs_needing_improvement"].append({
                    "index": para["index"],
                    "readability": para["readability"],
                    "word_count": para["word_count"]
                })
        
        return analysis
    
    def refine_workflow(
        self,
        workflow_id: str,
        strategy_name: str = "comprehensive",
        paragraph_indices: Optional[List[int]] = None
    ) -> Dict:
        """
        Execute refinement workflow
        
        Args:
            workflow_id: Workflow to refine
            strategy_name: Strategy to use
            paragraph_indices: Specific paragraphs to refine (None = all)
        
        Returns:
            Dict with refinement results
        """
        workflow = self.active_workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        strategy = self.STRATEGIES.get(strategy_name)
        if not strategy:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        
        workflow.status = "refining"
        
        results = {
            "workflow_id": workflow_id,
            "strategy": strategy_name,
            "refinements": [],
            "validations": [],
            "summary": {}
        }
        
        # Determine which paragraphs to refine
        target_indices = paragraph_indices or list(range(len(workflow.paragraphs)))
        
        for idx in target_indices:
            if idx < len(workflow.paragraphs):
                para_data = workflow.paragraphs[idx]
                
                # Perform refinements based on strategy
                para_results = self._refine_paragraph(
                    workflow_id,
                    idx,
                    para_data,
                    strategy
                )
                
                results["refinements"].append(para_results)
        
        # Validate all refinements
        workflow.status = "validating"
        validation_summary = self._validate_refinements(workflow_id, results["refinements"])
        results["validations"] = validation_summary
        
        # Update workflow
        workflow.status = "completed"
        workflow.refinements_applied = results["refinements"]
        workflow.validations = results["validations"]
        workflow.metrics = self._calculate_workflow_metrics(workflow)
        
        self._save_workflow(workflow)
        
        return results
    
    def _refine_paragraph(
        self,
        workflow_id: str,
        para_index: int,
        para_data: Dict,
        strategy: RefinementStrategy
    ) -> Dict:
        """Refine a single paragraph"""
        result = {
            "paragraph_index": para_index,
            "original_text": para_data["text"],
            "critiques": [],
            "refinement": para_data["text"],  # Start with original
            "iteration": 0
        }
        
        current_text = para_data["text"]
        
        # Apply multiple critique types
        for critique_type in strategy.critique_types:
            critique = self.refinement_manager.generate_critique(
                ParagraphContext(
                    index=para_index,
                    text=current_text,
                    original_text=para_data["original_text"],
                    source_id=self.active_workflows[workflow_id].source_id
                ),
                critique_type
            )
            
            result["critiques"].append({
                "type": critique_type,
                "feedback": critique
            })
        
        # Simulate refinement (in real impl, would use LLM)
        if strategy.auto_apply:
            refined = self._apply_simple_refinement(current_text, strategy)
            result["refinement"] = refined
        
        return result
    
    def _apply_simple_refinement(self, text: str, strategy: RefinementStrategy) -> str:
        """
        Apply simple heuristic refinements
        
        In production, this would call an LLM for real refinements
        """
        refined = text
        
        # Remove duplicate spaces
        refined = " ".join(refined.split())
        
        # Remove common filler words if conciseness in strategy
        if "conciseness" in strategy.critique_types:
            fillers = ['very', 'really', 'actually', 'basically']
            for filler in fillers:
                refined = refined.replace(f" {filler} ", " ")
        
        return refined
    
    def _validate_refinements(
        self,
        workflow_id: str,
        refinements: List[Dict]
    ) -> List[Dict]:
        """Validate all refinements"""
        workflow = self.active_workflows[workflow_id]
        validation_results = []
        
        for ref in refinements:
            result = self.validator.validate_refinement(
                original_text=ref["original_text"],
                refined_text=ref["refinement"],
                source_id=workflow.source_id,
                validation_type="full"
            )
            
            validation_results.append({
                "paragraph_index": ref["paragraph_index"],
                "is_valid": result.is_valid,
                "score": result.validation_score,
                "issues": len(result.issues)
            })
        
        return validation_results
    
    def get_workflow_status(self, workflow_id: str) -> Dict:
        """Get current status of a workflow"""
        workflow = self.active_workflows.get(workflow_id)
        if not workflow:
            return {"error": f"Workflow {workflow_id} not found"}
        
        return {
            "workflow_id": workflow_id,
            "status": workflow.status,
            "created_at": workflow.created_at,
            "total_paragraphs": len(workflow.paragraphs),
            "refinements_applied": len(workflow.refinements_applied),
            "validations_passed": len([v for v in workflow.validations if v.get("is_valid")]),
            "metrics": workflow.metrics
        }
    
    def _calculate_distribution(self, workflow: RefinementWorkflow) -> Dict:
        """Calculate readability distribution"""
        scores = [p["readability"] for p in workflow.paragraphs]
        return {
            "min": min(scores) if scores else 0,
            "max": max(scores) if scores else 0,
            "avg": sum(scores) / len(scores) if scores else 0
        }
    
    def _calculate_average_readability(self, workflow: RefinementWorkflow) -> float:
        """Calculate average readability"""
        if not workflow.paragraphs:
            return 0.0
        return sum(p["readability"] for p in workflow.paragraphs) / len(workflow.paragraphs)
    
    def _calculate_workflow_metrics(self, workflow: RefinementWorkflow) -> Dict:
        """Calculate final metrics for workflow"""
        return {
            "total_paragraphs": len(workflow.paragraphs),
            "refined": len(workflow.refinements_applied),
            "validated": len(workflow.validations),
            "passed_validation": len([v for v in workflow.validations if v.get("is_valid")]),
            "completion_time": (
                datetime.fromisoformat(workflow.created_at)
            ).isoformat() if workflow.created_at else None
        }
    
    def list_workflows(self) -> List[Dict]:
        """List all workflows"""
        return [
            {
                "workflow_id": wf.workflow_id if hasattr(wf, 'workflow_id') else wf["workflow_id"],
                "status": wf.status if hasattr(wf, 'status') else wf["status"],
                "created_at": wf.created_at if hasattr(wf, 'created_at') else wf["created_at"],
                "source_id": wf.source_id if hasattr(wf, 'source_id') else wf["source_id"]
            }
            for wf in self.active_workflows.values()
        ]
    
    def export_workflow_document(self, workflow_id: str, format: str = "text") -> str:
        """
        Export refined document
        
        Args:
            workflow_id: Workflow to export
            format: 'text', 'markdown', 'html'
        
        Returns:
            Formatted document text
        """
        workflow = self.active_workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        if format == "markdown":
            return self._export_markdown(workflow)
        elif format == "html":
            return self._export_html(workflow)
        else:
            return self._export_text(workflow)
    
    def _export_text(self, workflow: RefinementWorkflow) -> str:
        """Export as plain text"""
        lines = [f"Refined Document: {workflow.workflow_id}",
                f"Generated: {workflow.created_at}",
                "=" * 50, ""]
        
        for ref in workflow.refinements_applied:
            lines.append(ref["refinement"])
            lines.append("")
        
        return "\n".join(lines)
    
    def _export_markdown(self, workflow: RefinementWorkflow) -> str:
        """Export as markdown"""
        lines = [f"# {workflow.workflow_id}",
                f"*Generated: {workflow.created_at}*",
                ""]
        
        for ref in workflow.refinements_applied:
            lines.append(ref["refinement"])
            lines.append("")
        
        return "\n".join(lines)
    
    def _export_html(self, workflow: RefinementWorkflow) -> str:
        """Export as HTML"""
        html_parts = [
            f"<html><head><title>{workflow.workflow_id}</title></head><body>",
            f"<h1>{workflow.workflow_id}</h1>",
            f"<p><em>Generated: {workflow.created_at}</em></p>"
        ]
        
        for ref in workflow.refinements_applied:
            html_parts.append(f"<p>{ref['refinement']}</p>")
        
        html_parts.append("</body></html>")
        return "".join(html_parts)
