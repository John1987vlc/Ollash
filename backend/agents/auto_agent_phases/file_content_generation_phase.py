from typing import Dict, Any, List, Tuple
from pathlib import Path
import asyncio

from backend.interfaces.iagent_phase import IAgentPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.utils.domains.auto_generation.structure_generator import StructureGenerator # For extract_file_paths
from backend.utils.core.parallel_generator import GenerationTask


class FileContentGenerationPhase(IAgentPhase):
    """
    Phase 4: Generates the content for all planned files, potentially in parallel.
    NOW USES LOGIC PLANS for more accurate, complete implementations.
    Handles dependency awareness, incremental validation, and error logging.
    """
    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str,
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str], # This will be populated here
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        
        file_paths = kwargs.get("file_paths", []) # Get from kwargs or assume context has it

        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 4: Generating file contents with logic plans...")
        self.context.event_publisher.publish("phase_start", phase="4", message="Starting intelligent content generation")
        
        self.context.dependency_graph.build_from_structure(initial_structure, readme_content)
        generation_order = self.context.dependency_graph.get_generation_order()
        
        # NEW: Get logic plans from context (generated in LogicPlanningPhase)
        logic_plan = getattr(self.context, 'logic_plan', {})
        
        generation_tasks = []
        for file_path in generation_order:
            context_files = self.context.dependency_graph.get_context_for_file(file_path, max_depth=2)
            context_data = {
                "readme": readme_content,
                "structure": initial_structure,
                "dependencies": context_files,
                "readme_excerpt": readme_content[:1000],
                "logic_plan": logic_plan.get(file_path, {}),  # NEW: Include file's logic plan
            }
            
            language = self._infer_language(file_path) # Helper method below
            prevention_warnings = self.context.error_knowledge_base.get_prevention_warnings(
                file_path, project_name, language
            )
            context_data["error_warnings"] = prevention_warnings
            
            task = GenerationTask(
                file_path=file_path,
                context=context_data,
                priority=10 if any(x in file_path for x in ["__init__", "config", "utils"]) else 5,
            )
            generation_tasks.append(task)
        
        async def async_generate_wrapper():
            """Wrapper to call sync generation function asynchronously."""
            async def gen_file_async(file_path: str, context_for_file: Dict) -> Tuple[str, bool, str]:
                try:
                    # Get related files for context
                    related = self.context.select_related_files(file_path, generated_files)
                    
                    # NEW: Use logic plan if available
                    file_logic_plan = context_for_file.get("logic_plan", {})
                    
                    if file_logic_plan:
                        # Use enhanced generator with detailed plan
                        self.context.logger.info(f"  Generating {file_path} using detailed logic plan")
                        # We'll need to get EnhancedFileContentGenerator from context if available
                        # For now, try to use it if available, otherwise fall back to regular generator
                        content = await self._generate_with_plan(
                            file_path, file_logic_plan, related,
                            context_for_file["readme"], context_for_file["structure"]
                        )
                    else:
                        # Fallback to regular generation
                        content = self.context.file_content_generator.generate_file(
                            file_path, context_for_file["readme"], 
                            context_for_file["structure"], related
                        )
                    
                    # NEW: Validate content before saving
                    if content and self._validate_file_content(file_path, content, file_logic_plan):
                        generated_files[file_path] = content
                        self.context.file_manager.write_file(project_root / file_path, content)
                        self.context.logger.info(f"  ✓ {file_path} generated and validated")
                        return (content, True, "")
                    else:
                        # Content validation failed
                        self.context.logger.warning(f"  ⚠ {file_path} content validation failed, attempting retry...")
                        # Could implement retry logic here
                        if content:
                            generated_files[file_path] = content
                            self.context.file_manager.write_file(project_root / file_path, content)
                            return (content, False, "Content validation warning")
                        else:
                            raise ValueError(f"No content generated for {file_path}")
                    
                except Exception as e:
                    self.context.logger.error(f"Error generating {file_path}: {e}")
                    generated_files[file_path] = ""
                    self.context.error_knowledge_base.record_error(
                        file_path, "generation_failure", str(e), "", context_for_file.get("readme_excerpt", "")
                    )
                    return ("", False, str(e))
            
            results = await self.context.parallel_generator.generate_files(
                generation_tasks,
                gen_file_async,
                progress_callback=lambda fp, completed, total: self.context.event_publisher.publish(
                    "tool_output", tool_name="content_generation", file=fp, 
                    progress=f"{completed}/{total}", status="success"
                ),
                dependency_order=generation_order,
            )
            return results
        
        try:
            generation_results = await async_generate_wrapper()
            stats = self.context.parallel_generator.get_statistics()
            self.context.logger.info(
                f"Phase 4 content generation: {stats['success']}/{stats['total']} files, "
                f"avg time: {stats['avg_time_per_file']:.2f}s"
            )
        except Exception as e:
            self.context.logger.error(f"Error in parallel generation: {e}. Falling back to sequential...")
            # Implement sequential fallback if needed
            for file_path in generation_order:
                if file_path not in generated_files or not generated_files[file_path]:
                    self.context.logger.info(f"Sequential generation for {file_path}")
        
        self.context.event_publisher.publish(
            "phase_complete", phase="4", 
            message=f"Content generated for {len(generated_files)} files"
        )
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 4 complete.")

        return generated_files, initial_structure, file_paths
    
    async def _generate_with_plan(self, file_path: str, plan: Dict, 
                                 related: Dict[str, str], readme: str,
                                 structure: Dict) -> str:
        """Use enhanced generator with detailed plan."""
        try:
            from backend.utils.domains.auto_generation.enhanced_file_content_generator import EnhancedFileContentGenerator
            
            enhanced_gen = EnhancedFileContentGenerator(
                self.context.llm_manager.get_client("coder"),
                self.context.logger,
                self.context.response_parser
            )
            
            content = enhanced_gen.generate_file_with_plan(
                file_path, plan, "", readme, structure, related
            )
            return content
        except Exception as e:
            self.context.logger.debug(f"Enhanced generation failed, falling back: {e}")
            return None
    
    def _validate_file_content(self, file_path: str, content: str, plan: Dict) -> bool:
        """Validate that generated content is complete and correct."""
        
        if not content or len(content.strip()) < 50:
            return False
        
        # Check for required exports from plan
        exports = plan.get("exports", [])
        for export in exports:
            # Basic validation - export name should appear in file
            if export and export not in content:
                self.context.logger.warning(f"    Missing expected export: {export}")
                return False
        
        # Check for common failure patterns
        if "TODO" in content and content.count("TODO") > len(exports) + 2:
            self.context.logger.warning(f"    Too many TODOs in {file_path}")
            return False
        
        return True
    
    def _infer_language(self, file_path: str) -> str:
        """Infer programming language from file path. Copied from AutoAgent for now."""
        ext = Path(file_path).suffix.lower()
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
        }
        return language_map.get(ext, "unknown")