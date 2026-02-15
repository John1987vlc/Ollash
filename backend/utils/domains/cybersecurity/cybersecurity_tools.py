import hashlib
import json
import platform
import re
from typing import Any, List, Optional

from backend.utils.core.command_executor import CommandExecutor
from backend.utils.core.file_manager import FileManager
from backend.utils.core.tool_decorator import ollash_tool


class CybersecurityTools:
    def __init__(
        self, command_executor: CommandExecutor, file_manager: FileManager, logger: Any
    ):
        self.exec = command_executor
        self.files = file_manager
        self.logger = logger
        self.os_type = platform.system()

    @ollash_tool(
        name="scan_ports",
        description="Performs a port scan on a target host to identify open ports and services.",
        parameters={
            "host": {
                "type": "string",
                "description": "The target hostname or IP address.",
            },
            "ports": {
                "type": "string",
                "description": "Optional: Port range (e.g., '1-1024') or specific ports (e.g., '22,80,443'). Defaults to common ports.",
            },
        },
        toolset_id="cybersecurity_tools",
        agent_types=["cybersecurity"],
        required=["host"],
    )
    def scan_ports(self, host: str, common_ports_only: bool = True):
        """
        Scans common or all ports on a host for open services.
        Returns structured JSON output of scan results.
        """
        self.logger.info(
            f"🕵️‍♀️ Scanning ports on host: {host} (common_ports_only: {common_ports_only})..."
        )
        command = ""
        ports_to_scan = "21,22,23,25,53,80,110,143,3389,443,8080"  # Common ports

        if self.os_type == "Windows":
            if common_ports_only:
                # Test-NetConnection is better for single port checks, multi-port is complex to parse nicely.
                # For simplicity, if Nmap isn't explicitly used, return raw for Windows.
                self.logger.warning(
                    "Windows port scanning without Nmap will return less structured output for multiple ports."
                )
                port_commands = []
                for p in ports_to_scan.split(","):
                    port_commands.append(
                        f'try {{ Test-NetConnection -ComputerName {host} -Port {p} -InformationLevel Detailed | ConvertTo-Json -Compress }} catch {{ Write-Output "{{ \\"Port\\": {p}, \\"Status\\": \\"Closed/Filtered\\" }}" }}'
                    )
                command = f"powershell -command \"{';'.join(port_commands)}\""
            else:
                return {
                    "ok": False,
                    "result": {
                        "host": host,
                        "error": "Full port scan not supported on Windows without external tools like Nmap.",
                    },
                }
        else:  # Linux or macOS (nmap)
            if common_ports_only:
                command = f"nmap -p {ports_to_scan} {host}"
            else:
                command = f"nmap {host}"  # Full scan using nmap

        if not command:
            return {
                "ok": False,
                "result": {
                    "host": host,
                    "error": "Port scanning not implemented for this OS or common_ports_only setting without Nmap.",
                },
            }

        result = self.exec.execute(command, timeout=180)  # Longer timeout for scans

        parsed_output = {"host": host, "ports": [], "raw_output": result.stdout}

        if result.success:
            self.logger.info(f"✅ Port scan on {host} completed.")
            if self.os_type == "Windows":
                # Parse JSON array from PowerShell output
                try:
                    json_output = f"[{result.stdout.replace('}{', '},{')}]"  # Convert concatenated JSON objects to array
                    ps_results = json.loads(json_output)
                    for res in ps_results:
                        port_status = (
                            "open" if res.get("TcpTestSucceeded") else "closed/filtered"
                        )
                        port_num = res.get("Port")
                        if not port_num and res.get(
                            "remotePort"
                        ):  # If Detailed, Port might be remotePort
                            port_num = res.get("remotePort")

                        parsed_output["ports"].append(
                            {
                                "port": port_num,
                                "status": port_status,
                                "service": res.get(
                                    "RemoteHost", host
                                ),  # Placeholder for service, if any
                            }
                        )
                except json.JSONDecodeError:
                    self.logger.warning(
                        "Failed to parse PowerShell JSON output for ports. Returning raw."
                    )
            else:  # Linux/macOS (nmap parsing)
                lines = result.stdout.splitlines()
                port_section_started = False
                for line in lines:
                    if "PORT" in line and "STATE" in line and "SERVICE" in line:
                        port_section_started = True
                        continue
                    if not port_section_started or not line.strip():
                        continue

                    # Example Nmap line: 22/tcp   open  ssh
                    match = re.match(r"(\d+)/([a-z]+)\s+(\S+)\s+(.*)", line)
                    if match:
                        port_num = int(match.group(1))
                        protocol = match.group(2)
                        state = match.group(3)
                        service = match.group(4).strip()
                        parsed_output["ports"].append(
                            {
                                "port": port_num,
                                "protocol": protocol,
                                "state": state,
                                "service": service,
                            }
                        )

            return {"ok": True, "result": parsed_output}
        else:
            self.logger.error(f"❌ Port scan on {host} failed: {result.stderr}")
            parsed_output["error"] = result.stderr
            return {"ok": False, "result": parsed_output}

    @ollash_tool(
        name="check_file_hash",
        description="Calculates the hash (MD5, SHA256) of a file and compares it against a known good hash for integrity checking.",
        parameters={
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
        toolset_id="cybersecurity_tools",
        agent_types=["cybersecurity"],
        required=["path", "expected_hash"],
    )
    def check_file_hash(self, path: str, algorithm: str = "sha256"):
        """
        Calculates the cryptographic hash of a file for integrity checking.
        Returns structured JSON output with path, algorithm, and hash.
        """
        self.logger.info(f"Integrity checking file: {path} with {algorithm}...")
        try:
            full_path = self.files.root / path
            if not full_path.is_file():
                return {
                    "ok": False,
                    "result": {"path": path, "error": "File not found or not a file."},
                }

            hasher = hashlib.new(algorithm)
            with open(full_path, "rb") as f:
                while chunk := f.read(8192):  # Read in 8KB chunks
                    hasher.update(chunk)

            file_hash = hasher.hexdigest()
            self.logger.info(f"✅ Hash for {path} ({algorithm}): {file_hash}")
            return {
                "ok": True,
                "result": {"path": path, "algorithm": algorithm, "hash": file_hash},
            }
        except FileNotFoundError:
            self.logger.error(f"❌ File not found: {path}")
            return {"ok": False, "result": {"path": path, "error": "File not found"}}
        except ValueError:
            self.logger.error(f"❌ Invalid hashing algorithm: {algorithm}")
            return {
                "ok": False,
                "result": {
                    "algorithm": algorithm,
                    "error": f"Invalid algorithm: {algorithm}",
                },
            }
        except Exception as e:
            self.logger.error(f"❌ Error calculating hash for {path}: {e}", e)
            return {
                "ok": False,
                "result": {"path": path, "error": str(e), "raw_error": str(e)},
            }

    @ollash_tool(
        name="analyze_security_log",
        description="Analyzes a security log file for suspicious activities, login failures, or unauthorized access attempts.",
        parameters={
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
        toolset_id="cybersecurity_tools",
        agent_types=["cybersecurity"],
        required=["log_path"],
    )
    def analyze_security_log(self, path: str, keywords: Optional[List[str]] = None):
        """
        Analyzes a security log file for specific keywords or anomalies.
        Returns structured JSON output with path, status, and details of matches.
        """
        self.logger.info(
            f"🕵️‍♀️ Analyzing security log: {path} for keywords: {keywords or 'any'}..."
        )
        try:
            full_path = self.files.root / path
            if not full_path.exists():
                return {
                    "ok": False,
                    "result": {"path": path, "error": "Log file not found."},
                }

            log_content = full_path.read_text(encoding="utf-8", errors="ignore")
            found_entries = []
            status = "no_anomalies_found"

            search_keywords = (
                keywords
                if keywords
                else [
                    "ERROR",
                    "FAILED",
                    "WARNING",
                    "DENIED",
                    "FAILED LOGIN",
                    "authentication failure",
                    "access denied",
                    "attack",
                    "malware",
                ]
            )

            for line_num, line in enumerate(log_content.splitlines(), 1):
                for keyword in search_keywords:
                    if keyword.lower() in line.lower():
                        found_entries.append(
                            {
                                "line_number": line_num,
                                "keyword": keyword,
                                "context": line.strip(),
                            }
                        )
                        status = "anomalies_found"
                        # Only report first match of a keyword per line
                        break

            if found_entries:
                self.logger.warning(
                    f"⚠️ Potential security events found in {path}. Matches: {len(found_entries)}"
                )
            else:
                self.logger.info(f"✅ No immediate security concerns found in {path}.")

            return {
                "ok": True,
                "result": {
                    "path": path,
                    "status": status,
                    "matched_keywords": keywords,
                    "analysis_summary": f"Found {len(found_entries)} potential security events.",
                    "events": found_entries,
                },
            }

        except Exception as e:
            self.logger.error(f"❌ Error analyzing security log {path}: {e}", e)
            return {
                "ok": False,
                "result": {"path": path, "error": str(e), "raw_error": str(e)},
            }

    @ollash_tool(
        name="recommend_security_hardening",
        description="Provides basic security hardening recommendations for a given operating system.",
        parameters={
            "os_type": {
                "type": "string",
                "description": "The type of operating system (e.g., 'Windows', 'Linux', 'macOS').",
            }
        },
        toolset_id="cybersecurity_tools",
        agent_types=["cybersecurity"],
        required=["os_type"],
    )
    def recommend_security_hardening(self, os_type: str):
        """
        Provides basic security hardening recommendations for a given operating system.
        Returns structured JSON output with the OS type and a list of recommendations.
        """
        self.logger.info(
            f"🛡️ Generating security hardening recommendations for {os_type}..."
        )
        recommendations = []
        os_type_lower = os_type.lower()

        if "windows" in os_type_lower:
            recommendations.append(
                "Ensure Windows Defender/Antivirus is active and up-to-date."
            )
            recommendations.append("Keep OS and applications patched (Windows Update).")
            recommendations.append("Enable Firewall and configure rules appropriately.")
            recommendations.append(
                "Use strong, unique passwords and enable MFA where possible."
            )
            recommendations.append("Disable unnecessary services and features.")
            recommendations.append("Implement account lockout policies.")
            recommendations.append(
                "Enable Controlled Folder Access to protect against ransomware."
            )
            recommendations.append("Regularly backup important data.")
        elif "linux" in os_type_lower:
            recommendations.append(
                "Keep packages updated (e.g., apt update && apt upgrade)."
            )
            recommendations.append("Configure a firewall (e.g., ufw, firewalld).")
            recommendations.append(
                "Disable root login via SSH; use key-based authentication and disable password authentication."
            )
            recommendations.append(
                "Regularly audit user accounts and permissions, enforce strong password policies."
            )
            recommendations.append(
                "Install and configure an antivirus/malware scanner (e.g., ClamAV)."
            )
            recommendations.append(
                "Implement SELinux/AppArmor for mandatory access control."
            )
            recommendations.append("Regularly backup important data.")
        elif "macos" in os_type_lower:
            recommendations.append("Enable FileVault for full disk encryption.")
            recommendations.append("Keep macOS and applications updated.")
            recommendations.append(
                "Enable Firewall and block all incoming connections by default. Configure stealth mode."
            )
            recommendations.append(
                "Review Privacy & Security settings, especially app permissions, regularly."
            )
            recommendations.append(
                "Use strong passwords and enable Touch ID/Face ID. Do not reuse passwords."
            )
            recommendations.append(
                "Avoid installing software from untrusted sources; use Gatekeeper/Notarization."
            )
            recommendations.append(
                "Regularly backup important data using Time Machine or other solutions."
            )
        else:
            recommendations.append(
                f"No specific recommendations for '{os_type}'. General advice: Keep software updated, use strong unique passwords, enable multi-factor authentication, employ a firewall, and regularly backup important data."
            )

        self.logger.info(f"✅ Generated security recommendations for {os_type}.")
        return {
            "ok": True,
            "result": {"os_type": os_type, "recommendations": recommendations},
        }
