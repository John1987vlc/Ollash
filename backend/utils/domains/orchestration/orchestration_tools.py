import json  # Added
import platform  # Added
from pathlib import Path  # Added
from typing import Any, Dict, List, Optional


class OrchestrationTools:
    def __init__(self, logger: Any):
        self.logger = logger
        self.os_type = platform.system()  # "Windows", "Linux", "Darwin" (macOS)

    def evaluate_plan_risk(self, plan: Dict) -> Dict:
        """
        Evaluates a plan_actions before executing it, detecting technical, security, and impact risks.
        Analyzes plan steps for keywords that suggest high risk operations.
        """
        self.logger.info(f"Evaluating plan risk for goal: {plan.get('goal', 'N/A')}")

        risks = []
        risk_level = "low"

        high_risk_keywords = {
            "security": [
                "delete_file",
                "rm ",
                "format ",
                "git push --force",
                "revoke",
                "disable security",
                "open port",
                "firewall off",
            ],
            "technical": [
                "install package",
                "update system",
                "reboot",
                "shutdown",
                "modify critical config",
                "overwrite",
            ],
            "impact": [
                "delete",
                "remove",
                "all files",
                "entire directory",
                "production",
                "deploy",
                "wipe",
            ],
        }

        for step in plan.get("steps", []):
            step_lower = step.lower()
            for risk_type, keywords in high_risk_keywords.items():
                for keyword in keywords:
                    if keyword in step_lower:
                        risks.append({"type": risk_type, "keyword": keyword, "step": step})
                        if risk_type in ["security", "impact"]:
                            risk_level = "high"
                        elif risk_level == "low":  # Upgrade from low to medium if technical risk found
                            risk_level = "medium"

        if not risks:
            details = "No explicit high-risk keywords detected in the plan."
        else:
            details = f"Detected potential risks ({risk_level} level). Review detailed findings."

        return {
            "ok": True,
            "result": {
                "risk_level": risk_level,
                "details": details,
                "findings": risks,
                "plan_evaluated": plan,
            },
        }

    def detect_user_intent(self, user_request: str) -> Dict:
        """
        Classifies the user's real intent: exploration, debugging, production change, audit, incident, learning.
        Analyzes the user request for keywords to determine intent.
        """
        self.logger.info(f"Detecting user intent for: '{user_request[:50]}...'")

        intent_keywords = {
            "debugging": ["debug", "error", "fail", "issue", "fix", "problem"],
            "production change": ["deploy", "production", "release", "update service"],
            "audit": ["audit", "review", "check compliance", "security report"],
            "incident": ["incident", "outage", "down", "unresponsive", "urgent"],
            "learning": ["learn", "how to", "explain", "tutorial", "example"],
            "exploration": ["explore", "look at", "show", "what is", "analyze", "find"],
        }

        detected_intents = {}
        user_request_lower = user_request.lower()

        for intent, keywords in intent_keywords.items():
            for keyword in keywords:
                if keyword in user_request_lower:
                    detected_intents[intent] = detected_intents.get(intent, 0) + 1

        if detected_intents:
            # Select the intent with the most matching keywords
            best_intent = max(detected_intents, key=detected_intents.get)
            confidence = detected_intents[best_intent] / len(user_request_lower.split())  # Simple confidence
            details = f"Detected intent '{best_intent}' based on keywords."
        else:
            best_intent = "exploration"
            confidence = 0.5
            details = "No specific intent keywords detected. Defaulting to 'exploration'."

        return {
            "ok": True,
            "result": {
                "intent": best_intent,
                "confidence": round(confidence, 2),
                "details": details,
                "matching_keywords": detected_intents,
            },
        }

    def require_human_gate(self, action_description: str, reason: str) -> Dict:
        """
        Marks an action or set of actions as blocked until explicit human approval.
        In a non-interactive context, this logs the request and returns a status.
        """
        message = f"🛑 HUMAN GATE REQUIRED: Action '{action_description}' blocked. Reason: '{reason}'. Awaiting explicit human approval."
        self.logger.warning(message)

        return {
            "ok": False,  # Indicate that the action itself was not completed due to gate
            "result": {
                "status": "human_gate_requested",
                "action_description": action_description,
                "reason": reason,
                "details": message,
            },
        }

    def summarize_session_state(self, agent_state: Optional[Dict] = None) -> Dict:
        """
        Summarizes the current state of the system, changes made, decisions taken, and pending risks.
        This implementation provides a generic summary. A more complete version would
        require access to the full CodeAgent state (conversation, history, etc.).
        """
        self.logger.info("Summarizing session state...")

        # Default/generic values
        active_agent = agent_state.get("active_agent", "unknown") if agent_state else "orchestrator"
        conversation_length = agent_state.get("conversation_length", 0) if agent_state else 0
        last_user_request = agent_state.get("last_user_request", "N/A") if agent_state else "N/A"
        current_plan_goal = agent_state.get("current_plan_goal", "No active plan") if agent_state else "No active plan"

        summary_details = f"Currently operating in '{active_agent}' context. "
        summary_details += f"Conversation has {conversation_length} turns. "
        summary_details += f"Last user request: '{last_user_request}'. "
        summary_details += f"Active plan goal: '{current_plan_goal}'. "
        summary_details += "Further details on changes, decisions, and risks require full agent state access."

        return {
            "ok": True,
            "result": {
                "summary": summary_details,
                "active_agent_context": active_agent,
                "current_plan_goal": current_plan_goal,
                "last_user_request": last_user_request,
                "details_note": "This summary is limited by the context provided to this tool. For full details, the agent's complete state is required.",
            },
        }

    def explain_decision(self, decision_id: Optional[str] = None, current_context: Optional[Dict] = None) -> Dict:
        """
        Explains why the agent made a specific decision and what alternatives it discarded.
        This implementation provides a generic explanation. A more complete version would
        require access to the full CodeAgent state including its reasoning process.
        """
        self.logger.info(f"Explaining decision (ID: {decision_id or 'last'})...")

        # Generic explanation based on common agent behaviors
        if current_context and "last_tool_call" in current_context:
            decision = f"The agent decided to call '{current_context['last_tool_call']['name']}' with arguments {current_context['last_tool_call']['arguments']}."
            alternatives = "Other tools related to different domains were considered but discarded due to the focused nature of the request, or deemed less efficient."
            confidence = 0.90
        elif current_context and "user_intent" in current_context:
            decision = f"The agent decided to switch to the '{current_context['user_intent']}' agent context."
            alternatives = "Remaining in the orchestrator context or switching to another agent type were discarded as less appropriate given the detected user intent."
            confidence = 0.85
        else:
            decision = "The agent made a decision based on the current user request and available tools."
            alternatives = "Alternative paths, such as asking for clarification or attempting a different tool, were implicitly discarded as less optimal."
            confidence = 0.70

        return {
            "ok": True,
            "result": {
                "decision": decision,
                "alternatives_discarded": alternatives,
                "confidence": round(confidence, 2),
                "decision_id": decision_id,
                "details_note": "A deeper explanation requires more detailed internal state and reasoning logs from the CodeAgent.",
            },
        }

    def validate_environment_expectations(self, expectations: Dict) -> Dict:
        """
        Checks if the current environment matches what is expected (OS, version, permissions, network).
        Performs basic validation for OS type and version.
        """
        self.logger.info("Validating environment expectations...")
        validation_results = []
        overall_status = "match"

        # Validate OS Type
        if "os_type" in expectations:
            expected_os = expectations["os_type"].lower()
            current_os = self.os_type.lower()
            if expected_os in current_os:  # Check for partial match (e.g., 'linux' in 'gnulinux')
                validation_results.append(
                    {
                        "check": "os_type",
                        "expected": expected_os,
                        "actual": current_os,
                        "status": "match",
                    }
                )
            else:
                validation_results.append(
                    {
                        "check": "os_type",
                        "expected": expected_os,
                        "actual": current_os,
                        "status": "mismatch",
                    }
                )
                overall_status = "mismatch"

        # Validate OS Version (basic check, more complex would need SystemTools)
        if "os_version_prefix" in expectations:
            expected_version_prefix = str(expectations["os_version_prefix"])
            current_os_version = platform.version()  # More detailed version info
            if current_os_version.startswith(expected_version_prefix):
                validation_results.append(
                    {
                        "check": "os_version",
                        "expected_prefix": expected_version_prefix,
                        "actual": current_os_version,
                        "status": "match",
                    }
                )
            else:
                validation_results.append(
                    {
                        "check": "os_version",
                        "expected_prefix": expected_version_prefix,
                        "actual": current_os_version,
                        "status": "mismatch",
                    }
                )
                overall_status = "mismatch"

        # Placeholder for other checks (permissions, network, etc.)
        if overall_status == "match":
            details = "All checked environment expectations are met."
        else:
            details = "Some environment expectations do not match. See findings for details."

        return {
            "ok": overall_status == "match",
            "result": {
                "status": overall_status,
                "details": details,
                "findings": validation_results,
                "checked_expectations": expectations,
                "note": "Advanced checks (e.g., specific permissions, network config) would require integration with SystemTools/NetworkTools or more OS-specific commands.",
            },
        }

    def detect_configuration_drift(self, baseline_file: str, current_file: str) -> Dict:
        """
        Detects deviations with respect to a known baseline.
        Reads and compares the content of two files line by line.
        """
        self.logger.info(f"Detecting configuration drift between {baseline_file} and {current_file}...")

        try:
            baseline_path = Path(baseline_file)
            current_path = Path(current_file)

            if not baseline_path.exists():
                return {
                    "ok": False,
                    "result": {"error": f"Baseline file not found: {baseline_file}"},
                }
            if not current_path.exists():
                return {
                    "ok": False,
                    "result": {"error": f"Current file not found: {current_file}"},
                }

            baseline_content = baseline_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            current_content = current_path.read_text(encoding="utf-8", errors="ignore").splitlines()

            drift_detected = False
            differences = []

            max_lines = max(len(baseline_content), len(current_content))
            for i in range(max_lines):
                line_in_baseline = baseline_content[i].strip() if i < len(baseline_content) else ""
                line_in_current = current_content[i].strip() if i < len(current_content) else ""

                if line_in_baseline != line_in_current:
                    drift_detected = True
                    differences.append(
                        {
                            "line": i + 1,
                            "baseline_content": line_in_baseline,
                            "current_content": line_in_current,
                            "type": "modified"
                            if line_in_baseline and line_in_current
                            else "added"
                            if line_in_current
                            else "removed",
                        }
                    )

            if drift_detected:
                details = f"Configuration drift detected between {baseline_file} and {current_file}. Found {len(differences)} differences."
                self.logger.warning(details)
            else:
                details = f"No significant configuration drift detected between {baseline_file} and {current_file} (textual comparison)."
                self.logger.info(details)

            return {
                "ok": True,
                "result": {
                    "drift_detected": drift_detected,
                    "details": details,
                    "differences": differences,
                    "baseline": baseline_file,
                    "current": current_file,
                    "note": "This is a line-by-line textual comparison. Semantic differences in structured config files might require more advanced parsing.",
                },
            }

        except Exception as e:
            self.logger.error(f"Error detecting configuration drift: {e}", e)
            return {
                "ok": False,
                "result": {
                    "error": str(e),
                    "baseline": baseline_file,
                    "current": current_file,
                },
            }

    def evaluate_compliance(self, compliance_standard: str, audit_scope: List[str]) -> Dict:
        """
        Evaluates system configurations and practices against a specified compliance standard (e.g., ISO 27001, GDPR).
        Provides a generic evaluation framework, emphasizing the need for detailed, tool-specific checks.
        """
        self.logger.info(f"Evaluating compliance against {compliance_standard} for scope: {audit_scope}")

        findings = []
        overall_status = "needs_assessment"
        summary = f"Compliance evaluation initiated for '{compliance_standard}'. Detailed assessment requires tool integration."

        # Simulate some findings based on common compliance areas
        findings.append(
            {
                "control_area": "Access Control",
                "status": "partial_assessment",
                "details": "Access control policies and configurations need to be thoroughly reviewed (e.g., via `analyze_permissions` tool).",
                "recommendation": "Use `analyze_permissions` on relevant paths.",
            }
        )
        findings.append(
            {
                "control_area": "Data Protection",
                "status": "pending_assessment",
                "details": "Data encryption, backup, and retention policies require verification. Sensitive data discovery is also needed.",
                "recommendation": "Integrate with file content scanning and data classification tools.",
            }
        )
        findings.append(
            {
                "control_area": "Security Monitoring",
                "status": "partial_assessment",
                "details": "Logs and security events need to be collected and reviewed for suspicious activities (e.g., via `detect_ioc` tool).",
                "recommendation": "Use `detect_ioc` and log analysis tools.",
            }
        )
        findings.append(
            {
                "control_area": "Configuration Management",
                "status": "pending_assessment",
                "details": "System and application configurations must be hardened and regularly audited for drift (e.g., via `detect_configuration_drift` tool).",
                "recommendation": "Use `detect_configuration_drift` against known baselines.",
            }
        )

        if compliance_standard.lower() == "gdpr":
            findings.append(
                {
                    "control_area": "Privacy Impact Assessment (PIA)",
                    "status": "pending_assessment",
                    "details": "Verify that PIAs are conducted and documented for all data processing activities.",
                    "recommendation": "Manual review of PIA documentation.",
                }
            )
        elif compliance_standard.lower() == "iso 27001":
            findings.append(
                {
                    "control_area": "Risk Assessment & Treatment",
                    "status": "pending_assessment",
                    "details": "Review the organization's risk assessment methodology and treatment plans.",
                    "recommendation": "Manual review of risk management documentation.",
                }
            )

        return {
            "ok": True,
            "result": {
                "standard": compliance_standard,
                "audit_scope": audit_scope,
                "overall_status": overall_status,
                "summary": summary,
                "findings": findings,
                "note": "A true compliance audit is a complex process involving multiple tools, human expertise, and documentation review. This tool provides a high-level overview and areas for further investigation.",
            },
        }

    def generate_audit_report(self, report_format: str = "json") -> Dict:
        """
        Generates a structured report from previous tool outputs (e.g., security scan, compliance evaluation).
        Provides a generic report, emphasizing the need for integration with actual tool outputs.
        """
        self.logger.info(f"Generating audit report in {report_format} format...")

        report_content = {
            "report_title": "Automated System Audit Report",
            "generation_timestamp": "Current timestamp (placeholder)",
            "summary": "This is a generic audit report. Actual data needs to be collected from executed tools.",
            "sections": [
                {
                    "title": "Risk Assessment Overview",
                    "content": "Overall system risk appears low/medium (placeholder). Refer to `evaluate_plan_risk` for details.",
                    "note": "Requires integration with `evaluate_plan_risk` output.",
                },
                {
                    "title": "Compliance Status",
                    "content": "Compliance status is 'needs_assessment' (placeholder). Refer to `evaluate_compliance` for details.",
                    "note": "Requires integration with `evaluate_compliance` output.",
                },
                {
                    "title": "Security Posture",
                    "content": "Security posture is rated 'Good' (placeholder). Refer to `security_posture_score` for details.",
                    "note": "Requires integration with `security_posture_score` output.",
                },
                {
                    "title": "Environment Validation",
                    "content": "Environment expectations are assumed met (placeholder). Refer to `validate_environment_expectations` for details.",
                    "note": "Requires integration with `validate_environment_expectations` output.",
                },
                {
                    "title": "Configuration Drift",
                    "content": "No configuration drift detected (placeholder). Refer to `detect_configuration_drift` for details.",
                    "note": "Requires integration with `detect_configuration_drift` output.",
                },
                {
                    "title": "Recommendations",
                    "content": "To get a comprehensive report, execute specific analysis tools (e.g., security scans, permission audits) and ensure their outputs are accessible for aggregation.",
                },
            ],
        }

        if report_format == "json":
            formatted_report = json.dumps(report_content, indent=4)
        elif report_format == "text":
            formatted_report = "--- Automated System Audit Report ---\n"
            for section in report_content["sections"]:
                formatted_report += f"\n{section['title']}:\n  {section['content']}\n"
        else:
            return {
                "ok": False,
                "result": {
                    "error": f"Unsupported report format: {report_format}. Supported formats are 'json' and 'text'."
                },
            }

        return {
            "ok": True,
            "result": {
                "format": report_format,
                "report_content": formatted_report,
                "summary": "Generic audit report generated. Integrate with live tool outputs for meaningful data.",
            },
        }

    def propose_governance_policy(self, policy_type: str, scope: List[str]) -> Dict:
        """
        Proposes new governance policies or updates existing ones based on compliance gaps or best practices.
        Generates a generic policy outline based on the specified type and scope.
        """
        self.logger.info(f"Proposing governance policy of type '{policy_type}' for scope: {scope}")

        policy_template = {
            "title": f"Draft Governance Policy: {policy_type.replace('_', ' ').title()}",
            "version": "1.0",
            "status": "Draft",
            "scope": scope,
            "objectives": [
                "Establish clear guidelines for [policy_type] within the specified scope.",
                "Ensure compliance with relevant regulations and internal standards.",
                "Mitigate risks associated with [policy_type] practices.",
            ],
            "key_principles": [],
            "responsibilities": {
                "owner": "Placeholder: Define Policy Owner",
                "review_frequency": "Annually",
            },
            "review_date": "YYYY-MM-DD (placeholder)",
        }

        if policy_type.lower() == "data_handling":
            policy_template["key_principles"].extend(
                [
                    "Principle of Data Minimization",
                    "Principle of Purpose Limitation",
                    "Principle of Storage Limitation",
                    "Principle of Confidentiality and Integrity",
                ]
            )
            policy_template["objectives"].insert(0, "Protect sensitive data throughout its lifecycle.")
        elif policy_type.lower() == "access_control":
            policy_template["key_principles"].extend(
                [
                    "Principle of Least Privilege",
                    "Principle of Separation of Duties",
                    "Principle of Need-to-Know",
                ]
            )
            policy_template["objectives"].insert(0, "Ensure appropriate access to systems and information.")
        elif policy_type.lower() == "incident_response":
            policy_template["key_principles"].extend(
                [
                    "Principle of Preparedness",
                    "Principle of Timely Detection",
                    "Principle of Effective Response",
                    "Principle of Post-Incident Learning",
                ]
            )
            policy_template["objectives"].insert(0, "Define procedures for managing security incidents effectively.")
        else:
            policy_template["key_principles"].append("General Best Practice Principles")
            policy_template["objectives"].insert(0, "Establish sound governance practices.")

        return {
            "ok": True,
            "result": {
                "policy_type": policy_type,
                "proposed_policy": policy_template,
                "summary": f"Draft governance policy for '{policy_type}' generated. Content should be reviewed and expanded with specific organizational details. (Scope: {', '.join(scope)})",
                "note": "A complete policy requires specific details, legal review, and alignment with organizational context.",
            },
        }
