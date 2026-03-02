# Public API — imports from reorganised sub-packages.
# All names below remain importable from this module for backward compatibility.

from .planning.project_planner import ProjectPlanner
from .generation.structure_generator import StructureGenerator
from .generation.enhanced_file_content_generator import EnhancedFileContentGenerator
from .review.file_completeness_checker import FileCompletenessChecker
from .review.project_reviewer import ProjectReviewer
from .utilities.file_refiner import FileRefiner
from .utilities.prompt_templates import AutoGenPrompts
from .utilities.project_type_detector import ProjectTypeDetector, ProjectTypeInfo

# FileContentGenerator: deprecated — use EnhancedFileContentGenerator instead
from .generation.file_content_generator import FileContentGenerator

__all__ = [
    "ProjectPlanner",
    "StructureGenerator",
    "EnhancedFileContentGenerator",
    "FileContentGenerator",  # deprecated
    "FileRefiner",
    "FileCompletenessChecker",
    "ProjectReviewer",
    "AutoGenPrompts",
    "ProjectTypeDetector",
    "ProjectTypeInfo",
]
