import difflib
import re
from pathlib import Path
from typing import Dict, List, Any

from colorama import Fore, Style

from backend.utils.core.file_manager import FileManager
from backend.utils.core.confirmation_manager import ConfirmationManager
from backend.utils.core.tool_decorator import ollash_tool

class FileSystemTools:
    def __init__(self, project_root: Path, file_manager: FileManager, logger: Any, tool_executor: ConfirmationManager):
        self.project_root = project_root
        self.files = file_manager
        self.logger = logger
        self.tool_executor = tool_executor
        self._read_count: Dict[str, int] = {}

    @ollash_tool(
        name="read_file",
        description="Reads the content of a specified file. Can read specific line ranges for large files.",
        parameters={
            "path": {"type": "string", "description": "The path to the file to read."},
            "start_line": {"type": "integer", "description": "Optional: Starting line number (1-based) to read."},
            "end_line": {"type": "integer", "description": "Optional: Ending line number (1-based) to read."}
        },
        toolset_id="file_system_tools",
        agent_types=["code"],
        required=["path"]
    )
    def read_file(self, path: str, offset: int = 0, limit: int = 50):
        """Read a single file"""
        full = self.project_root / path
        if not full.exists():
            self.logger.warning(f"File not found: {path}")
            return {"ok": False, "error": "not_found", "path": path}

        try:
            content = full.read_text(encoding="utf-8")
            lines = content.splitlines()
            self._read_count[path] = self._read_count.get(path, 0) + 1

            result = {
                "ok": True,
                "path": path,
                "offset": offset,
                "limit": limit,
                "total_lines": len(lines),
                "content": "\n".join(lines[offset:offset + limit]),
                "reads": self._read_count[path]
            }
            
            self.logger.info(f"📖 Read: {path} ({len(lines)} lines)")
            return result
            
        except Exception as e:
            self.logger.error(f"Error reading {path}: {e}", e)
            return {"ok": False, "error": str(e), "path": path}

    @ollash_tool(
        name="read_files",
        description="Reads the content of multiple specified files. Use this for reading several files efficiently.",
        parameters={
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "A list of paths to the files to read."
            }
        },
        toolset_id="file_system_tools",
        agent_types=["code"],
        required=["paths"]
    )
    def read_files(self, files: List[Dict]):
        """Read multiple files at once"""
        self.logger.info(f"📚 Reading {len(files)} file(s)...")
        
        results = []
        for file_spec in files:
            path = file_spec["path"]
            offset = file_spec.get("offset", 0)
            limit = file_spec.get("limit", 50)
            
            result = self.read_file(path, offset, limit)
            results.append(result)
        
        success_count = sum(1 for r in results if r.get("ok"))
        self.logger.info(f"✅ Read {success_count}/{len(files)} files successfully")
        
        return {
            "ok": True,
            "files_read": success_count,
            "total_files": len(files),
            "results": results
        }

    @ollash_tool(
        name="write_file",
        description="Writes content to a specified file. Requires user confirmation if it modifies an existing file.",
        parameters={
            "path": {"type": "string", "description": "The path to the file to write."},
            "content": {"type": "string", "description": "The content to write to the file."},
            "reason": {"type": "string", "description": "The reason for writing this file, for user confirmation."}
        },
        toolset_id="file_system_tools",
        agent_types=["code"],
        required=["path", "content", "reason"]
    )
    def write_file(self, path: str, content: str, reason: str = ""):
        """Write file with user confirmation, with dynamic approval based on changes."""
        full_path = self.project_root / path
        file_exists = full_path.exists()
        current_content = full_path.read_text(encoding="utf-8") if file_exists else ""
        
        # Calculate diff if file exists (skip for large files > 5MB)
        max_diff_size = 5 * 1024 * 1024  # 5MB threshold
        if file_exists and len(current_content) < max_diff_size and len(content) < max_diff_size:
            diff = list(difflib.unified_diff(
                current_content.splitlines(),
                content.splitlines(),
                lineterm=""
            ))
            lines_changed = sum(1 for line in diff if line.startswith('+') or line.startswith('-'))
        elif file_exists:
            # For large files, estimate based on length difference
            lines_changed = abs(len(content.splitlines()) - len(current_content.splitlines()))
            self.logger.info(f"Skipping diff for large file {path} (>{max_diff_size // (1024*1024)}MB)")
        else:
            lines_changed = len(content.splitlines())
        
        # Check against critical paths patterns
        is_critical_file = False
        for pattern in self.tool_executor.critical_paths_patterns:
            if re.match(pattern, path):
                is_critical_file = True
                break

        # Decision logic for confirmation
        if is_critical_file: # Always force human gate if critical file is modified or created
            return self.tool_executor.require_human_gate(
                action_description=f"Attempting to modify/create critical file '{path}'. Manual approval required.",
                reason="Changes to critical configuration/system files detected."
            )
        elif self.tool_executor.auto_confirm_minor_writes and lines_changed <= self.tool_executor.write_auto_confirm_lines_threshold:
            self.logger.info(f"Auto-confirming minor file write to '{path}' (lines changed: {lines_changed}).")
            # Proceed with write without asking user
        else:
            # Fallback to manual confirmation
            if not self.tool_executor._ask_confirmation("write_file", {
                "path": path,
                "content": content,
                "reason": reason,
                "lines_changed": lines_changed
            }):
                self.logger.info(f"User cancelled write: {path}")
                return {
                    "ok": False,
                    "error": "user_cancelled",
                    "message": "User cancelled the file write operation"
                }
        
        # Original write logic
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            
            self.logger.info(f"✅ File written: {path}")
            return {"ok": True, "path": path, "chars": len(content)}
            
        except Exception as e:
            self.logger.error(f"Error writing {path}: {e}", e)
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="delete_file",
        description="Deletes a specified file. Requires user confirmation.",
        parameters={
            "path": {"type": "string", "description": "The path to the file to delete."},
            "reason": {"type": "string", "description": "The reason for deleting this file, for user confirmation."}
        },
        toolset_id="file_system_tools",
        agent_types=["code"],
        required=["path", "reason"]
    )
    def delete_file(self, path: str, reason: str = ""):
        """Delete file with user confirmation"""
        full = self.project_root / path
        
        if not full.exists():
            self.logger.warning(f"File not found for deletion: {path}")
            return {"ok": False, "error": "not_found", "path": path}
        
        if not self.tool_executor._ask_confirmation("delete_file", {"path": path, "reason": reason}):
            self.logger.info(f"User cancelled deletion: {path}")
            return {
                "ok": False,
                "error": "user_cancelled",
                "message": "User cancelled the file deletion"
            }
        
        try:
            full.unlink()
            self.logger.info(f"✅ File deleted: {path}")
            return {"ok": True, "path": path, "deleted": True}
        except Exception as e:
            self.logger.error(f"Error deleting {path}: {e}", e)
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="file_diff",
        description="Compares two files or a file with provided content and returns the differences.",
        parameters={
            "path1": {"type": "string", "description": "Path to the first file."},
            "path2": {"type": "string", "description": "Optional: Path to the second file."},
            "inline_content": {"type": "string", "description": "Optional: Content to compare with path1 if path2 is not provided."}
        },
        toolset_id="file_system_tools",
        agent_types=["code"],
        required=["path1"]
    )
    def file_diff(self, path: str, new_content: str):
        """Show diff before writing a file."""
        full = self.project_root / path
        old = full.read_text(encoding="utf-8") if full.exists() else ""
        diff = list(difflib.unified_diff(
            old.splitlines(),
            new_content.splitlines(),
            lineterm="",
            fromfile=f"{path} (current)",
            tofile=f"{path} (proposed)"
        ))
        
        if diff:
            self.logger.info(f"📊 DIFF for {path}")
            for line in diff[:50]:
                if line.startswith('+'):
                    self.logger.debug(f"{Fore.GREEN}{line}{Style.RESET_ALL}")
                elif line.startswith('-'):
                    self.logger.debug(f"{Fore.RED}{line}{Style.RESET_ALL}")
                else:
                    self.logger.debug(f"{Fore.WHITE}{line}{Style.RESET_ALL}")
            if len(diff) > 50:
                self.logger.debug(f"{Fore.YELLOW}... ({len(diff) - 50} more lines){Style.RESET_ALL}")
        
        return {
            "ok": True,
            "path": path,
            "diff_lines": diff[:200],
            "total_diff": len(diff)
        }

    @ollash_tool(
        name="summarize_file",
        description="Summarizes the content of a single file. Useful for getting a high-level understanding.",
        parameters={
            "path": {"type": "string", "description": "The path to the file to summarize."}
        },
        toolset_id="file_system_tools",
        agent_types=["code"],
        required=["path"]
    )
    def summarize_file(self, path: str):
        """Summarize a single file"""
        full = self.project_root / path
        if not full.exists():
            return {"ok": False, "error": "not_found"}
        
        try:
            content = full.read_text(encoding="utf-8")
            summary = {
                "ok": True,
                "path": path,
                "lines": len(content.splitlines()),
                "functions": content.count("def "),
                "classes": content.count("class "),
                "imports": content.count("import "),
                "size_bytes": len(content.encode('utf-8'))
            }
            
            self.logger.info(f"📊 {path}: "
                  f"{summary['lines']} lines, "
                  f"{summary['functions']} functions, "
                  f"{summary['classes']} classes")
            
            return summary
        except Exception as e:
            self.logger.error(f"Error summarizing {path}: {e}", e)
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="summarize_files",
        description="Summarizes the content of multiple files. Useful for getting a high-level understanding of several files.",
        parameters={
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "A list of paths to the files to summarize."
            }
        },
        toolset_id="file_system_tools",
        agent_types=["code"],
        required=["paths"]
    )
    def summarize_files(self, paths: List[str]):
        """Summarize multiple files at once"""
        self.logger.info(f"📊 Summarizing {len(paths)} file(s)...")
        
        results = []
        for path in paths:
            result = self.summarize_file(path)
            results.append(result)
        
        success_count = sum(1 for r in results if r.get("ok"))
        total_lines = sum(r.get("lines", 0) for r in results if r.get("ok"))
        
        self.logger.info(f"✅ Summarized {success_count}/{len(paths)} files "
              f"({total_lines} total lines)")
        
        return {
            "ok": True,
            "files_summarized": success_count,
            "total_files": len(paths),
            "total_lines": total_lines,
            "summaries": results
        }

    @ollash_tool(
        name="list_directory",
        description="Lists the contents of a specified directory. Can include hidden files and be recursive.",
        parameters={
            "path": {"type": "string", "description": "The path to the directory to list."},
            "recursive": {"type": "boolean", "description": "Optional: Whether to list contents recursively. Defaults to false."},
            "include_hidden": {"type": "boolean", "description": "Optional: Whether to include hidden files. Defaults to false."}
        },
        toolset_id="file_system_tools",
        agent_types=["code"],
        required=["path"]
    )
    def list_directory(self, path: str, recursive: bool = False):
        """List directory contents"""
        try:
            target = self.project_root / path
            if not target.exists():
                return {"ok": False, "error": "not_found"}
            
            if recursive:
                files = [str(p.relative_to(self.project_root)) 
                        for p in target.rglob("*") if p.is_file()]
            else:
                files = [str(p.relative_to(self.project_root)) 
                        for p in target.iterdir()]
            
            self.logger.info(f"📁 {path}: {len(files)} items")
            for f in files[:10]:
                self.logger.debug(f"  • {f}")
            if len(files) > 10:
                self.logger.debug(f"  ... and {len(files) - 10} more")
            
            return {
                "ok": True,
                "path": path,
                "items": files,
                "count": len(files)
            }
        except Exception as e:
            self.logger.error(f"List directory error: {e}", e)
            return {"ok": False, "error": str(e)}