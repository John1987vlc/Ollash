from typing import Any, Dict, Optional
from src.utils.command_executor import CommandExecutor
from src.utils.file_manager import FileManager
import platform # To determine OS type for platform-specific commands

class SystemTools:
    def __init__(self, command_executor: CommandExecutor, file_manager: FileManager, logger: Any):
        self.exec = command_executor
        self.files = file_manager
        self.logger = logger
        self.os_type = platform.system() # "Windows", "Linux", "Darwin" (macOS)

    def get_system_info(self):
        """Retrieves basic operating system and hardware information."""
        self.logger.info("ℹ️ Getting system information...")
        command = ""
        if self.os_type == "Windows":
            command = "powershell -command \"Get-ComputerInfo | Select-Object -Property CsName, OsName, OsVersion, OsArchitecture, TotalPhysicalMemory, FreePhysicalMemory\""
        elif self.os_type == "Linux":
            command = "hostnamectl && lscpu | grep 'Model name' && free -h | grep 'Mem:'"
        elif self.os_type == "Darwin": # macOS
            command = "sw_vers && sysctl -n machdep.cpu.brand_string && sysctl -n hw.memsize | awk '{print $0/1073741824\" GB\"}'"
        else:
            return {"ok": False, "error": "Unsupported OS for get_system_info"}
            
        result = self.exec.execute(command)
        if result.success:
            self.logger.info("✅ System information retrieved successfully.")
            return {"ok": True, "output": result.stdout}
        else:
            self.logger.error(f"❌ Failed to get system information: {result.stderr}")
            return {"ok": False, "error": result.stderr, "output": result.stdout}

    def list_processes(self):
        """Lists all currently running processes on the system."""
        self.logger.info("📋 Listing running processes...")
        command = ""
        if self.os_type == "Windows":
            command = "tasklist"
        elif self.os_type == "Linux" or self.os_type == "Darwin": # macOS
            command = "ps aux"
        else:
            return {"ok": False, "error": "Unsupported OS for list_processes"}

        result = self.exec.execute(command)
        if result.success:
            self.logger.info("✅ Processes listed successfully.")
            return {"ok": True, "output": result.stdout}
        else:
            self.logger.error(f"❌ Failed to list processes: {result.stderr}")
            return {"ok": False, "error": result.stderr, "output": result.stdout}

    def install_package(self, package_name: str, package_manager: str):
        """Installs a software package using a specified package manager."""
        self.logger.info(f"📦 Installing {package_name} using {package_manager}...")
        command = ""
        if package_manager == "apt" and (self.os_type == "Linux"):
            command = f"sudo apt-get install -y {package_name}"
        elif package_manager == "yum" and (self.os_type == "Linux"):
            command = f"sudo yum install -y {package_name}"
        elif package_manager == "choco" and (self.os_type == "Windows"):
            command = f"choco install {package_name} -y"
        elif package_manager == "brew" and (self.os_type == "Darwin"):
            command = f"brew install {package_name}"
        elif package_manager == "pip":
            command = f"pip install {package_name}"
        else:
            self.logger.error(f"Unsupported package manager '{package_manager}' for OS '{self.os_type}' or manager not recognized.")
            return {"ok": False, "error": f"Unsupported package manager '{package_manager}' for OS '{self.os_type}' or manager not recognized."}

        # Adding a confirmation step for installation might be good, but for now, assuming direct execution
        result = self.exec.execute(command, timeout=300) # Increased timeout for installation
        if result.success:
            self.logger.info(f"✅ Package {package_name} installed successfully using {package_manager}.")
            return {"ok": True, "package": package_name, "manager": package_manager, "output": result.stdout}
        else:
            self.logger.error(f"❌ Failed to install package {package_name}: {result.stderr}")
            return {"ok": False, "package": package_name, "manager": package_manager, "error": result.stderr, "output": result.stdout}

    def read_log_file(self, path: str, lines: int = 20):
        """Reads the last N lines of a specified log file."""
        self.logger.info(f"📜 Reading last {lines} lines from log file: {path}...")
        try:
            full_path = self.files.root / path
            if not full_path.exists():
                self.logger.warning(f"Log file not found: {path}")
                return {"ok": False, "error": "Log file not found", "path": path}
            
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                log_lines = f.readlines()
            
            last_lines = "".join(log_lines[-lines:])
            self.logger.info(f"✅ Successfully read last {lines} lines from {path}.")
            return {"ok": True, "path": path, "lines_read": len(log_lines), "content": last_lines}
        except Exception as e:
            self.logger.error(f"❌ Error reading log file {path}: {e}", e)
            return {"ok": False, "error": str(e), "path": path}
