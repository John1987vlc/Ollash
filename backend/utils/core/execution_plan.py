"""Execution Plan tracking system for AutoAgent pipeline milestones."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json


class MilestoneStatus(str, Enum):
    """Status of a milestone in the execution plan."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class Milestone:
    """Represents a single milestone in the execution plan."""
    id: str  # e.g., "0.5", "1", "2", etc.
    name: str
    description: str
    phase_class: str  # Name of the phase class
    status: MilestoneStatus = MilestoneStatus.PENDING
    estimated_duration_seconds: int = 60
    actual_duration_seconds: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    error_message: Optional[str] = None
    output_summary: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)  # IDs of milestone dependencies

    def to_dict(self) -> Dict[str, Any]:
        """Convert milestone to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "phase_class": self.phase_class,
            "status": self.status.value,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "actual_duration_seconds": self.actual_duration_seconds,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "error_message": self.error_message,
            "output_summary": self.output_summary,
            "dependencies": self.dependencies,
        }


class ExecutionPlan:
    """
    Tracks and manages the execution of AutoAgent pipeline phases as milestones.
    
    Features:
    - Publishes initial milestone list
    - Tracks progress of each milestone
    - Updates status as phases complete
    - Records timing and errors
    - Provides progress summary
    """

    def __init__(self, project_name: str, is_existing_project: bool = False):
        self.project_name = project_name
        self.is_existing_project = is_existing_project
        self.milestones: Dict[str, Milestone] = {}
        self.creation_time = datetime.now().isoformat()
        self.completion_time: Optional[str] = None
        
    def define_milestones(self, phases: List[Any]) -> None:
        """
        Defines milestones based on the list of phases to execute.
        
        Args:
            phases: List of IAgentPhase instances to execute
        """
        # Create milestone for each phase
        for idx, phase in enumerate(phases):
            phase_name = phase.__class__.__name__
            
            # Generate milestone ID and name
            if isinstance(phase, type):
                phase_class_name = phase.__name__
            else:
                phase_class_name = phase.__class__.__name__
            
            # Map phase names to milestone info
            milestone_info = self._get_milestone_info(phase_class_name, idx)
            
            milestone = Milestone(
                id=milestone_info["id"],
                name=milestone_info["name"],
                description=milestone_info["description"],
                phase_class=phase_class_name,
                status=MilestoneStatus.PENDING,
                estimated_duration_seconds=milestone_info["estimated_duration"],
                dependencies=milestone_info["dependencies"],
            )
            
            self.milestones[milestone.id] = milestone

    def start_milestone(self, milestone_id: str) -> None:
        """Mark a milestone as started."""
        if milestone_id in self.milestones:
            self.milestones[milestone_id].status = MilestoneStatus.IN_PROGRESS
            self.milestones[milestone_id].start_time = datetime.now().isoformat()

    def complete_milestone(self, milestone_id: str, output_summary: Optional[str] = None) -> None:
        """Mark a milestone as completed."""
        if milestone_id in self.milestones:
            milestone = self.milestones[milestone_id]
            milestone.status = MilestoneStatus.COMPLETED
            milestone.end_time = datetime.now().isoformat()
            milestone.output_summary = output_summary
            
            # Calculate actual duration
            if milestone.start_time:
                start = datetime.fromisoformat(milestone.start_time)
                end = datetime.fromisoformat(milestone.end_time)
                milestone.actual_duration_seconds = int((end - start).total_seconds())

    def fail_milestone(self, milestone_id: str, error_message: str) -> None:
        """Mark a milestone as failed."""
        if milestone_id in self.milestones:
            milestone = self.milestones[milestone_id]
            milestone.status = MilestoneStatus.FAILED
            milestone.error_message = error_message
            milestone.end_time = datetime.now().isoformat()
            
            # Calculate actual duration
            if milestone.start_time:
                start = datetime.fromisoformat(milestone.start_time)
                end = datetime.fromisoformat(milestone.end_time)
                milestone.actual_duration_seconds = int((end - start).total_seconds())

    def skip_milestone(self, milestone_id: str) -> None:
        """Mark a milestone as skipped."""
        if milestone_id in self.milestones:
            self.milestones[milestone_id].status = MilestoneStatus.SKIPPED

    def get_progress(self) -> Dict[str, Any]:
        """
        Get overall progress statistics.
        
        Returns:
            Dictionary with progress metrics
        """
        total = len(self.milestones)
        completed = sum(1 for m in self.milestones.values() if m.status == MilestoneStatus.COMPLETED)
        failed = sum(1 for m in self.milestones.values() if m.status == MilestoneStatus.FAILED)
        in_progress = sum(1 for m in self.milestones.values() if m.status == MilestoneStatus.IN_PROGRESS)
        skipped = sum(1 for m in self.milestones.values() if m.status == MilestoneStatus.SKIPPED)
        pending = sum(1 for m in self.milestones.values() if m.status == MilestoneStatus.PENDING)
        
        return {
            "project_name": self.project_name,
            "is_existing_project": self.is_existing_project,
            "total_milestones": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "skipped": skipped,
            "pending": pending,
            "completion_percentage": int((completed / total * 100) if total > 0 else 0),
            "creation_time": self.creation_time,
            "is_complete": failed == 0 and (pending + in_progress == 0),
        }

    def get_milestones_list(self) -> List[Dict[str, Any]]:
        """Get list of all milestones as dictionaries."""
        return [m.to_dict() for m in self.milestones.values()]

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire execution plan to dictionary."""
        return {
            "project_name": self.project_name,
            "is_existing_project": self.is_existing_project,
            "creation_time": self.creation_time,
            "completion_time": self.completion_time,
            "progress": self.get_progress(),
            "milestones": self.get_milestones_list(),
        }

    def to_json(self) -> str:
        """Convert entire execution plan to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def mark_complete(self) -> None:
        """Mark the entire execution plan as complete."""
        self.completion_time = datetime.now().isoformat()

    def get_milestone_id_by_phase_class_name(self, phase_class_name: str) -> Optional[str]:
        """
        Retrieves the milestone ID for a given phase class name.
        """
        for milestone_id, milestone in self.milestones.items():
            if milestone.phase_class == phase_class_name:
                return milestone_id
        return None

    def _get_milestone_info(self, phase_class_name: str, phase_index: int) -> Dict[str, Any]:
        """
        Get milestone information for a specific phase.
        
        Maps phase classes to milestone definitions.
        """
        # Map of phase classes to their milestone information
        phase_milestone_map = {
            "ProjectAnalysisPhase": {
                "id": "0.5",
                "name": "Project Analysis",
                "description": "Analyze existing project structure and identify improvements",
                "estimated_duration": 45,
                "dependencies": [],
            },
            "ReadmeGenerationPhase": {
                "id": "1",
                "name": "README Generation",
                "description": "Generate comprehensive project README",
                "estimated_duration": 30,
                "dependencies": [],
            },
            "StructureGenerationPhase": {
                "id": "2",
                "name": "Structure Generation",
                "description": "Generate project directory structure",
                "estimated_duration": 20,
                "dependencies": ["1"],
            },
            "LogicPlanningPhase": {
                "id": "2.5",
                "name": "Logic Planning",
                "description": "Create detailed implementation plans",
                "estimated_duration": 60,
                "dependencies": ["1", "2"],
            },
            "StructurePreReviewPhase": {
                "id": "2.7",
                "name": "Structure Pre-Review",
                "description": "Review and refine directory structure",
                "estimated_duration": 25,
                "dependencies": ["2", "2.5"],
            },
            "EmptyFileScaffoldingPhase": {
                "id": "3",
                "name": "Empty File Scaffolding",
                "description": "Create empty project files",
                "estimated_duration": 15,
                "dependencies": ["2.7"],
            },
            "FileContentGenerationPhase": {
                "id": "4",
                "name": "File Content Generation",
                "description": "Generate content for each project file",
                "estimated_duration": 180,
                "dependencies": ["3", "2.5"],
            },
            "FileRefinementPhase": {
                "id": "5",
                "name": "File Refinement",
                "description": "Refine and improve generated files",
                "estimated_duration": 120,
                "dependencies": ["4"],
            },
            "VerificationPhase": {
                "id": "5.3",
                "name": "Verification",
                "description": "Verify file syntax and validity",
                "estimated_duration": 60,
                "dependencies": ["5"],
            },
            "CodeQuarantinePhase": {
                "id": "5.4",
                "name": "Code Quarantine",
                "description": "Isolate and analyze problematic code",
                "estimated_duration": 45,
                "dependencies": ["5.3"],
            },
            "LicenseCompliancePhase": {
                "id": "5.5",
                "name": "License Compliance",
                "description": "Ensure license compliance",
                "estimated_duration": 20,
                "dependencies": ["4"],
            },
            "DependencyReconciliationPhase": {
                "id": "5.6",
                "name": "Dependency Reconciliation",
                "description": "Reconcile project dependencies",
                "estimated_duration": 30,
                "dependencies": ["4"],
            },
            "TestGenerationExecutionPhase": {
                "id": "5.7",
                "name": "Test Generation & Execution",
                "description": "Generate and execute tests (MVP: required)",
                "estimated_duration": 150,
                "dependencies": ["4", "5"],
            },
            "ExhaustiveReviewRepairPhase": {
                "id": "5.8",
                "name": "Exhaustive Review & Repair",
                "description": "Comprehensive review and repair of code",
                "estimated_duration": 120,
                "dependencies": ["5.7"],
            },
            "FinalReviewPhase": {
                "id": "6",
                "name": "Final Review",
                "description": "Final quality review of the project",
                "estimated_duration": 60,
                "dependencies": ["5.8"],
            },
            "IterativeImprovementPhase": {
                "id": "7",
                "name": "Iterative Improvement",
                "description": "Apply iterative improvements",
                "estimated_duration": 90,
                "dependencies": ["6"],
            },
            "ContentCompletenessPhase": {
                "id": "7.3",
                "name": "Content Completeness",
                "description": "Ensure all content is complete",
                "estimated_duration": 40,
                "dependencies": ["7"],
            },
            "SeniorReviewPhase": {
                "id": "8",
                "name": "Senior Review",
                "description": "Senior architect review and approval",
                "estimated_duration": 45,
                "dependencies": ["7.3"],
            },
        }
        
        return phase_milestone_map.get(
            phase_class_name,
            {
                "id": str(phase_index),
                "name": phase_class_name,
                "description": f"Execute {phase_class_name}",
                "estimated_duration": 60,
                "dependencies": [],
            }
        )
