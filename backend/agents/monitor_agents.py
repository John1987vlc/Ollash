"""Specialized agents for proactive system monitoring."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from backend.agents.default_agent import DefaultAgent
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.core.system.metrics_database import get_metrics_database
from frontend.services.chat_event_bridge import ChatEventBridge

logger = logging.getLogger(__name__)


class SystemMonitorAgent:
    """Agent specialized in proactive system maintenance and monitoring."""

    def __init__(self, ollash_root_dir: Path, event_publisher: EventPublisher):
        """
        Initialize system monitor agent.

        Args:
            ollash_root_dir: Root directory
            event_publisher: Event publisher for notifications
        """
        self.ollash_root_dir = ollash_root_dir
        self.event_publisher = event_publisher
        self.metrics_db = get_metrics_database(ollash_root_dir)

    async def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive system health check and record metrics.

        Returns:
            Dictionary with health status and issues found
        """
        try:
            bridge = ChatEventBridge(self.event_publisher)
            agent = DefaultAgent(
                project_root=None,
                auto_confirm=True,
                base_path=self.ollash_root_dir,
                event_bridge=bridge,
            )
            agent.active_agent_type = "system"

            # Get system info
            logger.info("Starting system health check...")
            result = await asyncio.to_thread(
                agent.chat,
                """Get detailed system information including:
1. CPU usage and available cores
2. RAM usage (total, used, free)
3. Disk usage for all drives
4. System uptime
5. Running processes count

Format as structured data and highlight any critical issues.""",
            )

            # Parse and record metrics
            self._record_system_metrics(result)

            # Analyze for issues
            issues = self._analyze_health_issues(result)

            return {
                "status": "healthy" if not issues else "issues_found",
                "timestamp": datetime.now().isoformat(),
                "report": result,
                "issues": issues,
            }

        except Exception as e:
            logger.error(f"System health check failed: {e}")
            return {"status": "error", "error": str(e)}

    async def cleanup_system(self) -> Dict[str, Any]:
        """
        Perform automatic system cleanup (cache, temp files, etc).

        Returns:
            Dictionary with cleanup results
        """
        try:
            bridge = ChatEventBridge(self.event_publisher)
            agent = DefaultAgent(
                project_root=None,
                auto_confirm=True,
                base_path=self.ollash_root_dir,
                event_bridge=bridge,
            )
            agent.active_agent_type = "system"

            logger.info("Starting system cleanup...")
            result = await asyncio.to_thread(
                agent.chat,
                """Perform system cleanup:
1. Find and report size of __pycache__ directories
2. Look for temporary files (*.tmp, *.log if older than 7 days)
3. Check for unused dependencies or old virtual environments
4. Report total space that could be freed

Don't delete anything yet, just report findings.""",
            )

            return {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "cleanup_report": result,
            }

        except Exception as e:
            logger.error(f"System cleanup failed: {e}")
            return {"status": "error", "error": str(e)}

    async def analyze_logs(self, log_patterns: Optional[list] = None) -> Dict[str, Any]:
        """
        Analyze system logs for error patterns.

        Args:
            log_patterns: Optional list of patterns to search for

        Returns:
            Analysis results
        """
        try:
            bridge = ChatEventBridge(self.event_publisher)
            agent = DefaultAgent(
                project_root=None,
                auto_confirm=True,
                base_path=self.ollash_root_dir,
                event_bridge=bridge,
            )
            agent.active_agent_type = "system"

            logger.info("Analyzing system logs...")
            result = await asyncio.to_thread(
                agent.chat,
                """Analyze system logs for:
1. Error patterns and frequency
2. Warning messages
3. Critical events
4. Performance issues

Summarize findings by severity.""",
            )

            return {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "analysis": result,
            }

        except Exception as e:
            logger.error(f"Log analysis failed: {e}")
            return {"status": "error", "error": str(e)}

    def _record_system_metrics(self, report: str) -> None:
        """Extract and record metrics from system report."""
        try:
            # Simple extraction - can be enhanced with better parsing
            if "CPU" in report or "cpu" in report:
                self.metrics_db.record_metric("system", "cpu_check", 1, {"reported": True})
            if "RAM" in report or "Memory" in report or "memory" in report:
                self.metrics_db.record_metric("system", "memory_check", 1, {"reported": True})
            if "Disk" in report or "disk" in report:
                self.metrics_db.record_metric("system", "disk_check", 1, {"reported": True})
        except Exception as e:
            logger.error(f"Error recording system metrics: {e}")

    def _analyze_health_issues(self, report: str) -> list:
        """Identify health issues from the report."""
        issues = []

        keywords = {
            "critical": ["CRITICAL", "ERROR", "FAIL", "Down", "offline"],
            "warning": ["WARNING", "WARN", "High", "Low disk", "Memory pressure"],
            "info": ["INFO", "OK", "Healthy"],
        }

        for issue_type, keywords_list in keywords.items():
            for keyword in keywords_list:
                if keyword in report:
                    issues.append({"severity": issue_type, "keyword": keyword})

        return issues


class NetworkMonitorAgent:
    """Agent specialized in network uptime and connectivity monitoring."""

    def __init__(self, ollash_root_dir: Path, event_publisher: EventPublisher):
        """Initialize network monitor agent."""
        self.ollash_root_dir = ollash_root_dir
        self.event_publisher = event_publisher
        self.metrics_db = get_metrics_database(ollash_root_dir)

    async def check_services_uptime(self, services: Optional[list] = None) -> Dict[str, Any]:
        """
        Check uptime of critical services using heartbeat pings.

        Args:
            services: List of IP addresses or hostnames to check

        Returns:
            Uptime status for each service
        """
        try:
            bridge = ChatEventBridge(self.event_publisher)
            agent = DefaultAgent(
                project_root=None,
                auto_confirm=True,
                base_path=self.ollash_root_dir,
                event_bridge=bridge,
            )
            agent.active_agent_type = "network"

            if not services:
                services = ["8.8.8.8", "1.1.1.1", "localhost"]

            services_str = ", ".join(services)
            logger.info(f"Checking uptime for services: {services_str}")

            result = await asyncio.to_thread(
                agent.chat,
                f"""Check connectivity/heartbeat for these services: {services_str}
For each service, report:
1. Host/IP
2. Response time (ping)
3. Status (UP/DOWN)
4. Last successful connection time""",
            )

            # Record metrics
            self.metrics_db.record_metric("network", "uptime_check", 1, {"result": "completed"})

            return {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "services_report": result,
            }

        except Exception as e:
            logger.error(f"Service uptime check failed: {e}")
            return {"status": "error", "error": str(e)}

    async def detect_port_issues(self, ports: Optional[list] = None) -> Dict[str, Any]:
        """
        Detect issues with critical ports.

        Args:
            ports: List of port numbers to check

        Returns:
            Port status report
        """
        try:
            bridge = ChatEventBridge(self.event_publisher)
            agent = DefaultAgent(
                project_root=None,
                auto_confirm=True,
                base_path=self.ollash_root_dir,
                event_bridge=bridge,
            )
            agent.active_agent_type = "network"

            if not ports:
                ports = [80, 443, 22, 3306, 5432, 8080, 5000]

            ports_str = ", ".join(map(str, ports))
            logger.info(f"Checking ports: {ports_str}")

            result = await asyncio.to_thread(
                agent.chat,
                f"""Check status of these ports: {ports_str}
For each port, report:
1. Port number
2. Status (OPEN/CLOSED/FILTERED)
3. Service listening (if identifiable)
4. Last seen change""",
            )

            self.metrics_db.record_metric("network", "port_check", 1, {"result": "completed"})

            return {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "ports_report": result,
            }

        except Exception as e:
            logger.error(f"Port check failed: {e}")
            return {"status": "error", "error": str(e)}


class SecurityMonitorAgent:
    """Agent specialized in security monitoring and auditing."""

    def __init__(self, ollash_root_dir: Path, event_publisher: EventPublisher):
        """Initialize security monitor agent."""
        self.ollash_root_dir = ollash_root_dir
        self.event_publisher = event_publisher
        self.metrics_db = get_metrics_database(ollash_root_dir)

    async def integrity_scan(self, file_paths: Optional[list] = None) -> Dict[str, Any]:
        """
        Perform file integrity scanning on critical files.

        Args:
            file_paths: List of file paths to scan

        Returns:
            Integrity check results
        """
        try:
            bridge = ChatEventBridge(self.event_publisher)
            agent = DefaultAgent(
                project_root=None,
                auto_confirm=True,
                base_path=self.ollash_root_dir,
                event_bridge=bridge,
            )
            agent.active_agent_type = "cybersecurity"

            if not file_paths:
                file_paths = [
                    "backend/config/llm_models.json",
                    "backend/config/tool_settings.json",
                    "requirements.txt",
                    "docker-compose.yml",
                ]

            files_str = ", ".join(file_paths)
            logger.info(f"Scanning file integrity for: {files_str}")

            result = await asyncio.to_thread(
                agent.chat,
                f"""Perform integrity check on these files: {files_str}
For each file:
1. Calculate current hash (MD5/SHA256)
2. Check file size and modification time
3. Verify permissions
4. Report any unauthorized changes detected""",
            )

            self.metrics_db.record_metric("security", "integrity_scan", 1, {"result": "completed"})

            return {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "integrity_report": result,
            }

        except Exception as e:
            logger.error(f"Integrity scan failed: {e}")
            return {"status": "error", "error": str(e)}

    async def security_log_analysis(self) -> Dict[str, Any]:
        """
        Analyze security logs for suspicious activity.

        Returns:
            Security analysis results
        """
        try:
            bridge = ChatEventBridge(self.event_publisher)
            agent = DefaultAgent(
                project_root=None,
                auto_confirm=True,
                base_path=self.ollash_root_dir,
                event_bridge=bridge,
            )
            agent.active_agent_type = "cybersecurity"

            logger.info("Analyzing security logs...")

            result = await asyncio.to_thread(
                agent.chat,
                """Analyze security logs for:
1. Failed login attempts (frequency, sources)
2. Unauthorized access attempts
3. Permission changes on sensitive files
4. Process anomalies
5. Network suspicious connections

Summarize threats by severity (Critical/High/Medium/Low)""",
            )

            self.metrics_db.record_metric("security", "log_analysis", 1, {"result": "completed"})

            return {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "security_analysis": result,
            }

        except Exception as e:
            logger.error(f"Security analysis failed: {e}")
            return {"status": "error", "error": str(e)}

    async def vulnerability_scan(self) -> Dict[str, Any]:
        """
        Scan for known vulnerabilities in dependencies.

        Returns:
            Vulnerability report
        """
        try:
            bridge = ChatEventBridge(self.event_publisher)
            agent = DefaultAgent(
                project_root=None,
                auto_confirm=True,
                base_path=self.ollash_root_dir,
                event_bridge=bridge,
            )
            agent.active_agent_type = "cybersecurity"

            logger.info("Scanning for vulnerabilities...")

            result = await asyncio.to_thread(
                agent.chat,
                """Scan dependencies for known vulnerabilities:
1. Check Python packages (pip check, safety)
2. Check npm packages if any
3. Check system-level libraries
4. List outdated packages
5. Report CVEs and severity levels""",
            )

            self.metrics_db.record_metric("security", "vulnerability_scan", 1, {"result": "completed"})

            return {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "vulnerability_report": result,
            }

        except Exception as e:
            logger.error(f"Vulnerability scan failed: {e}")
            return {"status": "error", "error": str(e)}


# Factory function to create monitor agents
def create_monitor_agents(ollash_root_dir: Path, event_publisher: EventPublisher) -> Dict[str, Any]:
    """Create all monitor agent instances."""
    return {
        "system": SystemMonitorAgent(ollash_root_dir, event_publisher),
        "network": NetworkMonitorAgent(ollash_root_dir, event_publisher),
        "security": SecurityMonitorAgent(ollash_root_dir, event_publisher),
    }
