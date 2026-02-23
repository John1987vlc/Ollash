import ipaddress
import re
from typing import Dict, List, Any, Optional
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.tools.tool_decorator import ollash_tool

class NetworkEngineeringTools:
    """
    Advanced tools for Network Engineers: Subnetting, Config Auditing, and Troubleshooting.
    """
    
    def __init__(self, logger: AgentLogger):
        self.logger = logger

    @ollash_tool(
        name="calculate_subnets",
        description="Calculates subnets, usable IP ranges, and broadcast addresses for a given network.",
        parameters={
            "network_cidr": {"type": "string", "description": "The base network in CIDR notation (e.g., '192.168.1.0/24')"},
            "new_prefix": {"type": "integer", "description": "The prefix length for the new subnets (e.g., 26)"}
        },
        toolset_id="network_eng_tools",
        agent_types=["network"],
        required=["network_cidr", "new_prefix"]
    )
    def calculate_subnets(self, network_cidr: str, new_prefix: int) -> Dict[str, Any]:
        """Performs IPv4 subnetting calculations."""
        try:
            net = ipaddress.IPv4Network(network_cidr)
            subnets = list(net.subnets(new_prefix=new_prefix))
            
            result = {
                "base_network": network_cidr,
                "total_subnets": len(subnets),
                "subnets": []
            }
            
            # Return first 16 subnets to avoid output flooding
            for s in subnets[:16]:
                result["subnets"].append({
                    "network": str(s),
                    "broadcast": str(s.broadcast_address),
                    "usable_range": f"{s.network_address + 1} - {s.broadcast_address - 1}",
                    "total_hosts": s.num_addresses - 2
                })
            
            if len(subnets) > 16:
                result["note"] = f"Showing first 16 subnets out of {len(subnets)}."
                
            return {"ok": True, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="audit_cisco_config",
        description="Audits a Cisco IOS configuration snippet for common security misconfigurations.",
        parameters={
            "config_text": {"type": "string", "description": "The configuration snippet to audit."}
        },
        toolset_id="network_eng_tools",
        agent_types=["network"],
        required=["config_text"]
    )
    def audit_cisco_config(self, config_text: str) -> Dict[str, Any]:
        """Analyzes Cisco configuration for security issues."""
        self.logger.info("Auditing Cisco configuration...")
        findings = []
        
        checks = {
            "No Password Encryption": r"no service password-encryption",
            "Telnet Enabled": r"transport input telnet",
            "Unsecured Console": r"line con 0\n\s*[^p]*password",
            "No Enable Secret": r"^enable password",
            "HTTP Server Enabled": r"^ip http server",
            "SNMP Public Community": r"snmp-server community public"
        }
        
        for issue, pattern in checks.items():
            if re.search(pattern, config_text, re.MULTILINE | re.IGNORECASE):
                findings.append({
                    "issue": issue,
                    "severity": "high" if "password" in issue.lower() or "Telnet" in issue else "medium",
                    "recommendation": f"Disable or secure the {issue} setting."
                })
        
        return {
            "ok": True,
            "result": {
                "issues_found": len(findings),
                "findings": findings,
                "status": "secure" if not findings else "vulnerable"
            }
        }
