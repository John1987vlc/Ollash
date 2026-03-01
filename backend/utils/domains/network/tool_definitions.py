from typing import Dict, List

NETWORK_TOOL_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "ping_host",
            "description": "Sends ICMP echo requests to a network host to test reachability and measure round-trip time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "The hostname or IP address to ping.",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Optional: Number of echo requests to send. Defaults to 4.",
                    },
                },
                "required": ["host"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "traceroute_host",
            "description": "Traces the network path to a host, showing hops and latencies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "The hostname or IP address to traceroute.",
                    },
                    "max_hops": {
                        "type": "integer",
                        "description": "Optional: Maximum number of hops to search for the target. Defaults to 15.",
                    },
                },
                "required": ["host"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_active_connections",
            "description": "Lists all active network connections and listening ports on the system.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_port_status",
            "description": "Checks if a specific TCP port is open on a given host.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "The target hostname or IP address.",
                    },
                    "port": {
                        "type": "integer",
                        "description": "The TCP port number to check.",
                    },
                },
                "required": ["host", "port"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_network_latency",
            "description": "Correlates latency, packet loss, and network routes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_host": {
                        "type": "string",
                        "description": "The target host to analyze latency against.",
                    }
                },
                "required": ["target_host"],
            },
        },
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
                        "description": "A list of ports that are expected to be open.",
                    },
                },
                "required": ["host", "expected_ports"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "map_internal_network",
            "description": "Discovers hosts, probable roles, and relationships within the local network.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subnet": {
                        "type": "string",
                        "description": "The subnet to scan (e.g., '192.168.1.0/24'). If not provided, will attempt to auto-detect.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_subnets",
            "description": "Calculates subnets, usable IP ranges, and broadcast addresses for a given network.",
            "parameters": {
                "type": "object",
                "properties": {
                    "network_cidr": {
                        "type": "string",
                        "description": "The base network in CIDR notation (e.g., '192.168.1.0/24')",
                    },
                    "new_prefix": {
                        "type": "integer",
                        "description": "The prefix length for the new subnets (e.g., 26)",
                    },
                },
                "required": ["network_cidr", "new_prefix"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "audit_cisco_config",
            "description": "Audits a Cisco IOS configuration snippet for common security misconfigurations.",
            "parameters": {
                "type": "object",
                "properties": {"config_text": {"type": "string", "description": "The configuration snippet to audit."}},
                "required": ["config_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_scapy_simulation",
            "description": "Executes a Scapy Python script to simulate network traffic or analyze packets.",
            "parameters": {
                "type": "object",
                "properties": {"script": {"type": "string", "description": "Python code using Scapy"}},
                "required": ["script"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "advanced_nmap_scan",
            "description": "Performs an advanced Nmap scan with custom arguments in the isolated sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Target IP or hostname."},
                    "args": {"type": "string", "description": "Nmap arguments (e.g., '-sV -T4 -Pn')."},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cleanup_network_sandbox",
            "description": "Stops and removes the network sandbox container.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
