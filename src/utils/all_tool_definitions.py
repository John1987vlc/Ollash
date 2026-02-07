from typing import Dict, List

ALL_TOOLS_DEFINITIONS: List[Dict] = [
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
    },
    {
        "type": "function",
        "function": {
            "name": "select_agent_type",
            "description": "Selects the type of specialized agent (context) to use. The orchestrator agent uses this to delegate to a specific domain agent. Available types are 'code', 'network', 'system', 'cybersecurity', 'orchestrator'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_type": {"type": "string", "description": "The type of agent to switch to (e.g., 'code', 'network', 'system', 'cybersecurity', 'orchestrator')."}
                },
                "required": ["agent_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ping_host",
            "description": "Pings a specified host (IP address or hostname) to check network connectivity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "The IP address or hostname to ping."},
                    "count": {"type": "integer", "description": "Number of ping requests to send. Defaults to 4."}
                },
                "required": ["host"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "traceroute_host",
            "description": "Traces the network path to a specified host (IP address or hostname).",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "The IP address or hostname to traceroute to."}
                },
                "required": ["host"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_active_connections",
            "description": "Lists all active network connections on the system.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_port_status",
            "description": "Checks if a specific port is open on a given host.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "The IP address or hostname."},
                    "port": {"type": "integer", "description": "The port number to check."}
                },
                "required": ["host", "port"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Retrieves basic operating system and hardware information.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "Lists all currently running processes on the system.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "install_package",
            "description": "Installs a software package using a specified package manager.",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_name": {"type": "string", "description": "The name of the package to install."},
                    "package_manager": {"type": "string", "description": "The package manager to use (e.g., 'apt', 'yum', 'choco', 'brew')."}
                },
                "required": ["package_name", "package_manager"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_log_file",
            "description": "Reads the last N lines of a specified log file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the log file."},
                    "lines": {"type": "integer", "description": "The number of lines to read from the end of the file. Defaults to 20."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scan_ports",
            "description": "Scans common or all ports on a host for open services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "The IP address or hostname to scan."},
                    "common_ports_only": {"type": "boolean", "description": "If true, scans only common ports; otherwise, scans all ports. Defaults to true."}
                },
                "required": ["host"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_file_hash",
            "description": "Calculates the cryptographic hash of a file for integrity checking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the file."},
                    "algorithm": {"type": "string", "description": "The hashing algorithm to use (e.g., 'sha256', 'md5'). Defaults to 'sha256'."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_security_log",
            "description": "Analyzes a security log file for specific keywords or anomalies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The path to the security log file."},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of keywords to search for in the log file."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_security_hardening",
            "description": "Provides basic security hardening recommendations for a given operating system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "os_type": {"type": "string", "description": "The type of operating system (e.g., 'Windows', 'Linux', 'macOS')."}
                },
                "required": ["os_type"]
            }
        }
    }
]

def get_filtered_tool_definitions(tool_names: List[str]) -> List[Dict]:
    """
    Filters the ALL_TOOLS_DEFINITIONS to return only those whose names are in tool_names.
    """
    filtered_definitions = []
    for tool_def in ALL_TOOLS_DEFINITIONS:
        if tool_def["function"]["name"] in tool_names:
            filtered_definitions.append(tool_def)
    return filtered_definitions
