import json
import platform
from typing import Any, Optional

from backend.utils.core.command_executor import CommandExecutor
from backend.utils.core.file_manager import FileManager
from backend.utils.core.tool_decorator import ollash_tool
from backend.utils.domains.system.log_analyzer import LogAnalyzer


class SystemTools:
    def __init__(
        self,
        command_executor: CommandExecutor,
        file_manager: FileManager,
        logger: Any,
        agent_instance: Any,
    ):
        self.exec = command_executor
        self.files = file_manager
        self.logger = logger
        self.os_type = platform.system()
        self.agent = agent_instance
        self.log_analyzer = LogAnalyzer(logger)

    @ollash_tool(
        name="analyze_log_file",
        description="Analyzes a log file for errors and warnings.",
        parameters={
            "file_path": {
                "type": "string",
                "description": "The path to the log file to analyze.",
            },
        },
        toolset_id="system_tools",
        agent_types=["system", "orchestrator"],
        required=["file_path"],
    )
    def analyze_log_file(self, file_path: str):
        """Analyzes a log file for errors and warnings."""
        self.logger.info(f"Analyzing log file: {file_path}")
        full_path = self.files.root / file_path
        return self.log_analyzer.analyze_log_file(full_path)

    @ollash_tool(
        name="get_model_health",
        description="Retrieves health statistics for a specified model or all models.",
        parameters={
            "model_name": {
                "type": "string",
                "description": "Optional: The name of the model to check. If not provided, returns health for all models.",
            },
        },
        toolset_id="system_tools",
        agent_types=["system", "orchestrator"],
    )
    def get_model_health(self, model_name: Optional[str] = None):
        """Retrieves health statistics for a model."""
        self.logger.info(f"Checking model health for: {model_name or 'all models'}")
        health_monitor = self.agent.model_health_monitor
        if not health_monitor:
            return {"ok": False, "error": "ModelHealthMonitor not available."}

        if model_name:
            stats = health_monitor.get_health_stats(model_name)
            return {"ok": True, "model": model_name, "stats": stats}
        else:
            all_stats = {}
            for model in health_monitor.latencies.keys():
                all_stats[model] = health_monitor.get_health_stats(model)
            return {"ok": True, "all_models_stats": all_stats}

    @ollash_tool(
        name="get_system_info",
        description="Retrieves general system information (OS, CPU, memory, uptime, etc.).",
        parameters={"type": "object", "properties": {}},
        toolset_id="system_tools",
        agent_types=["system"],
    )
    def get_system_info(self):
        """
        Retrieves basic operating system and hardware information.
        Returns structured JSON output.
        """
        self.logger.info("ℹ️ Getting system information...")
        command = ""
        if self.os_type == "Windows":
            command = 'powershell -command "Get-ComputerInfo | Select-Object -Property CsName, OsName, OsVersion, OsArchitecture, TotalPhysicalMemory, FreePhysicalMemory | ConvertTo-Json"'
        elif self.os_type == "Linux":
            command = "hostnamectl --json=pretty; lscpu --json=pretty; free --json"
        elif self.os_type == "Darwin":  # macOS
            # For macOS, getting structured JSON is harder from shell. Will parse text.
            command = "sw_vers && sysctl -n machdep.cpu.brand_string && sysctl -n hw.memsize && sysctl -n hw.physicalcpu && sysctl -n hw.logicalcpu"
        else:
            return {
                "ok": False,
                "error": "Unsupported OS for get_system_info",
                "details": self.os_type,
            }

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
                            if char == "{":
                                open_braces += 1
                            elif char == "}":
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
                    else:  # Windows (single JSON output)
                        parsed_output["info"] = json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON system info: {e}")
                    parsed_output["error_parsing_json"] = str(e)
                    parsed_output["info"] = result.stdout  # Fallback to raw if parsing fails
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

    @ollash_tool(
        name="list_processes",
        description="Lists currently running processes with their IDs, CPU/memory usage, and owner.",
        parameters={"type": "object", "properties": {}},
        toolset_id="system_tools",
        agent_types=["system"],
    )
    def list_processes(self):
        """
        Lists all currently running processes on the system.
        Returns structured JSON output including process name, PID, memory, and CPU usage.
        """
        self.logger.info("📋 Listing running processes...")
        command = ""
        if self.os_type == "Windows":
            command = 'powershell -command "Get-Process | Select-Object -Property ProcessName, Id, CPU, WorkingSet | ConvertTo-Json"'
        elif self.os_type == "Linux" or self.os_type == "Darwin":  # macOS
            # ps aux output is space-separated, need careful parsing or another tool
            command = "ps aux"  # Will parse text output
        else:
            return {
                "ok": False,
                "error": "Unsupported OS for list_processes",
                "details": self.os_type,
            }

        result = self.exec.execute(command)

        parsed_output = {
            "os_type": self.os_type,
            "processes": [],
            "raw_output": result.stdout,
        }

        if result.success:
            self.logger.info("✅ Processes listed successfully.")
            if self.os_type == "Windows":
                try:
                    parsed_output["processes"] = json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse JSON process list: {e}")
                    parsed_output["error_parsing_json"] = str(e)
            else:  # Linux or macOS (ps aux output)
                lines = result.stdout.splitlines()
                if len(lines) > 1:  # Skip header
                    header = lines[0].split()
                    # Example ps aux header: USER     PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
                    for line in lines[1:]:
                        parts = line.split(
                            None, len(header) - 1
                        )  # Split by whitespace, max splits based on header length
                        if len(parts) >= 11:  # Ensure enough columns for common fields
                            try:
                                process = {
                                    "user": parts[0],
                                    "pid": int(parts[1]),
                                    "cpu_percent": float(parts[2]),
                                    "mem_percent": float(parts[3]),
                                    "command": " ".join(parts[10:]),  # Command might have spaces
                                }
                                parsed_output["processes"].append(process)
                            except (ValueError, IndexError) as e:
                                self.logger.warning(f"Failed to parse process line: {line.strip()} - {e}")
            return {"ok": True, "result": parsed_output}
        else:
            self.logger.error(f"❌ Failed to list processes: {result.stderr}")
            parsed_output["error"] = result.stderr
            return {"ok": False, "result": parsed_output}

    @ollash_tool(
        name="install_package",
        description="Installs a software package using the system's package manager.",
        parameters={
            "package_name": {
                "type": "string",
                "description": "The name of the package to install.",
            },
            "package_manager": {
                "type": "string",
                "enum": ["apt", "yum", "brew", "choco", "pip"],
                "description": "The package manager to use.",
            },
        },
        toolset_id="system_tools",
        agent_types=["system"],
        required=["package_name", "package_manager"],
    )
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
        elif package_manager == "dnf" and (self.os_type == "Linux"):  # Adding dnf for modern Fedora/RHEL
            command = f"sudo dnf install -y {package_name}"
        elif package_manager == "choco" and (self.os_type == "Windows"):
            command = f"choco install {package_name} -y"
        elif package_manager == "brew" and (self.os_type == "Darwin"):
            command = f"brew install {package_name}"
        elif package_manager == "pip":
            command = f"pip install {package_name}"
        else:
            self.logger.error(
                f"Unsupported package manager '{package_manager}' for OS '{self.os_type}' or manager not recognized."
            )
            return {
                "ok": False,
                "result": {
                    "package": package_name,
                    "manager": package_manager,
                    "error": f"Unsupported package manager '{package_manager}' for OS '{self.os_type}' or manager not recognized.",
                },
            }

        result = self.exec.execute(command, timeout=300)  # Increased timeout for installation
        if result.success:
            self.logger.info(f"✅ Package {package_name} installed successfully using {package_manager}.")
            return {
                "ok": True,
                "result": {
                    "package": package_name,
                    "manager": package_manager,
                    "status": "installed",
                    "raw_output": result.stdout,
                },
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
                    "raw_output": result.stdout,
                },
            }

    @ollash_tool(
        name="read_log_file",
        description="Reads the content of a specified log file, optionally filtering by keywords or time range.",
        parameters={
            "path": {"type": "string", "description": "Path to the log file."},
            "keyword": {
                "type": "string",
                "description": "Optional: Keyword to filter log entries.",
            },
            "lines": {
                "type": "integer",
                "description": "Optional: Number of recent lines to read. Defaults to 100.",
            },
        },
        toolset_id="system_tools",
        agent_types=["system"],
        required=["path"],
    )
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
                return {
                    "ok": False,
                    "result": {"path": path, "error": "Log file not found"},
                }

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
                    "content": last_lines_content,
                },
            }
        except Exception as e:
            self.logger.error(f"❌ Error reading log file {path}: {e}", e)
            return {
                "ok": False,
                "result": {"path": path, "error": str(e), "raw_error": str(e)},
            }

    @ollash_tool(
        name="check_resource_threshold",
        description="Checks if a system resource (disk/ram) is below a specified free percentage threshold.",
        parameters={
            "resource": {
                "type": "string",
                "enum": ["disk", "ram"],
                "description": "The resource to check: 'disk' or 'ram'",
            },
            "threshold_percent": {
                "type": "integer",
                "description": "Alert if free percentage is below this threshold (0-100)",
            },
        },
        toolset_id="system_tools",
        agent_types=["system", "orchestrator"],
        required=["resource", "threshold_percent"],
    )
    def check_resource_threshold(self, resource: str, threshold_percent: int):
        """
        Checks if a system resource (disk/ram) is below a critical threshold.
        Returns alert status and current free percentage.
        """
        self.logger.info(f"🔍 Checking {resource} resource threshold (alert if < {threshold_percent}%)...")

        if resource not in ["disk", "ram"]:
            return {
                "ok": False,
                "error": f"Invalid resource: {resource}. Must be 'disk' or 'ram'",
            }

        try:
            # Get system info first
            info_result = self.get_system_info()
            if not info_result.get("ok"):
                return {"ok": False, "error": "Failed to retrieve system information"}

            system_info = info_result.get("result", {})
            current_free_percent = None
            total = None
            used = None
            free = None

            # Parse resource info based on OS
            if self.os_type == "Windows":
                info = system_info.get("info", {})
                if resource == "ram":
                    total_mem = info.get("TotalPhysicalMemory", 0)
                    free_mem = info.get("FreePhysicalMemory", 0)
                    if total_mem > 0:
                        current_free_percent = (free_mem / total_mem) * 100
                        total = total_mem
                        used = total_mem - free_mem
                        free = free_mem

            elif self.os_type in ["Linux", "Darwin"]:
                # Use `df` for disk, `free` for memory
                if resource == "disk":
                    df_cmd = "df -h /" if self.os_type == "Linux" else "df -h /"
                    result = self.exec.execute(df_cmd)
                    if result.success:
                        # Parse df output: Filesystem Size Used Avail Use% Mounted on
                        lines = result.stdout.splitlines()
                        if len(lines) > 1:
                            parts = lines[1].split()
                            if len(parts) >= 4:
                                try:
                                    # parts[3] is Avail, parts[1] is Size
                                    avail_str = parts[3].rstrip("KMGT")
                                    size_str = parts[1].rstrip("KMGT")
                                    avail = float(avail_str)
                                    size = float(size_str)
                                    current_free_percent = (avail / size) * 100 if size > 0 else 0
                                    total = size
                                    used = size - avail
                                    free = avail
                                except (ValueError, IndexError):
                                    pass

                elif resource == "ram":
                    free_cmd = "free -b" if self.os_type == "Linux" else "vm_stat"
                    result = self.exec.execute(free_cmd)
                    if result.success and self.os_type == "Linux":
                        lines = result.stdout.splitlines()
                        if len(lines) > 1:
                            parts = lines[1].split()
                            if len(parts) >= 7:
                                try:
                                    total = int(parts[1])
                                    used = int(parts[2])
                                    free = int(parts[3])
                                    current_free_percent = (free / total) * 100 if total > 0 else 0
                                except (ValueError, IndexError):
                                    pass

            if current_free_percent is None:
                return {
                    "ok": True,
                    "alert": False,
                    "message": f"Could not determine {resource} usage for this OS",
                    "resource": resource,
                }

            alert_triggered = current_free_percent < threshold_percent

            return {
                "ok": True,
                "alert": alert_triggered,
                "resource": resource,
                "current_free_percent": round(current_free_percent, 2),
                "threshold_percent": threshold_percent,
                "total": total,
                "used": used,
                "free": free,
                "message": f"⚠️ {resource.upper()} CRITICAL" if alert_triggered else f"✅ {resource.upper()} OK",
                "severity": "critical" if alert_triggered else "info",
            }

        except Exception as e:
            self.logger.error(f"❌ Error checking {resource} threshold: {e}")
            return {"ok": False, "error": str(e)}
