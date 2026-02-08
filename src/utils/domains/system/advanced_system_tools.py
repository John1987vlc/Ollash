from typing import Any, Dict, List, Optional
import platform # Added
import re # Added

class AdvancedSystemTools:
    def __init__(self, command_executor: Any, logger: Any): # Added command_executor
        self.exec = command_executor # Stored CommandExecutor
        self.logger = logger
        self.os_type = platform.system() # "Windows", "Linux", "Darwin" (macOS)

    def check_disk_health(self) -> Dict:
        """
        Analyzes disk usage, inodes, anomalous growth, and suspicious directories.
        Uses OS-specific commands (wmic/df) to gather disk usage and inode information.
        """
        self.logger.info("Checking disk health...")
        
        partitions_info = []
        overall_status = "healthy"
        
        try:
            if self.os_type == "Windows":
                # Get disk usage
                command_disk = "wmic logicaldisk get Caption,Size,FreeSpace"
                result_disk = self.exec.execute(command_disk)
                if result_disk.success:
                    # Caption     FreeSpace    Size
                    # C:          100000000    500000000
                    lines = result_disk.stdout.splitlines()[1:] # Skip header
                    for line in lines:
                        parts = line.split()
                        if len(parts) == 3:
                            caption, freespace_str, size_str = parts
                            try:
                                total_gb = round(int(size_str) / (1024**3), 2)
                                free_gb = round(int(freespace_str) / (1024**3), 2)
                                used_gb = round(total_gb - free_gb, 2)
                                usage_percent = round((used_gb / total_gb) * 100, 2) if total_gb > 0 else 0
                                partitions_info.append({
                                    "name": caption,
                                    "total_gb": total_gb,
                                    "used_gb": used_gb,
                                    "free_gb": free_gb,
                                    "usage_percent": usage_percent,
                                    "anomalies": []
                                })
                                if usage_percent > 90:
                                    overall_status = "warning"
                                    partitions_info[-1]["anomalies"].append("High disk usage (>90%)")
                            except ValueError:
                                pass # Skip unparseable lines
                
                # Inode info is not directly available via wmic easily, might require PowerShell Get-Volume
                # For simplicity, skipping inode check on Windows for now.
                
            else: # Linux or macOS
                # Get disk usage
                command_disk = "df -h"
                result_disk = self.exec.execute(command_disk)
                if result_disk.success:
                    # Filesystem      Size  Used Avail Use% Mounted on
                    # /dev/sda1       20G  10G  9.0G  53% /
                    lines = result_disk.stdout.splitlines()[1:] # Skip header
                    for line in lines:
                        parts = line.split()
                        if len(parts) == 6:
                            filesystem, size, used, avail, use_percent, mounted_on = parts
                            try:
                                usage_percent = int(use_percent.replace('%', ''))
                                partitions_info.append({
                                    "name": mounted_on,
                                    "filesystem": filesystem,
                                    "size": size,
                                    "used": used,
                                    "available": avail,
                                    "usage_percent": usage_percent,
                                    "anomalies": []
                                })
                                if usage_percent > 90:
                                    overall_status = "warning"
                                    partitions_info[-1]["anomalies"].append("High disk usage (>90%)")
                            except ValueError:
                                pass # Skip unparseable lines

                # Get inode usage (Linux/macOS)
                command_inodes = "df -i"
                result_inodes = self.exec.execute(command_inodes)
                if result_inodes.success:
                    # Filesystem     Inodes IUsed IFree IUse% Mounted on
                    # /dev/sda1     1048576 100000 948576   10% /
                    lines = result_inodes.stdout.splitlines()[1:]
                    for line in lines:
                        parts = line.split()
                        if len(parts) == 6:
                            filesystem, inodes_total, inodes_used, inodes_free, iuse_percent, mounted_on = parts
                            try:
                                iuse_percent = int(iuse_percent.replace('%', ''))
                                # Find corresponding partition and update
                                for p in partitions_info:
                                    if p["name"] == mounted_on:
                                        p["inodes_total"] = inodes_total
                                        p["inodes_used"] = inodes_used
                                        p["inodes_free"] = inodes_free
                                        p["inodes_usage_percent"] = iuse_percent
                                        if iuse_percent > 90:
                                            overall_status = "warning"
                                            p["anomalies"].append("High inode usage (>90%)")
                                        break
                            except ValueError:
                                pass
        
        except Exception as e:
            self.logger.error(f"Error checking disk health: {e}", e)
            return {"ok": False, "result": {"error": str(e)}}

        if overall_status == "warning":
            details = "Some disk partitions show high usage or inode consumption."
        else:
            details = "Disk health appears good for all monitored partitions."

        return {
            "ok": overall_status == "healthy",
            "result": {
                "status": overall_status,
                "details": details,
                "partitions": partitions_info,
                "note": "Anomalous growth and suspicious directories require deeper file system monitoring, which is not implemented in this basic check."
            }
        }

    def monitor_resource_spikes(self, resource_type: str = "cpu", duration_minutes: int = 5) -> Dict:
        """
        Detects recent spikes in CPU, RAM, or I/O and correlates them with processes.
        Provides current resource usage and notes that spike detection requires historical data.
        """
        self.logger.info(f"Monitoring for {resource_type} spikes (current usage)...")
        
        command = ""
        parsed_output = {"resource_type": resource_type}

        if resource_type not in ["cpu", "ram", "io"]:
            return {"ok": False, "result": {"error": f"Invalid resource_type: {resource_type}. Must be 'cpu', 'ram', or 'io'."}}

        try:
            if self.os_type == "Windows":
                if resource_type == "cpu":
                    command = "powershell -command \"Get-Counter '\\Processor(_Total)\\% Processor Time' | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue | ConvertTo-Json\""
                elif resource_type == "ram":
                    command = "powershell -command \"Get-Counter '\\Memory\\Available MBytes' | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue | ConvertTo-Json\""
                elif resource_type == "io":
                    command = "powershell -command \"Get-Counter '\\PhysicalDisk(_Total)\\% Disk Time' | Select-Object -ExpandProperty CounterSamples | Select-Object -ExpandProperty CookedValue | ConvertTo-Json\""
                
                result = self.exec.execute(command)
                if result.success:
                    value = json.loads(result.stdout)
                    parsed_output["current_value"] = round(float(value), 2)
                    parsed_output["unit"] = "%" if resource_type == "cpu" or resource_type == "io" else "MB"
                    parsed_output["raw_output"] = result.stdout
                else:
                    parsed_output["error"] = result.stderr
                    return {"ok": False, "result": parsed_output}
            else: # Linux or macOS (using `top -bn1` for both CPU/RAM, `iostat` for IO)
                if resource_type == "cpu":
                    command = "top -bn1 | grep 'Cpu(s)'"
                    result = self.exec.execute(command)
                    if result.success:
                        cpu_match = re.search(r"(\d+\.?\d*)%id", result.stdout)
                        if cpu_match:
                            idle_cpu = float(cpu_match.group(1))
                            parsed_output["current_value"] = round(100 - idle_cpu, 2)
                            parsed_output["unit"] = "%"
                        parsed_output["raw_output"] = result.stdout
                elif resource_type == "ram":
                    command = "free -m | grep Mem:"
                    result = self.exec.execute(command)
                    if result.success:
                        mem_match = re.search(r"Mem:\s+(\d+)\s+(\d+)", result.stdout)
                        if mem_match:
                            total_mb = int(mem_match.group(1))
                            used_mb = int(mem_match.group(2))
                            parsed_output["total_mb"] = total_mb
                            parsed_output["used_mb"] = used_mb
                            parsed_output["free_mb"] = total_mb - used_mb
                            parsed_output["usage_percent"] = round((used_mb / total_mb) * 100, 2)
                            parsed_output["unit"] = "MB"
                        parsed_output["raw_output"] = result.stdout
                elif resource_type == "io":
                    # iostat might not be installed by default, psutil would be better
                    command = "iostat -d 1 1"
                    result = self.exec.execute(command)
                    if result.success:
                        io_match = re.search(r"avg-cpu:\s+%.*?%idle\s+(\d+\.?\d*)\s+Device:\s+.*?\s+(\d+\.?\d*)\s+(\d+\.?\d*)", result.stdout, re.DOTALL)
                        if io_match:
                            tps = float(io_match.group(2))
                            kb_read = float(io_match.group(3))
                            kb_write = float(io_match.group(4))
                            parsed_output["tps_current"] = tps
                            parsed_output["kb_read_s_current"] = kb_read
                            parsed_output["kb_write_s_current"] = kb_write
                            parsed_output["unit"] = "KB/s"
                        parsed_output["raw_output"] = result.stdout
                
                if not result.success:
                    parsed_output["error"] = result.stderr
                    return {"ok": False, "result": parsed_output}
        
        except Exception as e:
            self.logger.error(f"Error monitoring {resource_type} spikes: {e}", e)
            return {"ok": False, "result": {"error": str(e), "resource_type": resource_type}}

        return {
            "ok": True,
            "result": {
                "status": "monitoring_current_usage",
                "details": f"Current {resource_type} usage retrieved. Spike detection requires historical data logging and comparison, which is not part of this tool's basic implementation.",
                "current_usage": parsed_output,
                "note": "For true spike detection, integrate with a monitoring system or log historical usage for comparison."
            }
        }

    def analyze_startup_services(self) -> Dict:
        """
        Lists services that start with the system and evaluates if they are necessary.
        Uses OS-specific commands to retrieve and parse startup service information.
        """
        self.logger.info("Analyzing startup services...")
        
        services = []
        
        try:
            if self.os_type == "Windows":
                command = "powershell -command \"Get-WmiObject Win32_Service | Where-Object {$_.StartMode -eq 'Auto'} | Select-Object Name,DisplayName,StartMode,State | ConvertTo-Json\""
                result = self.exec.execute(command)
                if result.success:
                    ps_services = json.loads(result.stdout)
                    for svc in ps_services:
                        services.append({
                            "name": svc.get("Name"),
                            "display_name": svc.get("DisplayName"),
                            "start_mode": svc.get("StartMode"),
                            "state": svc.get("State"),
                            "recommendation": "Evaluate if this service is essential for system operation or required applications."
                        })
                else:
                    self.logger.error(f"Failed to get Windows services: {result.stderr}")
                    return {"ok": False, "result": {"error": result.stderr}}
            elif self.os_type == "Linux":
                command = "systemctl list-unit-files --type=service --state=enabled --no-pager"
                result = self.exec.execute(command)
                if result.success:
                    lines = result.stdout.splitlines()
                    for line in lines[1:]: # Skip header
                        parts = line.split()
                        if len(parts) >= 2:
                            service_name = parts[0]
                            status = parts[1]
                            services.append({
                                "name": service_name,
                                "status": status,
                                "recommendation": "Evaluate if this service is essential for system operation or required applications."
                            })
                else:
                    self.logger.error(f"Failed to get Linux services: {result.stderr}")
                    return {"ok": False, "result": {"error": result.stderr}}
            elif self.os_type == "Darwin": # macOS
                command = "launchctl list"
                result = self.exec.execute(command)
                if result.success:
                    lines = result.stdout.splitlines()
                    for line in lines[1:]: # Skip header
                        parts = line.split()
                        if len(parts) >= 3:
                            pid = parts[0]
                            status = parts[1]
                            label = parts[2]
                            services.append({
                                "name": label,
                                "pid": pid,
                                "status": status,
                                "recommendation": "Evaluate if this service is essential for system operation or required applications."
                            })
                else:
                    self.logger.error(f"Failed to get macOS services: {result.stderr}")
                    return {"ok": False, "result": {"error": result.stderr}}
            else:
                return {"ok": False, "result": {"error": f"Unsupported OS for analyze_startup_services: {self.os_type}"}}
        
        except Exception as e:
            self.logger.error(f"Error analyzing startup services: {e}", e)
            return {"ok": False, "result": {"error": str(e)}}

        summary = f"Found {len(services)} enabled startup services."
        return {
            "ok": True,
            "result": {
                "summary": summary,
                "services": services,
                "note": "Evaluation of service necessity requires domain-specific knowledge. Generic recommendations are provided."
            }
        }

    def rollback_last_change(self, change_type: str) -> Dict:
        """
        Reverts the last known change (git, config, package) in a controlled way.
        This operation is highly destructive and requires explicit human approval.
        """
        message = f"🛑 ROLLBACK REQUESTED: Attempting to roll back the last {change_type} change. This is a destructive operation and requires explicit human approval."
        self.logger.critical(message) # Use critical for destructive operations

        valid_change_types = ["git", "config", "package"]
        if change_type not in valid_change_types:
            return {
                "ok": False,
                "result": {
                    "status": "invalid_change_type",
                    "change_type": change_type,
                    "details": f"Invalid change type '{change_type}'. Must be one of: {', '.join(valid_change_types)}."
                }
            }
        
        # In a real system, this would trigger a human-in-the-loop workflow.
        # For now, we simulate by explicitly stating human approval is needed.
        return {
            "ok": False, # Action itself is not completed automatically
            "result": {
                "status": "human_gate_required",
                "change_type": change_type,
                "details": message,
                "note": "Actual rollback would be initiated after explicit human approval via a separate mechanism."
            }
        }

    def rollback_to_last_checkpoint(self) -> Dict:
        """
        Reverts the project to the last git checkpoint created by the agent.
        This is a destructive operation that uses `git reset --hard`.
        """
        self.logger.critical("Attempting to roll back to the last checkpoint...")
        try:
            # First, get the hash of the current HEAD
            result_pre_reset = self.exec.execute("git rev-parse HEAD")
            if not result_pre_reset.success:
                return {"ok": False, "result": {"error": "Failed to get current git HEAD.", "details": result_pre_reset.stderr}}
            
            head_before_reset = result_pre_reset.stdout.strip()
            
            # Perform the hard reset
            # This moves HEAD back by one commit.
            result = self.exec.execute("git reset --hard HEAD~1")
            
            if not result.success:
                return {"ok": False, "result": {"error": "git reset --hard HEAD~1 failed.", "details": result.stderr}}

            # Get the new HEAD hash to confirm the change
            result_post_reset = self.exec.execute("git rev-parse HEAD")
            if not result_post_reset.success:
                return {"ok": True, "result": {"status": "rollback_likely_successful_but_unverified", "details": "git reset command succeeded, but failed to verify the new HEAD."}}
            
            head_after_reset = result_post_reset.stdout.strip()

            if head_before_reset == head_after_reset:
                 return {"ok": False, "result": {"error": "Rollback failed. HEAD is still at the same commit.", "details": head_before_reset}}

            return {
                "ok": True,
                "result": {
                    "status": "rollback_successful",
                    "details": f"Successfully rolled back from {head_before_reset[:8]} to {head_after_reset[:8]}."
                }
            }
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during rollback: {e}", exc_info=True)
            return {"ok": False, "result": {"error": f"An unexpected error occurred during rollback: {e}"}}
