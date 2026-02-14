from typing import Dict, List

CODE_TOOL_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "analyze_project",
            "description": "Analyzes the entire project structure, dependencies, and code patterns to provide a comprehensive overview.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional: The path to the project root or sub-directory to analyze. Defaults to current project root."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the content of a specified file. Can read specific line ranges for large files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the file to read."},
                    "start_line": {"type": "integer", "description": "Optional: Starting line number (1-based) to read."},
                    "end_line": {"type": "integer", "description": "Optional: Ending line number (1-based) to read."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_files",
            "description": "Reads the content of multiple specified files. Use this for reading several files efficiently.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of paths to the files to read."
                    }
                },
                "required": ["paths"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes content to a specified file. Requires user confirmation if it modifies an existing file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the file to write."},
                    "content": {"type": "string", "description": "The content to write to the file."},
                    "reason": {"type": "string", "description": "The reason for writing this file, for user confirmation."}
                },
                "required": ["path", "content", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Deletes a specified file. Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the file to delete."},
                    "reason": {"type": "string", "description": "The reason for deleting this file, for user confirmation."}
                },
                "required": ["path", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_diff",
            "description": "Compares two files or a file with provided content and returns the differences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path1": {"type": "string", "description": "Path to the first file."},
                    "path2": {"type": "string", "description": "Optional: Path to the second file."},
                    "inline_content": {"type": "string", "description": "Optional: Content to compare with path1 if path2 is not provided."}
                },
                "required": ["path1"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_file",
            "description": "Summarizes the content of a single file. Useful for getting a high-level understanding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the file to summarize."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_files",
            "description": "Summarizes the content of multiple files. Useful for getting a high-level understanding of several files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of paths to the files to summarize."
                    }
                },
                "required": ["paths"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Searches for a specific pattern within the codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "The regex pattern to search for."},
                    "file_pattern": {"type": "string", "description": "Optional: Glob pattern to filter files (e.g., '*.py', 'src/**/*.js')."},
                    "case_sensitive": {"type": "boolean", "description": "Optional: Whether the search should be case-sensitive. Defaults to false."}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists the contents of a specified directory. Can include hidden files and be recursive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the directory to list."},
                    "recursive": {"type": "boolean", "description": "Optional: Whether to list contents recursively. Defaults to false."},
                    "include_hidden": {"type": "boolean", "description": "Optional: Whether to include hidden files. Defaults to false."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_code_smells",
            "description": "Analyzes files or folders for code smells (long functions, duplication, dead imports, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The file or directory path to analyze."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_refactor",
            "description": "Proposes concrete refactors (without executing them), indicating benefits and risks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "The path to the file to be refactored."},
                    "line_number": {"type": "integer", "description": "Optional line number to focus the refactor suggestion."}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "map_code_dependencies",
            "description": "Builds a logical map of dependencies between modules, services, or packages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_or_module": {"type": "string", "description": "The name of the package or module to map."}
                },
                "required": ["package_or_module"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_configs",
            "description": "Compares two or more configuration files and detects relevant semantic differences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of at least two configuration file paths to compare."
                    }
                },
                "required": ["file_paths"]
            }
        }
    },
]
