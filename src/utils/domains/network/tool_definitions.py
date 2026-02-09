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
]
