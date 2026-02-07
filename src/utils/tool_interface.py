import json
from typing import Dict, List, Any, Optional
# Removed datetime and difflib as they are not directly used in ToolExecutor
from colorama import Fore, Style # Kept for printing prompts, but init() moved to agent_logger

class ToolExecutor:
    MODIFY_ACTIONS = {"write_file", "delete_file", "git_commit", "git_push"}

    def __init__(self, logger: Any):
        self.logger = logger
        # Removed _current_plan as it should reside in CodeAgent

    def get_tool_definitions(self) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "plan_actions",
                    "description": "Create a step-by-step plan before taking actions. ALWAYS use this first.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "string", "description": "Main objective to accomplish"},
                            "steps": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Detailed list of steps to accomplish the goal"
                            },
                            "requires_confirmation": {
                                "type": "boolean",
                                "description": "Whether this plan requires user confirmation before execution"
                            }
                        },
                        "required": ["goal", "steps"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_project",
                    "description": "Analyze the entire project structure, dependencies, and get a comprehensive overview. Use this to understand the project before making changes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "focus": {
                                "type": "string",
                                "description": "Optional focus area: 'structure', 'dependencies', 'code_quality', 'all'"
                            },
                            "write_md": {
                                "type": "boolean",
                                "description": "Whether to write the analysis to a Markdown file. Default is false."
                            },
                            "force_md": {
                                "type": "boolean",
                                "description": "If write_md is true, force writing the Markdown file even if it exists. Default is false."
                            },
                            "md_name": {
                                "type": "string",
                                "description": "The name of the Markdown file to write (e.g., 'PROJECT_ANALYSIS.md')."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_files",
                    "description": "Read multiple files at once. More efficient than calling read_file multiple times.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string"},
                                        "offset": {"type": "integer"},
                                        "limit": {"type": "integer"}
                                    },
                                    "required": ["path"]
                                },
                                "description": "List of files to read with optional pagination"
                            }
                        },
                        "required": ["files"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a single file with pagination. Use read_files for multiple files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "offset": {"type": "integer"},
                            "limit": {"type": "integer"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write full content to a file. REQUIRES USER CONFIRMATION.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                            "reason": {"type": "string", "description": "Why this file is being written"}
                        },
                        "required": ["path", "content", "reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_file",
                    "description": "Delete a file. REQUIRES USER CONFIRMATION.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "reason": {"type": "string", "description": "Why this file is being deleted"}
                        },
                        "required": ["path", "reason"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "file_diff",
                    "description": "Show diff before writing a file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "new_content": {"type": "string"}
                        },
                        "required": ["path", "new_content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "summarize_files",
                    "description": "Summarize multiple files at once. More efficient than multiple calls.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of file paths to summarize"
                            }
                        },
                        "required": ["paths"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "summarize_file",
                    "description": "Summarize a single file structure. Use summarize_files for multiple files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search code using grep.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "pattern": {"type": "string"},
                            "max_results": {"type": "integer", "description": "Maximum results to return"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run shell command.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "timeout": {"type": "integer"}
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_tests",
                    "description": "Run pytest.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_change",
                    "description": "Run tests and lint before commit.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_status",
                    "description": "Get git status.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_commit",
                    "description": "Commit staged changes. REQUIRES USER CONFIRMATION.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"}
                        },
                        "required": ["message"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_push",
                    "description": "Push commits. REQUIRES USER CONFIRMATION.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "remote": {"type": "string"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "List files and directories in a path.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Directory path to list"},
                            "recursive": {"type": "boolean", "description": "List recursively"}
                        },
                        "required": ["path"]
                    }
                }
            }
        ]

    def _requires_confirmation(self, tool_name: str) -> bool:
        """Check if a tool requires user confirmation"""
        return tool_name in self.MODIFY_ACTIONS

    def _ask_confirmation(self, action: str, details: Dict) -> bool:
        """Ask user for confirmation"""
        self.logger.info(f"\n{Fore.YELLOW}{'='*60}")
        self.logger.info(f"⚠️  CONFIRMATION REQUIRED: {action}")
        self.logger.info(f"{'='*60}{Style.RESET_ALL}")
        
        if action == "write_file":
            self.logger.info(f"📝 File: {Fore.CYAN}{details['path']}{Style.RESET_ALL}")
            self.logger.info(f"📋 Reason: {details.get('reason', 'N/A')}")
            self.logger.info(f"📏 Size: {len(details['content'])} characters")
            
            # Show preview
            lines = details['content'].split('\n')
            preview_lines = min(10, len(lines))
            self.logger.info(f"\n📄 Preview (first {preview_lines} lines):")
            self.logger.info("-" * 60)
            for i, line in enumerate(lines[:preview_lines], 1):
                self.logger.info(f"{Fore.WHITE}{i:3}: {line}{Style.RESET_ALL}")
            if len(lines) > preview_lines:
                self.logger.info(f"{Fore.YELLOW}... ({len(lines) - preview_lines} more lines){Style.RESET_ALL}")
            self.logger.info("-" * 60)
            
        elif action == "delete_file":
            self.logger.info(f"🗑️  File: {Fore.RED}{details['path']}{Style.RESET_ALL}")
            self.logger.info(f"📋 Reason: {details.get('reason', 'N/A')}")
            
        elif action == "git_commit":
            self.logger.info(f"💾 Message: {Fore.CYAN}{details['message']}{Style.RESET_ALL}")
            
        elif action == "git_push":
            self.logger.info(f"🚀 Remote: {Fore.CYAN}{details.get('remote', 'origin')}{Style.RESET_ALL}")
        
        self.logger.info(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")
        
        while True:
            response = input(f"{Fore.GREEN}Proceed? (yes/no/view): {Style.RESET_ALL}").strip().lower()
            if response in ['yes', 'y', 'si', 's']:
                return True
            elif response in ['no', 'n']:
                return False
            elif response in ['view', 'v'] and action == "write_file":
                self.logger.info(f"\n{Fore.CYAN}{'='*60}")
                self.logger.info("FULL CONTENT:")
                self.logger.info(f"{'='*60}{Style.RESET_ALL}")
                print(details['content']) # Still need print for raw content
                self.logger.info(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
            else:
                self.logger.info(f"{Fore.RED}Please answer 'yes', 'no', or 'view'{Style.RESET_ALL}")
