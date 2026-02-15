from typing import Dict, List

CYBERSECURITY_TOOL_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "scan_ports",
            "description": "Performs a port scan on a target host to identify open ports and services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "The target hostname or IP address.",
                    },
                    "ports": {
                        "type": "string",
                        "description": "Optional: Port range (e.g., '1-1024') or specific ports (e.g., '22,80,443'). Defaults to common ports.",
                    },
                },
                "required": ["host"],
            },
        },
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
                    "expected_hash": {
                        "type": "string",
                        "description": "The known good hash to compare against.",
                    },
                    "hash_type": {
                        "type": "string",
                        "enum": ["md5", "sha256"],
                        "description": "The type of hash to calculate. Defaults to sha256.",
                    },
                },
                "required": ["path", "expected_hash"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_security_log",
            "description": "Analyzes a security log file for suspicious activities, login failures, or unauthorized access attempts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "log_path": {
                        "type": "string",
                        "description": "Path to the security log file.",
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional: List of keywords to search for.",
                    },
                },
                "required": ["log_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_security_hardening",
            "description": "Provides basic security hardening recommendations for a given operating system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "os_type": {
                        "type": "string",
                        "description": "The type of operating system (e.g., 'Windows', 'Linux', 'macOS').",
                    }
                },
                "required": ["os_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_attack_surface",
            "description": "Evaluates the attack surface by combining open ports, services, users, and configurations.",
            "parameters": {"type": "object", "properties": {}},
        },
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
                        "description": "Optional: List of file/directory paths to scan for IOCs.",
                    },
                    "hash_to_check": {
                        "type": "string",
                        "description": "Optional: A specific file hash to check against known IOCs.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_permissions",
            "description": "Audits file, user, and service permissions for excesses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The file or directory path to analyze permissions for.",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "security_posture_score",
            "description": "Calculates a security posture score with an explanation.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
