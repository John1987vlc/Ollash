from typing import Optional, List, Dict, Any
from pathlib import Path
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.tools.scripting_sandbox import ScriptingSandbox

class NetworkSandbox(ScriptingSandbox):
    """
    Specialized sandbox for Network Engineering.
    Uses 'netshoot' image which contains:
    - tcpdump, tshark, nmap, scapy, iperf, mtr, dig, etc.
    """
    
    def __init__(self, logger: Optional[AgentLogger] = None):
        # Using nicolaka/netshoot as the industry standard for network troubleshooting
        super().__init__(logger=logger, image="nicolaka/netshoot:latest")

    def run_scapy_script(self, python_code: str) -> Dict[str, Any]:
        """Runs a Scapy-based Python script inside the network sandbox."""
        # Wrap code to ensure scapy is imported
        full_code = f"from scapy.all import *\n{python_code}"
        self.write_file("scapy_task.py", full_code)
        
        return self.execute_command(["python3", "scapy_task.py"])

    def run_nmap_scan(self, target: str, arguments: str = "-sV") -> Dict[str, Any]:
        """Runs an nmap scan inside the sandbox."""
        import shlex
        cmd = ["nmap"] + shlex.split(arguments) + [target]
        return self.execute_command(cmd, timeout=300)
