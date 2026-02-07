from typing import Any, Dict
from src.utils.command_executor import CommandExecutor
import platform # To determine OS type for platform-specific commands

class NetworkTools:
    def __init__(self, command_executor: CommandExecutor, logger: Any):
        self.exec = command_executor
        self.logger = logger
        self.os_type = platform.system() # "Windows", "Linux", "Darwin" (macOS)

    def ping_host(self, host: str, count: int = 4):
        """Pings a specified host (IP address or hostname) to check network connectivity."""
        self.logger.info(f"🌐 Pinging host: {host} ({count} times)")
        command = ""
        if self.os_type == "Windows":
             command = f"ping -n {count} {host}" 
        else: # Linux or macOS
             command = f"ping -c {count} {host}"

        result = self.exec.execute(command)
        if result.success:
            self.logger.info(f"✅ Ping successful to {host}")
            return {"ok": True, "host": host, "output": result.stdout}
        else:
            self.logger.error(f"❌ Ping failed to {host}: {result.stderr}")
            return {"ok": False, "host": host, "error": result.stderr, "output": result.stdout}

    def traceroute_host(self, host: str):
        """Traces the network path to a specified host (IP address or hostname)."""
        self.logger.info(f"🗺️ Tracing route to host: {host}")
        command = ""
        if self.os_type == "Windows":
            command = f"tracert {host}" 
        else: # Linux or macOS
            command = f"traceroute {host}"
            
        result = self.exec.execute(command)
        if result.success:
            self.logger.info(f"✅ Traceroute successful to {host}")
            return {"ok": True, "host": host, "output": result.stdout}
        else:
            self.logger.error(f"❌ Traceroute failed to {host}: {result.stderr}")
            return {"ok": False, "host": host, "error": result.stderr, "output": result.stdout}

    def list_active_connections(self):
        """Lists all active network connections on the system."""
        self.logger.info("🔗 Listing active network connections...")
        command = "netstat -an" # Common for Windows/Linux/macOS
        result = self.exec.execute(command)
        if result.success:
            self.logger.info("✅ Successfully listed active connections.")
            return {"ok": True, "output": result.stdout}
        else:
            self.logger.error(f"❌ Failed to list active connections: {result.stderr}")
            return {"ok": False, "error": result.stderr, "output": result.stdout}

    def check_port_status(self, host: str, port: int):
        """Checks if a specific port is open on a given host."""
        self.logger.info(f"🔍 Checking port {port} on {host}...")
        command = ""
        if self.os_type == "Windows":
             command = f"powershell -command \"Test-NetConnection -ComputerName {host} -Port {port}\""
        else: # Linux or macOS
             command = f"nc -vz {host} {port}" # nc for Linux/macOS
        
        result = self.exec.execute(command, timeout=5) # Short timeout for port check
        
        if result.success and (
            ("succeeded" in result.stdout) or 
            ("TcpTestSucceeded : True" in result.stdout) or
            ("Connection to" in result.stderr and "succeeded!" in result.stderr) # nc output to stderr on success
        ):
            self.logger.info(f"✅ Port {port} on {host} is open.")
            return {"ok": True, "host": host, "port": port, "status": "open", "output": result.stdout + result.stderr}
        else:
            self.logger.info(f"❌ Port {port} on {host} is closed or unreachable. Error: {result.stderr}")
            return {"ok": False, "host": host, "port": port, "status": "closed/unreachable", "error": result.stderr, "output": result.stdout}