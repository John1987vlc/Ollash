from typing import Dict, List, Any, Callable, Optional


class ToolRegistry:
    """Centralized registry for tool-to-toolset mapping and agent-type tool routing.

    Extracted from DefaultAgent to reduce its responsibilities.
    """

    # Maps tool_name -> (toolset_identifier, method_name_in_toolset)
    TOOL_MAPPING: Dict[str, tuple] = {
        # Planning
        "plan_actions": ("planning_tools", "plan_actions"),
        "select_agent_type": ("planning_tools", "select_agent_type"),
        # File System
        "analyze_project": ("code_analysis_tools", "analyze_project"),
        "read_file": ("file_system_tools", "read_file"),
        "read_files": ("file_system_tools", "read_files"),
        "write_file": ("file_system_tools", "write_file"),
        "delete_file": ("file_system_tools", "delete_file"),
        "file_diff": ("file_system_tools", "file_diff"),
        "summarize_file": ("file_system_tools", "summarize_file"),
        "summarize_files": ("file_system_tools", "summarize_files"),
        "list_directory": ("file_system_tools", "list_directory"),
        # Code Analysis
        "search_code": ("code_analysis_tools", "search_code"),
        # Command Line
        "run_command": ("command_line_tools", "run_command"),
        "run_tests": ("command_line_tools", "run_tests"),
        "validate_change": ("command_line_tools", "validate_change"),
        # Git
        "git_status": ("git_operations_tools", "git_status"),
        "git_commit": ("git_operations_tools", "git_commit"),
        "git_push": ("git_operations_tools", "git_push"),
        # Network
        "ping_host": ("network_tools", "ping_host"),
        "traceroute_host": ("network_tools", "traceroute_host"),
        "list_active_connections": ("network_tools", "list_active_connections"),
        "check_port_status": ("network_tools", "check_port_status"),
        # System
        "get_system_info": ("system_tools", "get_system_info"),
        "list_processes": ("system_tools", "list_processes"),
        "install_package": ("system_tools", "install_package"),
        "read_log_file": ("system_tools", "read_log_file"),
        # Cybersecurity
        "scan_ports": ("cybersecurity_tools", "scan_ports"),
        "check_file_hash": ("cybersecurity_tools", "check_file_hash"),
        "analyze_security_log": ("cybersecurity_tools", "analyze_security_log"),
        "recommend_security_hardening": ("cybersecurity_tools", "recommend_security_hardening"),
        # Orchestration (Advanced)
        "evaluate_plan_risk": ("orchestration_tools", "evaluate_plan_risk"),
        "detect_user_intent": ("orchestration_tools", "detect_user_intent"),
        "require_human_gate": ("orchestration_tools", "require_human_gate"),
        "summarize_session_state": ("orchestration_tools", "summarize_session_state"),
        "explain_decision": ("orchestration_tools", "explain_decision"),
        "validate_environment_expectations": ("orchestration_tools", "validate_environment_expectations"),
        "detect_configuration_drift": ("orchestration_tools", "detect_configuration_drift"),
        "evaluate_compliance": ("orchestration_tools", "evaluate_compliance"),
        "generate_audit_report": ("orchestration_tools", "generate_audit_report"),
        "propose_governance_policy": ("orchestration_tools", "propose_governance_policy"),
        # Advanced Code
        "detect_code_smells": ("advanced_code_tools", "detect_code_smells"),
        "suggest_refactor": ("advanced_code_tools", "suggest_refactor"),
        "map_code_dependencies": ("advanced_code_tools", "map_code_dependencies"),
        "compare_configs": ("advanced_code_tools", "compare_configs"),
        # Advanced System
        "check_disk_health": ("advanced_system_tools", "check_disk_health"),
        "monitor_resource_spikes": ("advanced_system_tools", "monitor_resource_spikes"),
        "analyze_startup_services": ("advanced_system_tools", "analyze_startup_services"),
        "rollback_last_change": ("advanced_system_tools", "rollback_last_change"),
        # Advanced Network
        "analyze_network_latency": ("advanced_network_tools", "analyze_network_latency"),
        "detect_unexpected_services": ("advanced_network_tools", "detect_unexpected_services"),
        "map_internal_network": ("advanced_network_tools", "map_internal_network"),
        # Advanced Cybersecurity
        "assess_attack_surface": ("advanced_cybersecurity_tools", "assess_attack_surface"),
        "detect_ioc": ("advanced_cybersecurity_tools", "detect_ioc"),
        "analyze_permissions": ("advanced_cybersecurity_tools", "analyze_permissions"),
        "security_posture_score": ("advanced_cybersecurity_tools", "security_posture_score"),
        # Bonus
        "estimate_change_blast_radius": ("bonus_tools", "estimate_change_blast_radius"),
        "generate_runbook": ("bonus_tools", "generate_runbook"),
        "analyze_sentiment": ("bonus_tools", "analyze_sentiment"),
        "generate_creative_content": ("bonus_tools", "generate_creative_content"),
        "translate_text": ("bonus_tools", "translate_text"),
    }

    # Maps agent_type -> list of available tool names
    AGENT_TOOLS: Dict[str, List[str]] = {
        "orchestrator": [
            "plan_actions", "select_agent_type",
            "evaluate_plan_risk", "detect_user_intent", "require_human_gate",
            "summarize_session_state", "explain_decision",
            "validate_environment_expectations", "detect_configuration_drift",
            "evaluate_compliance", "generate_audit_report", "propose_governance_policy",
            "estimate_change_blast_radius", "generate_runbook",
            "analyze_sentiment", "generate_creative_content", "translate_text"
        ],
        "code": [
            "plan_actions", "analyze_project", "read_file", "read_files",
            "write_file", "delete_file", "file_diff", "summarize_file",
            "summarize_files", "search_code", "run_command", "run_tests",
            "validate_change", "git_status", "git_commit", "git_push",
            "list_directory", "select_agent_type", "detect_code_smells",
            "suggest_refactor", "map_code_dependencies", "compare_configs"
        ],
        "network": [
            "plan_actions", "ping_host", "traceroute_host",
            "list_active_connections", "check_port_status", "select_agent_type",
            "analyze_network_latency", "detect_unexpected_services", "map_internal_network"
        ],
        "system": [
            "plan_actions", "get_system_info", "list_processes", "install_package",
            "read_log_file", "select_agent_type", "check_disk_health",
            "monitor_resource_spikes", "analyze_startup_services", "rollback_last_change"
        ],
        "cybersecurity": [
            "plan_actions", "scan_ports", "check_file_hash", "analyze_security_log",
            "recommend_security_hardening", "select_agent_type", "assess_attack_surface",
            "detect_ioc", "analyze_permissions", "security_posture_score"
        ]
    }

    def get_toolset_for_tool(self, tool_name: str) -> Optional[tuple]:
        """Returns (toolset_identifier, method_name) for a given tool, or None."""
        return self.TOOL_MAPPING.get(tool_name)

    def get_tools_for_agent(self, agent_type: str) -> List[str]:
        """Returns the list of tool names available for a given agent type."""
        return self.AGENT_TOOLS.get(agent_type, [])

    def is_valid_tool(self, tool_name: str) -> bool:
        """Checks if a tool name exists in the registry."""
        return tool_name in self.TOOL_MAPPING

    def is_valid_agent_type(self, agent_type: str) -> bool:
        """Checks if an agent type exists in the registry."""
        return agent_type in self.AGENT_TOOLS
