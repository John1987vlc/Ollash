from typing import Any, Dict, List, Optional
from src.utils.command_executor import CommandExecutor
from src.utils.file_manager import FileManager
import hashlib
import platform # To determine OS type for platform-specific commands

class CybersecurityTools:
    def __init__(self, command_executor: CommandExecutor, file_manager: FileManager, logger: Any):
        self.exec = command_executor
        self.files = file_manager
        self.logger = logger
        self.os_type = platform.system() # "Windows", "Linux", "Darwin" (macOS)

    def scan_ports(self, host: str, common_ports_only: bool = True):
        """Scans common or all ports on a host for open services."""
        self.logger.info(f"🕵️‍♀️ Scanning ports on host: {host} (common_ports_only: {common_ports_only})...")
        command = ""
        if common_ports_only:
            # Common ports for a quick scan (HTTP, HTTPS, SSH, FTP, DNS, SMTP, POP3, IMAP)
            ports = "21,22,23,25,53,80,110,143,3389,443,8080" 
            if self.os_type == "Windows":
                 # Using PowerShell for Test-NetConnection for multiple ports
                 command = f"powershell -command \"{';'.join([f'(Test-NetConnection -ComputerName {host} -Port {p} -InformationLevel Quiet)' for p in ports.split(',')])}\""
                 # This PowerShell command checks connectivity, but doesn't list all open ports like nmap
                 # For a more robust scan, nmap would be ideal but requires installation.
            else: # Linux or macOS
                command = f"nmap -p {ports} {host}" # nmap is a standard tool but might not be installed
        else:
            if self.os_type == "Windows":
                 return {"ok": False, "error": "Full port scan not supported on Windows without external tools like Nmap."}
            else: # Linux or macOS
                command = f"nmap {host}" # Full scan using nmap

        if not command:
            return {"ok": False, "error": "Port scanning not implemented for this OS or common_ports_only setting without Nmap."}

        result = self.exec.execute(command, timeout=120) # Longer timeout for scans
        if result.success:
            self.logger.info(f"✅ Port scan on {host} completed.")
            return {"ok": True, "host": host, "output": result.stdout}
        else:
            self.logger.error(f"❌ Port scan on {host} failed: {result.stderr}")
            return {"ok": False, "host": host, "error": result.stderr, "output": result.stdout}

    def check_file_hash(self, path: str, algorithm: str = "sha256"):
        """Calculates the cryptographic hash of a file for integrity checking."""
        self.logger.info(f"Integrity checking file: {path} with {algorithm}...")
        try:
            full_path = self.files.root / path
            if not full_path.is_file():
                return {"ok": False, "error": "File not found or not a file.", "path": path}

            hasher = hashlib.new(algorithm)
            with open(full_path, 'rb') as f:
                while chunk := f.read(8192): # Read in 8KB chunks
                    hasher.update(chunk)
            
            file_hash = hasher.hexdigest()
            self.logger.info(f"✅ Hash for {path} ({algorithm}): {file_hash}")
            return {"ok": True, "path": path, "algorithm": algorithm, "hash": file_hash}
        except FileNotFoundError:
            self.logger.error(f"❌ File not found: {path}")
            return {"ok": False, "error": "File not found", "path": path}
        except ValueError:
            self.logger.error(f"❌ Invalid hashing algorithm: {algorithm}")
            return {"ok": False, "error": f"Invalid algorithm: {algorithm}"}
        except Exception as e:
            self.logger.error(f"❌ Error calculating hash for {path}: {e}", e)
            return {"ok": False, "error": str(e), "path": path}

    def analyze_security_log(self, path: str, keywords: Optional[List[str]] = None):
        """Analyzes a security log file for specific keywords or anomalies."""
        self.logger.info(f"🕵️‍♀️ Analyzing security log: {path} for keywords: {keywords or 'any'}...")
        try:
            full_path = self.files.root / path
            if not full_path.exists():
                return {"ok": False, "error": "Log file not found.", "path": path}
            
            log_content = full_path.read_text(encoding="utf-8", errors="ignore")
            found_matches = []

            if keywords:
                for keyword in keywords:
                    if keyword in log_content:
                        found_matches.append(f"Keyword '{keyword}' found.")
            else:
                # Basic anomaly detection: look for common error/warning indicators
                # This is very basic and would need an actual AI model for real anomaly detection
                common_indicators = ["ERROR", "FAILED", "WARNING", "DENIED", "FAILED LOGIN"]
                for indicator in common_indicators:
                    if indicator in log_content:
                        found_matches.append(f"Potential indicator '{indicator}' found.")

            if found_matches:
                self.logger.warning(f"⚠️ Potential security events found in {path}: {found_matches}")
                return {"ok": True, "path": path, "status": "anomalies_found", "matches": found_matches}
            else:
                self.logger.info(f"✅ No immediate security concerns found in {path}.")
                return {"ok": True, "path": path, "status": "no_anomalies_found"}

        except Exception as e:
            self.logger.error(f"❌ Error analyzing security log {path}: {e}", e)
            return {"ok": False, "error": str(e), "path": path}

    def recommend_security_hardening(self, os_type: str):
        """Provides basic security hardening recommendations for a given operating system."""
        self.logger.info(f"🛡️ Generating security hardening recommendations for {os_type}...")
        recommendations = []
        os_type_lower = os_type.lower()

        if "windows" in os_type_lower:
            recommendations.append("Ensure Windows Defender/Antivirus is active and up-to-date.")
            recommendations.append("Keep OS and applications patched (Windows Update).")
            recommendations.append("Enable Firewall and configure rules appropriately.")
            recommendations.append("Use strong, unique passwords and enable MFA where possible.")
            recommendations.append("Disable unnecessary services and features.")
            recommendations.append("Implement account lockout policies.")
        elif "linux" in os_type_lower:
            recommendations.append("Keep packages updated (e.g., apt update && apt upgrade).")
            recommendations.append("Configure a firewall (e.g., ufw, firewalld).")
            recommendations.append("Disable root login via SSH; use key-based authentication.")
            recommendations.append("Regularly audit user accounts and permissions.")
            recommendations.append("Install and configure an antivirus/malware scanner (e.g., ClamAV).")
        elif "macos" in os_type_lower:
            recommendations.append("Enable FileVault for disk encryption.")
            recommendations.append("Keep macOS and applications updated.")
            recommendations.append("Enable Firewall and block all incoming connections by default.")
            recommendations.append("Review Privacy & Security settings, especially app permissions.")
            recommendations.append("Use strong passwords and enable Touch ID/Face ID.")
            recommendations.append("Avoid installing software from untrusted sources.")
        else:
            recommendations.append(f"No specific recommendations for '{os_type}'. General advice: Keep software updated, use strong passwords, and employ a firewall.")

        self.logger.info(f"✅ Generated security recommendations for {os_type}.")
        return {"ok": True, "os_type": os_type, "recommendations": recommendations}