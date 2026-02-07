from typing import Any, Dict, List, Optional
import platform # Added
import hashlib # Added
from pathlib import Path # Added

class AdvancedCybersecurityTools:
    def __init__(self, command_executor: Any, file_manager: Any, logger: Any): # Added file_manager
        self.exec = command_executor
        self.files = file_manager # Stored FileManager
        self.logger = logger
        self.os_type = platform.system() # "Windows", "Linux", "Darwin" (macOS)

    def assess_attack_surface(self) -> Dict:
        """
        Evaluates the attack surface by combining open ports, services, users, and configurations.
        Provides a basic assessment based on OS type and potential common vulnerabilities.
        """
        self.logger.info("Assessing attack surface...")
        
        risk_score = 0
        details = []
        
        # OS-based initial risk
        if self.os_type == "Windows":
            risk_score += 3 # Windows often has larger attack surface by default
            details.append({"type": "os_type", "finding": "Windows OS", "risk_impact": "medium", "note": "Historically larger attack surface due to complexity and widespread use."})
        elif self.os_type == "Linux":
            risk_score += 1
            details.append({"type": "os_type", "finding": "Linux OS", "risk_impact": "low", "note": "Generally smaller attack surface if properly configured."})
        elif self.os_type == "Darwin": # macOS
            risk_score += 2
            details.append({"type": "os_type", "finding": "macOS", "risk_impact": "low-medium", "note": "Increasingly targeted, user awareness is key."})

        # Placeholder for integration with other tools
        details.append({"type": "integration_needed", "finding": "Open Ports & Services", "risk_impact": "unknown", "note": "Integrate with 'scan_ports' and 'detect_unexpected_services' for a real assessment."})
        details.append({"type": "integration_needed", "finding": "User Permissions", "risk_impact": "unknown", "note": "Integrate with 'analyze_permissions' for a real assessment."})
        details.append({"type": "integration_needed", "finding": "System Configuration", "risk_impact": "unknown", "note": "Integrate with 'get_system_info' and 'analyze_startup_services' for a real assessment."})
        
        if risk_score > 5:
            summary = "High potential attack surface. Review recommended integrations."
            overall_risk = "high"
        elif risk_score > 2:
            summary = "Medium potential attack surface. Review recommended integrations."
            overall_risk = "medium"
        else:
            summary = "Low potential attack surface. Review recommended integrations."
            overall_risk = "low"

        return {
            "ok": True,
            "result": {
                "overall_risk_level": overall_risk,
                "risk_score": risk_score,
                "summary": summary,
                "findings": details,
                "note": "This is a high-level, generic assessment. A comprehensive attack surface assessment requires deep integration with specific scanning and analysis tools (e.g., Nmap, vulnerability scanners, configuration management tools) and correlating their outputs."
            }
        }

    def detect_ioc(self, paths_to_scan: Optional[List[str]] = None, hash_to_check: Optional[str] = None) -> Dict:
        """
        Searches for known Indicators of Compromise (IOCs) in logs, processes, and files.
        Performs basic checks for suspicious patterns/hashes.
        """
        self.logger.info("Detecting Indicators of Compromise (IOCs)...")
        
        iocs_found = []
        
        # Generic IOCs (expand this with real threat intel)
        suspicious_keywords = ["malware", "ransom", "exploit", "backdoor", "trojan", "phish", "c2server"]
        suspicious_process_names = ["nc.exe", "ncat", "mimikatz", "psexec"] # Example
        suspicious_file_extensions = [".exe.exe", ".dll.dll", ".vbs", ".ps1"] # Double extensions, scripts
        
        # --- Check Process List (basic) ---
        process_result = self.exec.execute("tasklist" if self.os_type == "Windows" else "ps aux")
        if process_result.success:
            for proc_name in suspicious_process_names:
                if proc_name.lower() in process_result.stdout.lower():
                    iocs_found.append({"type": "suspicious_process", "finding": f"Process '{proc_name}' detected.", "severity": "high"})
        else:
            self.logger.warning(f"Could not list processes for IOC detection: {process_result.stderr}")

        # --- Check File Paths (basic) ---
        scan_paths = paths_to_scan if paths_to_scan else [
            "/tmp", "/var/tmp", "/dev/shm", # Linux
            "C:\\Windows\\Temp", "C:\\Users\\Public" # Windows
        ]
        
        for spath in scan_paths:
            try:
                target_dir = Path(spath)
                if not target_dir.exists():
                    continue
                
                for f_path in target_dir.rglob("*"):
                    if f_path.is_file():
                        if f_path.suffix in suspicious_file_extensions:
                            iocs_found.append({"type": "suspicious_file_extension", "finding": str(f_path), "severity": "medium"})
                        
                        # Basic content scan for keywords (very inefficient for large files)
                        try:
                            content = f_path.read_text(encoding="utf-8", errors="ignore").lower()
                            for keyword in suspicious_keywords:
                                if keyword in content:
                                    iocs_found.append({"type": "suspicious_keyword_in_file", "finding": str(f_path), "keyword": keyword, "severity": "medium"})
                        except Exception:
                            pass # Cannot read file
                            
            except Exception as e:
                self.logger.warning(f"Error scanning path {spath} for IOCs: {e}")

        # --- Check File Hash ---
        if hash_to_check:
            # This would typically compare against a database of known malware hashes
            iocs_found.append({"type": "hash_check", "finding": f"Hash '{hash_to_check}' provided. Integration with external threat intelligence for hash lookup needed.", "severity": "info"})

        if iocs_found:
            summary = f"Detected {len(iocs_found)} potential Indicators of Compromise."
            status = "iocs_detected"
        else:
            summary = "No immediate Indicators of Compromise detected (basic checks)."
            status = "no_iocs_detected"

        return {
            "ok": True,
            "result": {
                "status": status,
                "summary": summary,
                "iocs": iocs_found,
                "note": "This is a basic IOC detection. A robust solution requires comprehensive threat intelligence, advanced scanning tools, and deeper analysis capabilities."
            }
        }

    def analyze_permissions(self, path: str) -> Dict:
        """
        Audits file, user, and service permissions for excesses.
        Uses OS-specific commands (ls -ld, icacls) to retrieve and analyze permissions.
        """
        self.logger.info(f"Analyzing permissions for: {path}")
        
        target_path = Path(path)
        if not target_path.exists():
            return {"ok": False, "result": {"error": f"Path not found: {path}"}}
            
        findings = []
        
        try:
            if self.os_type == "Windows":
                command = f"icacls \"{path}\""
                result = self.exec.execute(command)
                if result.success:
                    # Example output: C:\Users\Public BUILTIN\Users:(I)(OI)(CI)(F)
                    # Look for "(F)" (Full control) or "(W)" (Write) for non-admin users
                    if "Everyone:(F)" in result.stdout or "BUILTIN\\Users:(I)(OI)(CI)(F)" in result.stdout:
                         findings.append({"type": "excessive_permissions", "finding": f"Full control permissions detected for 'Everyone' or 'Users' on '{path}'.", "severity": "high"})
                    elif "Everyone:(W)" in result.stdout:
                         findings.append({"type": "excessive_permissions", "finding": f"Write permissions detected for 'Everyone' on '{path}'.", "severity": "medium"})
                    
                    details = result.stdout
                else:
                    details = result.stderr
                    findings.append({"type": "command_error", "finding": f"Failed to retrieve permissions for '{path}'.", "details": details, "severity": "error"})
            else: # Linux/macOS
                command = f"ls -ld \"{path}\""
                result = self.exec.execute(command)
                if result.success:
                    # Example output: drwxrwxrwx 1 user group 0 Jan  1 00:00 directory
                    perm_match = re.search(r"^[drwx-]{10}", result.stdout)
                    if perm_match:
                        perms = perm_match.group(0)
                        if perms[8] == 'w': # World writable
                            findings.append({"type": "excessive_permissions", "finding": f"World-writable permissions detected on '{path}'. Permissions: {perms}", "severity": "high"})
                        elif perms[5] == 'w' and target_path.is_file(): # Group writable file
                             findings.append({"type": "excessive_permissions", "finding": f"Group-writable file detected on '{path}'. Permissions: {perms}", "severity": "medium"})

                    details = result.stdout
                else:
                    details = result.stderr
                    findings.append({"type": "command_error", "finding": f"Failed to retrieve permissions for '{path}'.", "details": details, "severity": "error"})
            
        except Exception as e:
            self.logger.error(f"Error analyzing permissions for {path}: {e}", e)
            return {"ok": False, "result": {"error": str(e), "path": path}}

        if findings:
            summary = f"Detected {len(findings)} potential permission issues for '{path}'."
            status = "permission_issues_detected"
        else:
            summary = f"No immediate permission issues detected for '{path}' (basic check)."
            status = "no_permission_issues"

        return {
            "ok": True,
            "result": {
                "path": path,
                "status": status,
                "summary": summary,
                "findings": findings,
                "note": "This is a basic permission analysis. Comprehensive auditing requires understanding user/group contexts and ACLs, and is highly OS-specific."
            }
        }

    def security_posture_score(self) -> Dict:
        """
        Calculates a security posture score with an explanation.
        Provides a basic score based on OS type and generic security assessments.
        """
        self.logger.info("Calculating security posture score...")
        
        base_score = 70 # Start with a 'C' equivalent
        explanation = []
        
        # Adjust score based on OS type (simplified)
        if self.os_type == "Windows":
            base_score -= 5 # Higher historical vulnerability, more configuration needed
            explanation.append({"area": "os_base_security", "status": "adjusted", "details": "Windows typically requires more active hardening.", "impact": -5})
        elif self.os_type == "Linux":
            base_score += 5 # Generally lower baseline attack surface
            explanation.append({"area": "os_base_security", "status": "adjusted", "details": "Linux can achieve high security with proper configuration.", "impact": +5})
        
        # Generic checks (would integrate with other tools in a real scenario)
        explanation.append({"area": "patch_management", "status": "unknown", "details": "Assumed good. Integrate with SystemTools.get_system_info for actual patch status.", "impact": 0})
        explanation.append({"area": "firewall_status", "status": "unknown", "details": "Assumed active. Integrate with NetworkTools.check_port_status / detect_unexpected_services for actual status.", "impact": 0})
        explanation.append({"area": "access_control", "status": "unknown", "details": "Assumed fair. Integrate with CybersecurityTools.analyze_permissions for actual status.", "impact": 0})
        explanation.append({"area": "malware_detection", "status": "unknown", "details": "Assumed present. Integrate with CybersecurityTools.detect_ioc for actual status.", "impact": 0})

        # Calculate final score and rating
        score = max(0, min(100, base_score)) # Keep score between 0-100
        if score >= 90:
            rating = "Excellent"
        elif score >= 70:
            rating = "Good"
        elif score >= 50:
            rating = "Fair"
        else:
            rating = "Poor"

        summary = f"Overall security posture: {rating} (Score: {score})."
        
        return {
            "ok": True,
            "result": {
                "score": score,
                "rating": rating,
                "summary": summary,
                "explanation": explanation,
                "note": "This is a high-level, generic security posture score. A true assessment requires comprehensive checks across all relevant tools (e.g., active port scans, detailed permission analysis, patch status, IOC detection)."
            }
        }
