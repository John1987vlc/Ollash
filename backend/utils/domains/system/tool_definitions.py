from typing import Dict, List

SYSTEM_TOOL_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Retrieves general system information (OS, CPU, memory, uptime, etc.).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "Lists currently running processes with their IDs, CPU/memory usage, and owner.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "install_package",
            "description": "Installs a software package using the system's package manager.",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "The name of the package to install.",
                    },
                    "package_manager": {
                        "type": "string",
                        "enum": ["apt", "yum", "brew", "choco", "pip"],
                        "description": "The package manager to use.",
                    },
                },
                "required": ["package_name", "package_manager"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_log_file",
            "description": "Reads the content of a specified log file, optionally filtering by keywords or time range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the log file."},
                    "keyword": {
                        "type": "string",
                        "description": "Optional: Keyword to filter log entries.",
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Optional: Number of recent lines to read. Defaults to 100.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_disk_health",
            "description": "Analyzes disk usage, inodes, anomalous growth, and suspicious directories.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "monitor_resource_spikes",
            "description": "Detects recent spikes in CPU, RAM, or I/O and correlates them with processes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_type": {
                        "type": "string",
                        "enum": ["cpu", "ram", "io"],
                        "description": "The resource to monitor ('cpu', 'ram', 'io').",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "How many minutes in the past to check for spikes. Defaults to 5.",
                    },
                },
                "required": ["resource_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_startup_services",
            "description": "Lists services that start with the system and evaluates if they are necessary.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rollback_last_change",
            "description": "Reverts the last known change (git, config, package) in a controlled way.",
            "parameters": {
                "type": "object",
                "properties": {
                    "change_type": {
                        "type": "string",
                        "enum": ["git", "config", "package"],
                        "description": "The type of change to roll back.",
                    }
                },
                "required": ["change_type"],
            },
        },
    },
]
