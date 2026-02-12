from typing import Dict, Any, List, Tuple
from pathlib import Path
import asyncio

from src.interfaces.iagent_phase import IAgentPhase
from src.agents.auto_agent_phases.phase_context import PhaseContext
from src.utils.domains.auto_generation.structure_generator import StructureGenerator # For extract_file_paths


class FileContentGenerationPhase(IAgentPhase):
    """
    Phase 4: Generates the content for all planned files, potentially in parallel.
    Handles dependency awareness and error logging to the knowledge base.
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

        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 4: Generating file contents (parallelized)...")
        self.context.event_publisher.publish("phase_start", phase="4", message="Starting parallel content generation")
        
        self.context.dependency_graph.build_from_structure(initial_structure, readme_content)
        generation_order = self.context.dependency_graph.get_generation_order()
        
        generation_tasks = []
        for file_path in generation_order:
            context_files = self.context.dependency_graph.get_context_for_file(file_path, max_depth=2)
            context_data = {
                "readme": readme_content,
                "structure": initial_structure,
                "dependencies": context_files,
                "readme_excerpt": readme_content[:1000]
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
                    # Select related files logic needs to be within AutoAgent or a service it provides
                    # For now, it remains a method that AutoAgent calls, and PhaseContext passes auto_agent as self.context.auto_agent
                    related = self.context.select_related_files(file_path, generated_files)
                    content = self.context.file_content_generator.generate_file(
                        file_path, context_for_file["readme"], context_for_file["structure"], related
                    )
                    generated_files[file_path] = content or ""
                    if content:
                        self.context.file_manager.write_file(project_root / file_path, content)
                    return (content or "", bool(content), "") # Return empty string for error if no error
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
                f"Phase 4 parallel generation: {stats['success']}/{stats['total']} files, "
                f"avg time: {stats['avg_time_per_file']:.2f}s"
            )
        except Exception as e:
            self.context.logger.error(f"Error in parallel generation: {e}. Falling back to sequential...")
            # Fallback to sequential generation
            for idx, rel_path in enumerate(file_paths, 1):
                self.context.event_publisher.publish("tool_start", tool_name="content_generation", file=rel_path, progress=f"{idx}/{len(file_paths)}")
                try:
                    related = self.context.select_related_files(rel_path, generated_files)
                    content = self.context.file_content_generator.generate_file(rel_path, readme_content, initial_structure, related)
                    generated_files[rel_path] = content or ""
                    if content:
                        self.context.file_manager.write_file(project_root / rel_path, content)
                except Exception as e2:
                    self.context.logger.error(f"Error generating {rel_path}: {e2}")
                    generated_files[rel_path] = ""
        
        self.context.event_publisher.publish("phase_complete", phase="4", message="File contents generated")
        self.context.logger.info("PHASE 4 complete.")

        return generated_files, initial_structure, file_paths
    
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