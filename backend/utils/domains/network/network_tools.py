import platform
import re
from typing import Any

from backend.utils.core.command_executor import CommandExecutor
from backend.utils.core.tools.tool_decorator import ollash_tool


class NetworkTools:
    def __init__(self, command_executor: CommandExecutor, logger: Any):
        self.exec = command_executor
        self.logger = logger
        self.os_type = platform.system()

    @ollash_tool(
        name="ping_host",
        description="Sends ICMP echo requests to a network host to test reachability and measure round-trip time.",
        parameters={
            "host": {
                "type": "string",
                "description": "The hostname or IP address to ping.",
            },
            "count": {
                "type": "integer",
                "description": "Optional: Number of echo requests to send. Defaults to 4.",
            },
        },
        toolset_id="network_tools",
        agent_types=["network"],
        required=["host"],
    )
    def ping_host(self, host: str, count: int = 4):
        """
        Pings a specified host (IP address or hostname) to check network connectivity.
        Returns structured JSON output.
        """
        self.logger.info(f"🌐 Pinging host: {host} ({count} times)")
        command = ""
        if self.os_type == "Windows":
            command = f"ping -n {count} {host}"
        else:  # Linux or macOS
            command = f"ping -c {count} {host}"

        result = self.exec.execute(command)

        parsed_output = {
            "host": host,
            "packets_sent": 0,
            "packets_received": 0,
            "packet_loss_percent": 100,
            "avg_rtt_ms": None,
            "min_rtt_ms": None,
            "max_rtt_ms": None,
            "raw_output": result.stdout,
        }

        if result.success:
            self.logger.info(f"✅ Ping successful to {host}")
            # Parse Windows ping output
            if self.os_type == "Windows":
                sent_match = re.search(r"Packets: Sent = (\d+)", result.stdout)
                received_match = re.search(r"Received = (\d+)", result.stdout)
                loss_match = re.search(r"Lost = (\d+) \((\d+)% loss\)", result.stdout)
                avg_match = re.search(r"Average = (\d+)ms", result.stdout)
                min_match = re.search(r"Minimum = (\d+)ms", result.stdout)
                max_match = re.search(r"Maximum = (\d+)ms", result.stdout)

                if sent_match:
                    parsed_output["packets_sent"] = int(sent_match.group(1))
                if received_match:
                    parsed_output["packets_received"] = int(received_match.group(1))
                if loss_match:
                    parsed_output["packet_loss_percent"] = int(loss_match.group(2))
                if avg_match:
                    parsed_output["avg_rtt_ms"] = int(avg_match.group(1))
                if min_match:
                    parsed_output["min_rtt_ms"] = int(min_match.group(1))
                if max_match:
                    parsed_output["max_rtt_ms"] = int(max_match.group(1))
            # Parse Linux/macOS ping output
            else:
                sent_received_match = re.search(r"(\d+) packets transmitted, (\d+) received", result.stdout)
                loss_match = re.search(r"(\d+\.?\d*)% packet loss", result.stdout)
                rtt_match = re.search(
                    r"min/avg/max/mdev = (\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*) ms",
                    result.stdout,
                )

                if sent_received_match:
                    parsed_output["packets_sent"] = int(sent_received_match.group(1))
                    parsed_output["packets_received"] = int(sent_received_match.group(2))
                if loss_match:
                    parsed_output["packet_loss_percent"] = float(loss_match.group(1))
                if rtt_match:
                    parsed_output["min_rtt_ms"] = float(rtt_match.group(1))
                    parsed_output["avg_rtt_ms"] = float(rtt_match.group(2))
                    parsed_output["max_rtt_ms"] = float(rtt_match.group(3))

            return {"ok": True, "result": parsed_output}
        else:
            self.logger.error(f"❌ Ping failed to {host}: {result.stderr}")
            parsed_output["error"] = result.stderr
            return {"ok": False, "result": parsed_output}

    @ollash_tool(
        name="traceroute_host",
        description="Traces the network path to a host, showing hops and latencies.",
        parameters={
            "host": {
                "type": "string",
                "description": "The hostname or IP address to traceroute.",
            },
            "max_hops": {
                "type": "integer",
                "description": "Optional: Maximum number of hops to search for the target. Defaults to 30.",
            },
        },
        toolset_id="network_tools",
        agent_types=["network"],
        required=["host"],
    )
    def traceroute_host(self, host: str, max_hops: int = 30):
        """
        Traces the network path to a specified host (IP address or hostname).
        Returns structured JSON output including hops and their response times.
        """
        self.logger.info(f"🗺️ Tracing route to host: {host}")
        command = ""
        if self.os_type == "Windows":
            command = f"tracert -h {max_hops} {host}"
        else:  # Linux or macOS
            command = f"traceroute -m {max_hops} {host}"

        result = self.exec.execute(command)

        parsed_output = {"host": host, "hops": [], "raw_output": result.stdout}

        if result.success:
            self.logger.info(f"✅ Traceroute successful to {host}")
            lines = result.stdout.splitlines()

            if self.os_type == "Windows":
                # Example: "  1     1 ms     1 ms     1 ms  router.local [192.168.1.1]"
                # Example: "  2    10 ms    12 ms    11 ms  some.isp.com [1.2.3.4]"
                for line in lines:
                    match = re.search(
                        r"^\s*(\d+)\s+([\d.<>msh\* ]+)\s+([a-zA-Z0-9.-]+(?: \[\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\])?)",
                        line,
                    )
                    if match:
                        hop_num = int(match.group(1))
                        times_str = match.group(2).strip()
                        ip_hostname = match.group(3).strip()

                        times = re.findall(r"(\d+)\s*ms", times_str)

                        parsed_output["hops"].append(
                            {
                                "hop": hop_num,
                                "ip_address": re.search(
                                    r"\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]",
                                    ip_hostname,
                                ).group(1)
                                if "[" in ip_hostname
                                else ip_hostname,
                                "hostname": ip_hostname.split(" ")[0] if "[" in ip_hostname else None,
                                "rtt_ms": [int(t) for t in times] if times else None,
                                "raw": line.strip(),
                            }
                        )
            else:  # Linux/macOS
                # Example: " 1  router.local (192.168.1.1)  1.234 ms  2.345 ms  3.456 ms"
                for line in lines:
                    match = re.search(
                        r"^\s*(\d+)\s+([a-zA-Z0-9.-]+)\s+\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)\s+(.*)",
                        line,
                    )
                    if match:
                        hop_num = int(match.group(1))
                        hostname = match.group(2)
                        ip_address = match.group(3)
                        times_str = match.group(4).strip()

                        times = re.findall(r"(\d+\.?\d*)\s*ms", times_str)

                        parsed_output["hops"].append(
                            {
                                "hop": hop_num,
                                "hostname": hostname,
                                "ip_address": ip_address,
                                "rtt_ms": [float(t) for t in times] if times else None,
                                "raw": line.strip(),
                            }
                        )

            return {"ok": True, "result": parsed_output}
        else:
            self.logger.error(f"❌ Traceroute failed to {host}: {result.stderr}")
            parsed_output["error"] = result.stderr
            return {"ok": False, "result": parsed_output}

    @ollash_tool(
        name="list_active_connections",
        description="Lists all active network connections and listening ports on the system.",
        parameters={"type": "object", "properties": {}},
        toolset_id="network_tools",
        agent_types=["network"],
    )
    def list_active_connections(self):
        """
        Lists all active network connections on the system.
        Returns structured JSON output including protocol, local address, foreign address, and state.
        """
        self.logger.info("🔗 Listing active network connections...")
        command = "netstat -an"  # Common for Windows/Linux/macOS
        result = self.exec.execute(command)

        parsed_output = {"connections": [], "raw_output": result.stdout}

        if result.success:
            self.logger.info("✅ Successfully listed active connections.")
            lines = result.stdout.splitlines()

            # Skip header lines
            data_started = False
            for line in lines:
                if "Proto" in line or "Protocol" in line:  # Header line
                    data_started = True
                    continue
                if not data_started or not line.strip():
                    continue

                parts = line.split()
                if len(parts) >= 4:  # Minimum parts for a connection
                    proto = parts[0]
                    local_address = parts[1]
                    foreign_address = parts[2]
                    state = parts[3] if len(parts) > 3 else "N/A"

                    parsed_output["connections"].append(
                        {
                            "protocol": proto,
                            "local_address": local_address,
                            "foreign_address": foreign_address,
                            "state": state,
                        }
                    )

            return {"ok": True, "result": parsed_output}
        else:
            self.logger.error(f"❌ Failed to list active connections: {result.stderr}")
            parsed_output["error"] = result.stderr
            return {"ok": False, "result": parsed_output}

    @ollash_tool(
        name="check_port_status",
        description="Checks if a specific TCP port is open on a given host.",
        parameters={
            "host": {
                "type": "string",
                "description": "The target hostname or IP address.",
            },
            "port": {"type": "integer", "description": "The TCP port number to check."},
        },
        toolset_id="network_tools",
        agent_types=["network"],
        required=["host", "port"],
    )
    def check_port_status(self, host: str, port: int):
        """
        Checks if a specific port is open on a given host.
        Returns structured JSON output including host, port, and status.
        """
        self.logger.info(f"🔍 Checking port {port} on {host}...")
        command = ""
        if self.os_type == "Windows":
            command = f'powershell -command "Test-NetConnection -ComputerName {host} -Port {port}"'
        else:  # Linux or macOS
            command = f"nc -vz {host} {port}"  # nc for Linux/macOS

        result = self.exec.execute(command, timeout=5)  # Short timeout for port check

        status = "closed/unreachable"
        if result.success and (
            ("succeeded" in result.stdout)
            or ("TcpTestSucceeded : True" in result.stdout)
            or ("Connection to" in result.stderr and "succeeded!" in result.stderr)  # nc output to stderr on success
        ):
            status = "open"
            self.logger.info(f"✅ Port {port} on {host} is {status}.")
            return {
                "ok": True,
                "result": {
                    "host": host,
                    "port": port,
                    "status": status,
                    "raw_output": result.stdout + result.stderr,
                },
            }
        else:
            self.logger.info(f"❌ Port {port} on {host} is {status}. Error: {result.stderr}")
            return {
                "ok": False,
                "result": {
                    "host": host,
                    "port": port,
                    "status": status,
                    "error": result.stderr,
                    "raw_output": result.stdout + result.stderr,
                },
            }
