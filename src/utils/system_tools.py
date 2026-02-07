import platform # To determine OS type for platform-specific commands
import re       # For regex parsing
import json     # For JSON operations. Assuming it's already imported or available.
# Keep other imports as they are
from typing import Any, Dict, Optional
from src.utils.command_executor import CommandExecutor
from src.utils.file_manager import FileManager

class SystemTools:
    def __init__(self, command_executor: CommandExecutor, file_manager: FileManager, logger: Any):
        self.exec = command_executor
        self.files = file_manager
        self.logger = logger
        self.os_type = platform.system() # "Windows", "Linux", "Darwin" (macOS)

    def get_system_info(self):
        """
        Retrieves basic operating system and hardware information.
        Returns structured JSON output.
        """
        self.logger.info("ℹ️ Getting system information...")
        command = ""
        if self.os_type == "Windows":
            command = "powershell -command \"Get-ComputerInfo | Select-Object -Property CsName, OsName, OsVersion, OsArchitecture, TotalPhysicalMemory, FreePhysicalMemory | ConvertTo-Json\""
        elif self.os_type == "Linux":
            command = "hostnamectl --json=pretty; lscpu --json=pretty; free --json"
        elif self.os_type == "Darwin": # macOS
            # For macOS, getting structured JSON is harder from shell. Will parse text.
            command = "sw_vers && sysctl -n machdep.cpu.brand_string && sysctl -n hw.memsize && sysctl -n hw.physicalcpu && sysctl -n hw.logicalcpu"
        else:
            return {"ok": False, "error": "Unsupported OS for get_system_info", "details": self.os_type}
            
        result = self.exec.execute(command)
        
        parsed_output = {"os_type": self.os_type, "raw_output": result.stdout}

        if result.success:
            self.logger.info("✅ System information retrieved successfully.")
            if self.os_type == "Windows" or self.os_type == "Linux":
                try:
                    # Linux commands produce multiple JSONs, Windows one.
                    # Attempt to split if multiple JSON objects are concatenated for Linux
                    if self.os_type == "Linux":
                        json_parts = []
                        # Basic attempt to split multiple JSON objects
                        buffer = ""
                        open_braces = 0
                        for char in result.stdout:
                            if char == '{':
                                open_braces += 1
                            elif char == '}':
                                open_braces -= 1
                            buffer += char
                            if open_braces == 0 and buffer.strip():
                                json_parts.append(json.loads(buffer))
                                buffer = ""
                        
                        # Merge multiple JSON objects into one, prioritizing certain fields
                        final_json = {}
                        for part in json_parts:
                            final_json.update(part)
                        parsed_output["info"] = final_json
                    else: # Windows (single JSON output)
                        parsed_output["info"] = json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON system info: {e}")
                    parsed_output["error_parsing_json"] = str(e)
                    parsed_output["info"] = result.stdout # Fallback to raw if parsing fails
            elif self.os_type == "Darwin":
                info_lines = result.stdout.splitlines()
                mac_info = {}
                for line in info_lines:
                    if "ProductName" in line:
                        mac_info["OsName"] = line.split(":")[-1].strip()
                    elif "ProductVersion" in line:
                        mac_info["OsVersion"] = line.split(":")[-1].strip()
                    elif "BuildVersion" in line:
                        mac_info["OsBuild"] = line.split(":")[-1].strip()
                    elif "machdep.cpu.brand_string" in line:
                        mac_info["CpuModel"] = line.split(":")[-1].strip()
                    elif "hw.memsize" in line:
                        mem_bytes = int(line.split(":")[-1].strip())
                        mac_info["TotalPhysicalMemoryGB"] = round(mem_bytes / (1024**3), 2)
                    elif "hw.physicalcpu" in line:
                        mac_info["PhysicalCores"] = int(line.split(":")[-1].strip())
                    elif "hw.logicalcpu" in line:
                        mac_info["LogicalCores"] = int(line.split(":")[-1].strip())
                parsed_output["info"] = mac_info

            return {"ok": True, "result": parsed_output}
        else:
            self.logger.error(f"❌ Failed to get system information: {result.stderr}")
            parsed_output["error"] = result.stderr
            return {"ok": False, "result": parsed_output}

    def list_processes(self):
        """
        Lists all currently running processes on the system.
        Returns structured JSON output including process name, PID, memory, and CPU usage.
        """
        self.logger.info("📋 Listing running processes...")
        command = ""
        if self.os_type == "Windows":
            command = "powershell -command \"Get-Process | Select-Object -Property ProcessName, Id, CPU, WorkingSet | ConvertTo-Json\""
        elif self.os_type == "Linux" or self.os_type == "Darwin": # macOS
            # ps aux output is space-separated, need careful parsing or another tool
            command = "ps aux" # Will parse text output
        else:
            return {"ok": False, "error": "Unsupported OS for list_processes", "details": self.os_type}

        result = self.exec.execute(command)
        
        parsed_output = {"os_type": self.os_type, "processes": [], "raw_output": result.stdout}

        if result.success:
            self.logger.info("✅ Processes listed successfully.")
            if self.os_type == "Windows":
                try:
                    parsed_output["processes"] = json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON process list: {e}")
                    parsed_output["error_parsing_json"] = str(e)
            else: # Linux or macOS (ps aux output)
                lines = result.stdout.splitlines()
                if len(lines) > 1: # Skip header
                    header = lines[0].split()
                    # Example ps aux header: USER     PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
                    for line in lines[1:]:
                        parts = line.split(None, len(header) - 1) # Split by whitespace, max splits based on header length
                        if len(parts) >= 11: # Ensure enough columns for common fields
                            try:
                                process = {
                                    "user": parts[0],
                                    "pid": int(parts[1]),
                                    "cpu_percent": float(parts[2]),
                                    "mem_percent": float(parts[3]),
                                    "command": " ".join(parts[10:]) # Command might have spaces
                                }
                                parsed_output["processes"].append(process)
                            except (ValueError, IndexError) as e:
                                self.logger.warning(f"Failed to parse process line: {line.strip()} - {e}")
            return {"ok": True, "result": parsed_output}
        else:
            self.logger.error(f"❌ Failed to list processes: {result.stderr}")
            parsed_output["error"] = result.stderr
            return {"ok": False, "result": parsed_output}

    def install_package(self, package_name: str, package_manager: str):
        """
        Installs a software package using a specified package manager.
        Returns structured JSON output indicating success/failure and relevant details.
        """
        self.logger.info(f"📦 Installing {package_name} using {package_manager}...")
        command = ""
        if package_manager == "apt" and (self.os_type == "Linux"):
            command = f"sudo apt-get update && sudo apt-get install -y {package_name}"
        elif package_manager == "yum" and (self.os_type == "Linux"):
            command = f"sudo yum install -y {package_name}"
        elif package_manager == "dnf" and (self.os_type == "Linux"): # Adding dnf for modern Fedora/RHEL
            command = f"sudo dnf install -y {package_name}"
        elif package_manager == "choco" and (self.os_type == "Windows"):
            command = f"choco install {package_name} -y"
        elif package_manager == "brew" and (self.os_type == "Darwin"):
            command = f"brew install {package_name}"
        elif package_manager == "pip":
            command = f"pip install {package_name}"
        else:
            self.logger.error(f"Unsupported package manager '{package_manager}' for OS '{self.os_type}' or manager not recognized.")
            return {
                "ok": False,
                "result": {
                    "package": package_name,
                    "manager": package_manager,
                    "error": f"Unsupported package manager '{package_manager}' for OS '{self.os_type}' or manager not recognized."
                }
            }

        result = self.exec.execute(command, timeout=300) # Increased timeout for installation
        if result.success:
            self.logger.info(f"✅ Package {package_name} installed successfully using {package_manager}.")
            return {
                "ok": True, 
                "result": {
                    "package": package_name, 
                    "manager": package_manager, 
                    "status": "installed",
                    "raw_output": result.stdout
                }
            }
        else:
            self.logger.error(f"❌ Failed to install package {package_name}: {result.stderr}")
            return {
                "ok": False, 
                "result": {
                    "package": package_name, 
                    "manager": package_manager, 
                    "status": "failed",
                    "error": result.stderr, 
                    "raw_output": result.stdout
                }
            }

    def read_log_file(self, path: str, lines: int = 20):
        """
        Reads the last N lines of a specified log file.
        Returns structured JSON output including file path, number of lines read, and content.
        """
        self.logger.info(f"📜 Reading last {lines} lines from log file: {path}...")
        try:
            full_path = self.files.root / path
            if not full_path.exists():
                self.logger.warning(f"Log file not found: {path}")
                return {"ok": False, "result": {"path": path, "error": "Log file not found"}}
            
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                log_lines = f.readlines()
            
            last_lines_content = "".join(log_lines[-lines:])
            self.logger.info(f"✅ Successfully read last {lines} lines from {path}.")
            return {
                "ok": True, 
                "result": {
                    "path": path, 
                    "total_lines_in_file": len(log_lines), 
                    "lines_read": lines, 
                    "content": last_lines_content
                }
            }
        except Exception as e:
            self.logger.error(f"❌ Error reading log file {path}: {e}", e)
            return {"ok": False, "result": {"path": path, "error": str(e), "raw_error": str(e)}}
