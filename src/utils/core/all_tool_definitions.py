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
            "name": "select_agent_type",
            "description": "Switches the agent's active persona and toolset to a specialized domain (e.g., 'code', 'system', 'network', 'cybersecurity', 'orchestrator'). This is a meta-tool for agent self-modification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_type": {"type": "string", "enum": ["orchestrator", "code", "network", "system", "cybersecurity", "bonus"], "description": "The type of specialized agent to switch to."},
                    "reason": {"type": "string", "description": "Explanation for why the agent type switch is necessary."}
                },
                "required": ["agent_type", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_project",
            "description": "Analyzes the entire project structure, dependencies, and code patterns to provide a comprehensive overview. Use this for gaining a broad understanding of the codebase.",
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
                    "path2": {"type": "string", "description": "Optional: Path to the second file. If not provided, compares path1 with inline_content."},
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
            "description": "Searches for a specific pattern within the codebase. Useful for finding definitions, usages, or specific code snippets.",
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
            "name": "run_command",
            "description": "Executes a shell command. Use for running scripts, build tools, or any command-line utility.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute."},
                    "timeout": {"type": "integer", "description": "Optional: Maximum time in seconds to wait for the command to complete. Defaults to 300 seconds."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Runs a specified set of tests or all tests in the project. Useful for verifying changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {"type": "string", "description": "Optional: Path to a specific test file or directory. If not provided, runs all tests."},
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: Additional arguments to pass to the test runner (e.g., ['-k', 'test_my_feature'])."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_change",
            "description": "Runs validation checks (e.g., linting, type-checking, tests) on proposed changes. Use before committing or pushing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: List of files to validate. If not provided, validates all changed files or the entire project."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Shows the status of the git repository (e.g., modified, staged, untracked files).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commits changes to the git repository. Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The commit message."},
                    "all": {"type": "boolean", "description": "Optional: Whether to commit all changes. Defaults to false (only staged)."},
                    "reason": {"type": "string", "description": "The reason for this commit, for user confirmation."}
                },
                "required": ["message", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": "Pushes committed changes to the remote git repository. Requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "Optional: The name of the remote to push to. Defaults to 'origin'."},
                    "branch": {"type": "string", "description": "Optional: The name of the branch to push. Defaults to current branch."}
                },
                "required": ["remote", "branch"]
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
            "name": "ping_host",
            "description": "Sends ICMP echo requests to a network host to test reachability and measure round-trip time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "The hostname or IP address to ping."},
                    "count": {"type": "integer", "description": "Optional: Number of echo requests to send. Defaults to 4."}
                },
                "required": ["host"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "traceroute_host",
            "description": "Traces the network path to a host, showing hops and latencies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "The hostname or IP address to traceroute."},
                    "max_hops": {"type": "integer", "description": "Optional: Maximum number of hops to search for the target. Defaults to 30."}
                },
                "required": ["host"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_active_connections",
            "description": "Lists all active network connections and listening ports on the system.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_port_status",
            "description": "Checks if a specific TCP port is open on a given host.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "The target hostname or IP address."},
                    "port": {"type": "integer", "description": "The TCP port number to check."}
                },
                "required": ["host", "port"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Retrieves general system information (OS, CPU, memory, uptime, etc.).",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_processes",
            "description": "Lists currently running processes with their IDs, CPU/memory usage, and owner.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "install_package",
            "description": "Installs a software package using the system's package manager.",
            "parameters": {
                "type": "object",
                "properties": {
                    "package_name": {"type": "string", "description": "The name of the package to install."},
                    "package_manager": {"type": "string", "enum": ["apt", "yum", "brew", "choco", "pip"], "description": "The package manager to use."}
                },
                "required": ["package_name", "package_manager"]
            }
        }
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
                    "keyword": {"type": "string", "description": "Optional: Keyword to filter log entries."},
                    "lines": {"type": "integer", "description": "Optional: Number of recent lines to read. Defaults to 100."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scan_ports",
            "description": "Performs a port scan on a target host to identify open ports and services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "The target hostname or IP address."},
                    "ports": {"type": "string", "description": "Optional: Port range (e.g., '1-1024') or specific ports (e.g., '22,80,443'). Defaults to common ports."}
                },
                "required": ["host"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_file_hash",
            "description": "Calculates the hash (MD5, SHA256) of a file and compares it against a known good hash for integrity checking.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."},
                    "expected_hash": {"type": "string", "description": "The known good hash to compare against."},
                    "hash_type": {"type": "string", "enum": ["md5", "sha256"], "description": "The type of hash to calculate. Defaults to sha256."}
                },
                "required": ["path", "expected_hash"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_security_log",
            "description": "Analyzes a security log file for suspicious activities, login failures, or unauthorized access attempts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "log_path": {"type": "string", "description": "Path to the security log file."},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: List of keywords to search for."
                    }
                },
                "required": ["log_path"]
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
    },
    # META / ORQUESTACIÓN AVANZADA
    {
        "type": "function",
        "function": {
            "name": "evaluate_plan_risk",
            "description": "Evaluates a plan_actions before executing it, detecting technical, security, and impact risks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan": {"type": "object", "description": "The plan to evaluate, as generated by plan_actions."}
                },
                "required": ["plan"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_user_intent",
            "description": "Classifies the user's real intent: exploration, debugging, change, audit, incident, learning.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_request": {"type": "string", "description": "The user's request text."}
                },
                "required": ["user_request"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "require_human_gate",
            "description": "Marks an action or set of actions as blocked until explicit human approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_description": {"type": "string", "description": "A clear description of the action to be gated."},
                    "reason": {"type": "string", "description": "Why human approval is required."}
                },
                "required": ["action_description", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_session_state",
            "description": "Summarizes the current state of the system, changes made, decisions taken, and pending risks.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_decision",
            "description": "Explains why the agent made a specific decision and what alternatives it discarded.",
            "parameters": {
                "type": "object",
                "properties": {
                    "decision_id": {"type": "string", "description": "Optional ID of a past decision to explain."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_environment_expectations",
            "description": "Checks if the current environment matches what is expected (OS, version, permissions, network).",
            "parameters": {
                "type": "object",
                "properties": {
                    "expectations": {"type": "object", "description": "A dictionary of expected environment attributes."}
                },
                "required": ["expectations"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_configuration_drift",
            "description": "Detects deviations with respect to a known baseline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "baseline_file": {"type": "string", "description": "Path to the baseline configuration file."},
                    "current_file": {"type": "string", "description": "Path to the current configuration file to compare."}
                },
                "required": ["baseline_file", "current_file"]
            }
        }
    },
    # META / CALIDAD Y GOVERNANCE
    {
        "type": "function",
        "function": {
            "name": "evaluate_compliance",
            "description": "Evaluates system configurations and practices against a specified compliance standard (e.g., ISO 27001, GDPR).",
            "parameters": {
                "type": "object",
                "properties": {
                    "compliance_standard": {"type": "string", "description": "The name of the compliance standard (e.g., 'ISO 27001', 'GDPR')."},
                    "audit_scope": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "A list of areas or components to audit."
                    }
                },
                "required": ["compliance_standard", "audit_scope"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_audit_report",
            "description": "Generates a structured report from previous tool outputs (e.g., security scan, compliance evaluation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "report_format": {"type": "string", "enum": ["json", "text"], "description": "The desired format of the report (e.g., 'json', 'text')."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_governance_policy",
            "description": "Proposes new governance policies or updates existing ones based on compliance gaps or best practices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "policy_type": {"type": "string", "description": "The type of policy to propose (e.g., 'data_handling', 'access_control')."},
                    "scope": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The scope to which the policy applies."
                    }
                },
                "required": ["policy_type", "scope"]
            }
        }
    },
    # CÓDIGO / SOFTWARE ENGINEERING (Advanced)
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
    # SISTEMA / OPERACIONES (Advanced)
    {
        "type": "function",
        "function": {
            "name": "check_disk_health",
            "description": "Analyzes disk usage, inodes, anomalous growth, and suspicious directories.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "monitor_resource_spikes",
            "description": "Detects recent spikes in CPU, RAM, or I/O and correlates them with processes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_type": {"type": "string", "enum": ["cpu", "ram", "io"], "description": "The resource to monitor ('cpu', 'ram', 'io')."},
                    "duration_minutes": {"type": "integer", "description": "How many minutes in the past to check for spikes. Defaults to 5."}
                },
                "required": ["resource_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_startup_services",
            "description": "Lists services that start with the system and evaluates if they are necessary.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rollback_last_change",
            "description": "Reverts the last known change (git, config, package) in a controlled way.",
            "parameters": {
                "type": "object",
                "properties": {
                    "change_type": {"type": "string", "enum": ["git", "config", "package"], "description": "The type of change to roll back."}
                },
                "required": ["change_type"]
            }
        }
    },
    # NETWORK / INFRA (Advanced)
    {
        "type": "function",
        "function": {
            "name": "analyze_network_latency",
            "description": "Correlates latency, packet loss, and network routes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_host": {"type": "string", "description": "The target host to analyze latency against."}
                },
                "required": ["target_host"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_unexpected_services",
            "description": "Detects services listening on ports not expected for that host.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "The host to scan."},
                    "expected_ports": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "A list of ports that are expected to be open."
                    }
                },
                "required": ["host", "expected_ports"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "map_internal_network",
            "description": "Discovers hosts, probable roles, and relationships within the local network.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subnet": {"type": "string", "description": "The subnet to scan (e.g., '192.168.1.0/24'). If not provided, will attempt to auto-detect."}
                }
            }
        }
    },
    # CIBERSEGURIDAD (Advanced)
    {
        "type": "function",
        "function": {
            "name": "assess_attack_surface",
            "description": "Evaluates the attack surface by combining open ports, services, users, and configurations.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "detect_ioc",
            "description": "Searches for known Indicators of Compromise (IOCs) in logs, processes, and files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths_to_scan": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: List of file/directory paths to scan for IOCs."
                    },
                    "hash_to_check": {"type": "string", "description": "Optional: A specific file hash to check against known IOCs."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_permissions",
            "description": "Audits file, user, and service permissions for excesses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The file or directory path to analyze permissions for."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "security_posture_score",
            "description": "Calculates a security posture score with an explanation.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    # BONUS
    {
        "type": "function",
        "function": {
            "name": "estimate_change_blast_radius",
            "description": "Estimates how many components, users, or services will be affected by a change.",
            "parameters": {
                "type": "object",
                "properties": {
                    "change_description": {"type": "string", "description": "A clear description of the proposed change."}
                },
                "required": ["change_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_runbook",
            "description": "Generates a human-readable runbook from repeated actions or resolved incidents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_or_task_description": {"type": "string", "description": "Description of the incident or task to generate a runbook for."}
                },
                "required": ["incident_or_task_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_sentiment",
            "description": "Analyzes the sentiment of a given text (e.g., positive, negative, neutral).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to analyze."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_creative_content",
            "description": "Generates creative text content based on a prompt and desired style.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The prompt for content generation."},
                    "style": {"type": "string", "description": "The desired style (e.g., 'neutral', 'formal', 'poetic')."}
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "translate_text",
            "description": "Translates text from one language to another.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text to translate."},
                    "target_language": {"type": "string", "description": "The target language (e.g., 'en', 'es', 'fr')."}
                },
                "required": ["text", "target_language"]
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