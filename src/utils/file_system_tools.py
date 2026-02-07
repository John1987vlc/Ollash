import json
import difflib
from pathlib import Path
from typing import Dict, List, Any

from src.utils.file_manager import FileManager
from src.utils.tool_interface import ToolExecutor # For confirmation logic
# Assuming AgentLogger will be passed during initialization
# from src.agents.code_agent import AgentLogger # This will be changed

class FileSystemTools:
    def __init__(self, project_root: Path, file_manager: FileManager, logger: Any, tool_executor: ToolExecutor):
        self.project_root = project_root
        self.files = file_manager
        self.logger = logger
        self.tool_executor = tool_executor
        self._read_count: Dict[str, int] = {} # Still needed here for tracking file reads

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

    def write_file(self, path: str, content: str, reason: str = ""):
        """Write file with user confirmation"""
        if not self.tool_executor._ask_confirmation("write_file", {
            "path": path,
            "content": content,
            "reason": reason
        }):
            self.logger.info(f"User cancelled write: {path}")
            return {
                "ok": False,
                "error": "user_cancelled",
                "message": "User cancelled the file write operation"
            }
        
        try:
            full = self.project_root / path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            
            self.logger.info(f"✅ File written: {path}")
            return {"ok": True, "path": path, "chars": len(content)}
            
        except Exception as e:
            self.logger.error(f"Error writing {path}: {e}", e)
            return {"ok": False, "error": str(e)}

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