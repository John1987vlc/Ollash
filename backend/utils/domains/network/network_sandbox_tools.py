from typing import Dict, Any
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.tools.tool_decorator import ollash_tool
from backend.utils.core.tools.network_sandbox import NetworkSandbox


class NetworkSandboxTools:
    """
    Agent tools for running complex network tasks in an isolated environment.
    """

    def __init__(self, logger: AgentLogger):
        self.logger = logger
        self.sandbox = NetworkSandbox(logger=logger)

    @ollash_tool(
        name="run_scapy_simulation",
        description="Executes a Scapy Python script to simulate network traffic or analyze packets.",
        parameters={
            "script": {
                "type": "string",
                "description": "Python code using Scapy (e.g., 'p = IP(dst=\\'1.1.1.1\\')/ICMP(); send(p)')",
            }
        },
        toolset_id="network_sandbox",
        agent_types=["network"],
        required=["script"],
    )
    def run_scapy(self, script: str) -> Dict[str, Any]:
        try:
            if not self.sandbox._is_active:
                self.sandbox.start()

            result = self.sandbox.run_scapy_script(script)
            return {"ok": True, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="advanced_nmap_scan",
        description="Performs an advanced Nmap scan with custom arguments in the isolated sandbox.",
        parameters={
            "target": {"type": "string", "description": "Target IP or hostname."},
            "args": {"type": "string", "description": "Nmap arguments (e.g., '-sV -T4 -Pn')."},
        },
        toolset_id="network_sandbox",
        agent_types=["network"],
        required=["target"],
    )
    def nmap_scan(self, target: str, args: str = "-F") -> Dict[str, Any]:
        try:
            if not self.sandbox._is_active:
                self.sandbox.start()

            result = self.sandbox.run_nmap_scan(target, args)
            return {"ok": True, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="cleanup_network_sandbox",
        description="Stops and removes the network sandbox container.",
        parameters={"type": "object", "properties": {}},
        toolset_id="network_sandbox",
        agent_types=["network"],
    )
    def cleanup(self) -> Dict[str, Any]:
        try:
            self.sandbox.stop()
            return {"ok": True, "message": "Network sandbox stopped."}
        except Exception as e:
            return {"ok": False, "error": str(e)}
