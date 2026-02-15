from typing import Any, Dict, List, Optional
import platform # Added
import re # Added

class AdvancedNetworkTools:
    def __init__(self, command_executor: Any, logger: Any): # Added command_executor
        self.exec = command_executor # Stored CommandExecutor
        self.logger = logger
        self.os_type = platform.system() # "Windows", "Linux", "Darwin" (macOS)

    def analyze_network_latency(self, target_host: str) -> Dict:
        """
        Correlates latency, packet loss, and network routes.
        Uses ping and traceroute (tracert) commands to gather network data.
        """
        self.logger.info(f"Analyzing network latency to {target_host}...")

        latency_data = {"target_host": target_host}

        # 1. Ping for basic latency and packet loss
        ping_command = f"ping -n 4 {target_host}" if self.os_type == "Windows" else f"ping -c 4 {target_host}"
        ping_result = self.exec.execute(ping_command)

        if ping_result.success:
            if self.os_type == "Windows":
                match_loss = re.search(r"\((\d+)% loss\)", ping_result.stdout)
                match_avg_rtt = re.search(r"Average = (\d+)ms", ping_result.stdout)
                latency_data["packet_loss_percent"] = int(match_loss.group(1)) if match_loss else 100
                latency_data["avg_latency_ms"] = int(match_avg_rtt.group(1)) if match_avg_rtt else None
            else: # Linux/macOS
                match_loss = re.search(r"(\d+\.?\d*)% packet loss", ping_result.stdout)
                match_avg_rtt = re.search(r"min/avg/max/mdev = (\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*)/(\d+\.?\d*) ms", ping_result.stdout)
                latency_data["packet_loss_percent"] = float(match_loss.group(1)) if match_loss else 100
                latency_data["avg_latency_ms"] = float(match_avg_rtt.group(2)) if match_avg_rtt else None
            latency_data["ping_status"] = "success"
        else:
            latency_data["ping_status"] = "failure"
            latency_data["ping_error"] = ping_result.stderr
            latency_data["packet_loss_percent"] = 100
            latency_data["avg_latency_ms"] = None

        # 2. Traceroute for route and hops
        traceroute_command = f"tracert {target_host}" if self.os_type == "Windows" else f"traceroute {target_host}"
        traceroute_result = self.exec.execute(traceroute_command)

        latency_data["route_hops"] = []
        if traceroute_result.success:
            latency_data["traceroute_status"] = "success"
            lines = traceroute_result.stdout.splitlines()
            if self.os_type == "Windows":
                for line in lines:
                    match = re.search(r"^\s*(\d+)\s+([\d.<>msh\* ]+)\s+([a-zA-Z0-9.-]+(?: \[\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\])?)", line)
                    if match:
                        hop_num = int(match.group(1))
                        ip_hostname = match.group(3).strip()
                        latency_data["route_hops"].append({"hop": hop_num, "ip_hostname": ip_hostname})
            else: # Linux/macOS
                for line in lines:
                    match = re.search(r"^\s*(\d+)\s+([a-zA-Z0-9.-]+)\s+\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)", line)
                    if match:
                        hop_num = int(match.group(1))
                        hostname = match.group(2)
                        ip_address = match.group(3)
                        latency_data["route_hops"].append({"hop": hop_num, "hostname": hostname, "ip_address": ip_address})
        else:
            latency_data["traceroute_status"] = "failure"
            latency_data["traceroute_error"] = traceroute_result.stderr

        # 3. Overall summary
        summary = f"Network latency analysis for {target_host}: "
        if latency_data["ping_status"] == "success":
            summary += f"Avg Latency: {latency_data.get('avg_latency_ms', 'N/A')}ms, Packet Loss: {latency_data.get('packet_loss_percent', 'N/A')}%. "
        else:
            summary += "Ping failed. "

        summary += f"Route Hops: {len(latency_data['route_hops'])}."

        return {
            "ok": True,
            "result": {
                "status": "analysis_complete",
                "summary": summary,
                "data": latency_data
            }
        }

    def detect_unexpected_services(self, host: str, expected_ports: List[int]) -> Dict:
        """
        Detects services listening on ports not expected for that host.
        Uses Nmap (Linux/macOS) or Test-NetConnection (Windows) to scan.
        """
        self.logger.info(f"Detecting unexpected services on {host}...")

        unexpected_services = []
        scan_ports_list = ",".join(map(str, range(1, 1025))) # Scan common ports for unexpected ones

        try:
            if self.os_type == "Windows":
                # PowerShell: Test-NetConnection for each port
                self.logger.warning("Windows 'detect_unexpected_services' is basic and checks common ports individually. Nmap is recommended for comprehensive scans.")
                for port in range(1, 1025): # Loop through common ports
                    if port in expected_ports: # Skip expected ports
                        continue

                    command = f"powershell -command \"Test-NetConnection -ComputerName {host} -Port {port} -InformationLevel Quiet\""
                    result = self.exec.execute(command, timeout=5)

                    if result.success and ("TcpTestSucceeded : True" in result.stdout):
                        unexpected_services.append({
                            "port": port,
                            "status": "open",
                            "details": f"Port {port} is open and not in expected_ports list."
                        })
                        if len(unexpected_services) > 5: # Limit output
                            unexpected_services.append({"note": "Limiting unexpected services to first 5 findings."})
                            break
            else: # Linux or macOS (Nmap)
                command = f"nmap -p {scan_ports_list} {host} --open -oG -" # -oG - for grepable output
                result = self.exec.execute(command, timeout=120)

                if result.success:
                    # Nmap grepable output example: Host: 192.168.1.1 (router) Ports: 22/open/tcp//ssh///, 80/open/tcp//http///
                    lines = result.stdout.splitlines()
                    for line in lines:
                        if "Ports:" in line:
                            ports_str = line.split("Ports:")[1].strip()
                            port_entries = ports_str.split(',')
                            for entry in port_entries:
                                match = re.match(r"(\d+)/open/tcp//([^/]+)", entry.strip())
                                if match:
                                    port = int(match.group(1))
                                    service = match.group(2)
                                    if port not in expected_ports:
                                        unexpected_services.append({
                                            "port": port,
                                            "service": service,
                                            "details": f"Port {port} ({service}) is open and not in expected_ports list."
                                        })
                else:
                    self.logger.error(f"Nmap scan failed: {result.stderr}. Is Nmap installed?")
                    return {"ok": False, "result": {"host": host, "error": result.stderr, "note": "Nmap might not be installed or available."}}

        except Exception as e:
            self.logger.error(f"Error detecting unexpected services on {host}: {e}", e)
            return {"ok": False, "result": {"error": str(e), "host": host}}

        if unexpected_services:
            summary = f"Found {len(unexpected_services)} unexpected open services on {host}."
            status = "unexpected_services_detected"
        else:
            summary = f"No unexpected open services detected on {host} (compared against expected_ports: {', '.join(map(str, expected_ports))})."
            status = "no_unexpected_services"

        return {
            "ok": True,
            "result": {
                "host": host,
                "status": status,
                "summary": summary,
                "unexpected_services": unexpected_services,
                "expected_ports_checked": expected_ports
            }
        }

    def map_internal_network(self, subnet: Optional[str] = None) -> Dict:
        """
        Discovers hosts, probable roles, and relationships within the local network.
        Uses OS-specific commands (arp, ip) for local network device discovery.
        """
        self.logger.info(f"Mapping internal network (subnet: {subnet or 'auto-detected'})...")

        hosts_found = []
        discovered_subnet = subnet

        try:
            # Auto-detect subnet if not provided
            if not discovered_subnet:
                if self.os_type == "Windows":
                    ipconfig_result = self.exec.execute("ipconfig")
                    if ipconfig_result.success:
                        match = re.search(r"IPv4 Address[ .]+: (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", ipconfig_result.stdout)
                        if match:
                            local_ip = match.group(1)
                            # Simple /24 assumption for subnet
                            discovered_subnet = ".".join(local_ip.split('.')[:3]) + ".0/24"
                else: # Linux/macOS
                    ip_addr_result = self.exec.execute("ip addr")
                    if ip_addr_result.success:
                        match = re.search(r"inet (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2})", ip_addr_result.stdout)
                        if match:
                            discovered_subnet = match.group(1) # e.g., 192.168.1.10/24

            if not discovered_subnet:
                return {"ok": False, "result": {"error": "Could not determine local subnet. Please provide a subnet manually.", "note": "If using this tool, ensure network commands like ipconfig/ip addr are whitelisted."}}

            # Use arp -a for directly connected devices
            arp_command = "arp -a"
            arp_result = self.exec.execute(arp_command)

            if arp_result.success:
                lines = arp_result.stdout.splitlines()
                for line in lines:
                    ip_match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
                    if ip_match:
                        ip_address = ip_match.group(1)
                        # Basic role inference
                        probable_role = "unknown"
                        if ip_address.endswith(".1"):
                            probable_role = "gateway/router"

                        hosts_found.append({
                            "ip": ip_address,
                            "probable_role": probable_role,
                            "details": "Discovered via ARP table."
                        })
            else:
                self.logger.warning(f"ARP command failed: {arp_result.stderr}. Limited host discovery.")

            # Note: For full subnet scan (e.g., all 254 IPs), nmap would be ideal:
            # command = f"nmap -sn {discovered_subnet}"
            # This would require nmap to be installed and potentially longer execution times.
            # Current approach focuses on already known network devices from ARP cache.

        except Exception as e:
            self.logger.error(f"Error mapping internal network: {e}", e)
            return {"ok": False, "result": {"error": str(e), "subnet": discovered_subnet}}

        summary = f"Discovered {len(hosts_found)} hosts in local network."
        return {
            "ok": True,
            "result": {
                "subnet": discovered_subnet,
                "hosts_found": hosts_found,
                "summary": summary,
                "note": "Host roles are inferred. Comprehensive network mapping might require Nmap or other tools."
            }
        }
