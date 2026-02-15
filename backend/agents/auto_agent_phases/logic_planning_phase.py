"""Logic Planning Phase - Creates detailed implementation plans for each file."""

from typing import Dict, Any, List, Tuple
from pathlib import Path
import json

from backend.interfaces.iagent_phase import IAgentPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


class LogicPlanningPhase(IAgentPhase):
    """
    Phase 2.5 (between Structure and FileContentGeneration):
    Creates a detailed implementation plan for each file, specifying:
    - What the file should do
    - Key functions/classes to implement
    - Dependencies and interactions
    - Validation criteria
    
    This plan is then used by FileContentGenerationPhase to generate accurate content.
    """
    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str,
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str],
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        
        file_paths = kwargs.get("file_paths", [])
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2.5: Creating detailed logic plans for {len(file_paths)} files...")
        self.context.event_publisher.publish("phase_start", phase="2.5", message="Creating logic implementation plans")

        logic_plan = {}
        
        # Group files by type/purpose
        files_by_category = self._categorize_files(file_paths)
        
        for category, files in files_by_category.items():
            self.context.logger.info(f"  Planning {category}: {len(files)} files")
            
            # Generate a plan for this category
            category_plan = await self._plan_category(
                category, files, project_description, readme_content, initial_structure
            )
            
            for file_path, plan in category_plan.items():
                logic_plan[file_path] = plan

        # Save plan to disk
        plan_file = project_root / "IMPLEMENTATION_PLAN.json"
        self.context.file_manager.write_file(plan_file, json.dumps(logic_plan, indent=2))
        generated_files["IMPLEMENTATION_PLAN.json"] = json.dumps(logic_plan, indent=2)
        
        # Store in context for FileContentGenerationPhase to use
        self.context.logic_plan = logic_plan
        
        self.context.event_publisher.publish(
            "phase_complete", phase="2.5", 
            message=f"Logic plan created for {len(logic_plan)} files"
        )
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2.5 complete: Plans created for {len(logic_plan)} files")

        return generated_files, initial_structure, file_paths

    def _categorize_files(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """Group files by their category (config, main logic, utilities, tests, etc)."""
        categories = {
            "config": [],
            "main": [],
            "utils": [],
            "tests": [],
            "docs": [],
            "web": [],
            "other": [],
        }
        
        for file_path in file_paths:
            if any(x in file_path for x in ["config", "settings", "env"]):
                categories["config"].append(file_path)
            elif any(x in file_path for x in ["test", "spec"]):
                categories["tests"].append(file_path)
            elif any(x in file_path for x in ["utils", "helper", "lib"]):
                categories["utils"].append(file_path)
            elif any(x in file_path for x in [".html", ".css", ".js", "web", "static"]):
                categories["web"].append(file_path)
            elif any(x in file_path for x in [".md", "README", "LICENSE"]):
                categories["docs"].append(file_path)
            elif any(x in file_path for x in ["main", "app", "server", "index", "__main__"]):
                categories["main"].append(file_path)
            else:
                categories["other"].append(file_path)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    async def _plan_category(self, category: str, files: List[str], 
                            project_description: str, readme_content: str,
                            initial_structure: Dict[str, Any]) -> Dict[str, Dict]:
        """Create detailed plans for files in a category."""
        
        category_context = f"""
## Project Context
Description: {project_description}

## Files in this category:
{chr(10).join(f'- {f}' for f in files)}

## Create detailed implementation plans for EACH file above.
Specify for each file:
1. PURPOSE: What this file should do
2. EXPORTS: Key functions/classes/variables it should export
3. IMPORTS: What dependencies it needs
4. MAIN_LOGIC: Step-by-step implementation details
5. VALIDATION: How to verify it works correctly
6. DEPENDENCIES: Which other files it depends on

Format the response as JSON with file paths as keys.
"""

        system_prompt = (
            "You are an expert architect. Create detailed, actionable implementation plans "
            "for code files. Each plan should be specific enough that a developer can implement it step-by-step."
        )

        try:
            response_data, _ = self.context.llm_manager.get_client("planner").chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": category_context},
                ],
                options_override={"temperature": 0.5},  # Correctly pass temperature
            )
            
            # Parse the response
            response_text = response_data.get("content", "")
            
            # Try to extract JSON from response
            import json
            import re
            
            # Look for JSON block
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                plans = json.loads(json_match.group())
            else:
                # Fallback: create basic plans for each file
                plans = self._create_basic_plans(files, category)
            
            return plans
            
        except Exception as e:
            self.context.logger.error(f"Error planning category {category}: {e}")
            # Return basic plans as fallback
            return self._create_basic_plans(files, category)

    def _create_basic_plans(self, files: List[str], category: str) -> Dict[str, Dict]:
        """Create basic fallback plans when LLM planning fails."""
        plans = {}
        
        for file_path in files:
            basename = Path(file_path).name
            ext = Path(file_path).suffix
            
            # Basic plan based on file type
            if category == "config":
                purpose = "Configuration and settings"
                exports = ["Configuration object", "get_config()"]
            elif category == "main":
                purpose = "Main application entry point"
                exports = ["main()", "Application class"]
            elif category == "utils":
                purpose = "Utility functions and helpers"
                exports = ["Helper functions for common tasks"]
            elif category == "tests":
                purpose = "Unit tests for corresponding module"
                exports = ["Test functions"]
            elif category == "web":
                if ext == ".js":
                    purpose = "JavaScript logic and interactivity"
                    exports = ["Functions", "Classes"]
                elif ext == ".css":
                    purpose = "Styling and layout"
                    exports = ["CSS classes", "Responsive design"]
                elif ext == ".html":
                    purpose = "HTML page structure"
                    exports = ["Semantic HTML"]
            else:
                purpose = "Core functionality"
                exports = ["Main functions/classes"]
            
            plans[file_path] = {
                "purpose": purpose,
                "exports": exports,
                "imports": [],
                "main_logic": ["Implement core functionality as designed"],
                "validation": ["Code should execute without errors"],
                "dependencies": [],
            }
        
        return plans
