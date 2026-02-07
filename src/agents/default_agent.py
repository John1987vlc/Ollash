import hashlib
import json
import requests
import traceback # Added
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from src.utils.core.agent_logger import AgentLogger
from src.utils.core.token_tracker import TokenTracker
from src.utils.core.file_manager import FileManager
from src.utils.core.command_executor import CommandExecutor, SandboxLevel
from src.utils.core.git_manager import GitManager
from src.utils.core.code_analyzer import CodeAnalyzer

# Tool implementations
from src.utils.core.tool_interface import ToolExecutor
from src.utils.domains.code.file_system_tools import FileSystemTools
from src.utils.domains.code.code_analysis_tools import CodeAnalysisTools
from src.utils.domains.command_line.command_line_tools import CommandLineTools
from src.utils.domains.git.git_operations_tools import GitOperationsTools
from src.utils.domains.planning.planning_tools import PlanningTools
from src.utils.domains.network.network_tools import NetworkTools
from src.utils.domains.system.system_tools import SystemTools
from src.utils.domains.cybersecurity.cybersecurity_tools import CybersecurityTools
# New advanced toolsets
from src.utils.domains.orchestration.orchestration_tools import OrchestrationTools
from src.utils.domains.code.advanced_code_tools import AdvancedCodeTools
from src.utils.domains.system.advanced_system_tools import AdvancedSystemTools
from src.utils.domains.network.advanced_network_tools import AdvancedNetworkTools
from src.utils.domains.cybersecurity.advanced_cybersecurity_tools import AdvancedCybersecurityTools
from src.utils.domains.bonus.bonus_tools import BonusTools
from src.utils.core.all_tool_definitions import get_filtered_tool_definitions # Added

# Initialize colorama (needed for print statements in some tool methods)
from colorama import init, Fore, Style
init(autoreset=True)




# ======================================================
# OLLAMA CLIENT WITH BETTER ERROR HANDLING
# ======================================================

class OllamaClient:
    def __init__(self, url: str, model: str, timeout: int, logger: AgentLogger):
        self.url = f"{url}/api/chat"
        self.model = model
        self.timeout = timeout
        self.logger = logger

    def chat(self, messages: List[Dict], tools: List[Dict]) -> tuple[Dict, Dict]:
        """
        Returns (response_data, usage_stats)
        Enhanced with better error handling and logging
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 4096
            }
        }
        
        try:
            # Log request details
            self.logger.debug(f"Sending request to {self.url}")
            self.logger.debug(f"Model: {self.model}")
            self.logger.debug(f"Messages count: {len(messages)}")
            self.logger.debug(f"Tools count: {len(tools)}")
            
            # Log tool names for debugging
            tool_names = [t["function"]["name"] for t in tools]
            self.logger.debug(f"Available tools: {', '.join(tool_names)}")
            
            # Make request
            r = requests.post(self.url, json=payload, timeout=self.timeout)
            
            # Log response status
            self.logger.debug(f"Response status: {r.status_code}")
            
            # Check for errors
            if r.status_code != 200:
                error_detail = ""
                try:
                    error_data = r.json()
                    error_detail = error_data.get("error", str(error_data))
                except:
                    error_detail = r.text[:500]
                
                self.logger.error(f"Ollama API Error (Status {r.status_code})")
                self.logger.error(f"Error detail: {error_detail}")
                
                # Check if it's a tool not found error
                if "tool" in error_detail.lower() and "not found" in error_detail.lower():
                    self.logger.warning("The model tried to use a tool that doesn't exist.")
                    self.logger.warning(f"Available tools: {', '.join(tool_names)}")
                    self.logger.warning("This usually means:")
                    self.logger.warning("  1. The system prompt mentions a tool that isn't defined")
                    self.logger.warning("  2. The tool definition has a typo")
                    self.logger.warning("  3. The tool wasn't registered in tool_functions")
                
                # Don't log full payload by default (can be huge)
                self.logger.debug(f"Request had {len(messages)} messages and {len(tools)} tools")
                
                raise requests.exceptions.HTTPError(
                    f"Ollama API returned {r.status_code}: {error_detail}",
                    response=r
                )
            
            r.raise_for_status()
            data = r.json()
            
            # Estimate tokens (rough approximation: 1 token ≈ 4 chars)
            prompt_chars = sum(len(json.dumps(m)) for m in messages)
            completion_chars = len(json.dumps(data.get("message", {})))
            
            usage = {
                "prompt_tokens": prompt_chars // 4,
                "completion_tokens": completion_chars // 4,
                "total_tokens": (prompt_chars + completion_chars) // 4
            }
            
            return data, usage
            
        except requests.exceptions.Timeout:
            self.logger.error(f"Request timeout after {self.timeout}s")
            raise
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error: Cannot connect to Ollama at {self.url}")
            self.logger.error("Make sure Ollama is running: 'ollama serve'")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in API call: {str(e)}", e)
            raise


# ======================================================
# CODE AGENT (ENHANCED & FIXED)
# ======================================================

class DefaultAgent:
    def __init__(self, project_root: str | None = None):
        self.project_root = Path(project_root or Path.cwd())
        self.conversation: List[Dict] = []
        self._current_plan: Optional[Dict] = None # Keeping it here for now as discussed for reporting.
        self.loop_detection_history: List[Dict] = [] # Stores recent tool calls and results for loop detection
        self.loop_detection_threshold: int = 3 # Number of consecutive identical actions to detect a loop
        self.stagnation_timeout: timedelta = timedelta(minutes=2) # Time without meaningful progress to detect stagnation
        self.last_meaningful_action_time: datetime = datetime.now()
        self.progress_score: float = 0.0 # Heuristic score to track progress
        self.domain_context_memory: Dict[str, str] = {} # Short-term memory for domain-specific context

        # ---------------- LOGGING
        self.logger = AgentLogger(
            log_file=str(self.project_root / "agent.log")
        )
        self.logger.info(f"\n{Fore.GREEN}{'='*60}")
        self.logger.info(f"🤖 Code Agent Initialized")
        self.logger.info(f"{'='*60}{Style.RESET_ALL}")
        self.logger.info(f"📁 Project: {self.project_root}")

        # ---------------- CONFIG LOAD
        config_path = self.project_root / "config" / "settings.json"
        if not config_path.exists():
            self.logger.error(f"Config file not found: {config_path}")
            raise FileNotFoundError(f"No existe config: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.max_iterations = self.config.get("max_iterations", 30)
        
        # Load system prompt from file
        default_prompt_path = self.config.get(
            "default_system_prompt_path",
            "prompts/code/default_agent.json" # Default path if not specified
        )
        try:
            full_prompt_path = self.project_root / default_prompt_path
            with open(full_prompt_path, "r", encoding="utf-8") as f:
                prompt_data = json.load(f)
            self.system_prompt = prompt_data.get("prompt", "")
            if not self.system_prompt:
                self.logger.warning(f"System prompt 'prompt' field empty in {full_prompt_path}. Using default fallback.")
                self.system_prompt = """You are a disciplined coding agent. 
RULES:
1. ALWAYS start with plan_actions to show what you'll do
2. ASK for confirmation before: write_file, delete_file, git_commit, git_push
3. Use read_files (plural) to read multiple files at once efficiently
4. Use summarize_files (plural) to summarize multiple files at once
5. Use analyze_project to get a comprehensive overview of the project
6. Be clear and concise in your explanations"""
        except FileNotFoundError:
            self.logger.error(f"System prompt file not found: {full_prompt_path}. Using default fallback.")
            self.system_prompt = """You are a disciplined coding agent. 
RULES:
1. ALWAYS start with plan_actions to show what you'll do
2. ASK for confirmation before: write_file, delete_file, git_commit, git_push
3. Use read_files (plural) to read multiple files at once efficiently
4. Use summarize_files (plural) to summarize multiple files at once
5. Use analyze_project to get a comprehensive overview of the project
6. Be clear and concise in your explanations"""
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding system prompt JSON from {full_prompt_path}. Using default fallback.")
            self.system_prompt = """You are a disciplined coding agent. 
RULES:
1. ALWAYS start with plan_actions to show what you'll do
2. ASK for confirmation before: write_file, delete_file, git_commit, git_push
3. Use read_files (plural) to read multiple files at once efficiently
4. Use summarize_files (plural) to summarize multiple files at once
5. Use analyze_project to get a comprehensive overview of the project
6. Be clear and concise in your explanations"""
        except Exception as e:
            self.logger.error(f"Unexpected error loading system prompt from {full_prompt_path}: {e}. Using default fallback.")
            self.system_prompt = """You are a disciplined coding agent. 
RULES:
1. ALWAYS start with plan_actions to show what you'll do
2. ASK for confirmation before: write_file, delete_file, git_commit, git_push
3. Use read_files (plural) to read multiple files at once efficiently
4. Use summarize_files (plural) to summarize multiple files at once
5. Use analyze_project to get a comprehensive overview of the project
6. Be clear and concise in your explanations"""

        # ---------------- TOKEN TRACKING
        self.token_tracker = TokenTracker()

        # ---------------- CORE SERVICES
        try:
            self.file_manager = FileManager(str(self.project_root))
            self.command_executor = CommandExecutor(str(self.project_root), SandboxLevel.LIMITED, logger=self.logger)
            self.git_manager = GitManager(str(self.project_root))
            self.code_analyzer = CodeAnalyzer(str(self.project_root))
        except Exception as e:
            self.logger.error(f"Failed to initialize core services: {e}", e)
            raise

        # ---------------- TOOL EXECUTOR & TOOL SETS
        self.tool_executor = ToolExecutor(logger=self.logger, config=self.config) # Pass the logger and config instance
        
        self.file_system_tools = FileSystemTools(
            project_root=self.project_root,
            file_manager=self.file_manager,
            logger=self.logger,
            tool_executor=self.tool_executor
        )
        self.code_analysis_tools = CodeAnalysisTools(
            project_root=self.project_root,
            code_analyzer=self.code_analyzer,
            command_executor=self.command_executor,
            logger=self.logger
        )
        self.command_line_tools = CommandLineTools(
            command_executor=self.command_executor,
            logger=self.logger
        )
        self.git_operations_tools = GitOperationsTools(
            git_manager=self.git_manager,
            logger=self.logger,
            tool_executor=self.tool_executor
        )
        self.planning_tools = PlanningTools(
            logger=self.logger,
            project_root=self.project_root,
            agent_instance=self # Pass self here
        )
        self.network_tools = NetworkTools(
            command_executor=self.command_executor,
            logger=self.logger
        )
        self.system_tools = SystemTools(
            command_executor=self.command_executor,
            file_manager=self.file_manager,
            logger=self.logger
        )
        self.cybersecurity_tools = CybersecurityTools(
            command_executor=self.command_executor,
            file_manager=self.file_manager,
            logger=self.logger
        )
        self.orchestration_tools = OrchestrationTools(logger=self.logger)
        self.advanced_code_tools = AdvancedCodeTools(
            project_root=self.project_root,
            code_analyzer=self.code_analyzer,
            command_executor=self.command_executor,
            logger=self.logger
        )
        self.advanced_system_tools = AdvancedSystemTools(
            command_executor=self.command_executor,
            logger=self.logger
        )
        self.advanced_network_tools = AdvancedNetworkTools(
            command_executor=self.command_executor,
            logger=self.logger
        )
        self.advanced_cybersecurity_tools = AdvancedCybersecurityTools(
            command_executor=self.command_executor,
            file_manager=self.file_manager,
            logger=self.logger
        )
        self.bonus_tools = BonusTools(logger=self.logger)

        # ---------------- OLLAMA
        self.ollama = OllamaClient(
            url=self.config.get("ollama_url", "http://localhost:11434"),
            model=self.config.get("model", "qwen3-coder-next"),
            timeout=self.config.get("timeout", 300),
            logger=self.logger
        )
        
        self.logger.info(f"🔗 Ollama: {self.config.get('ollama_url')}")
        self.logger.info(f"🧠 Model: {self.config.get('model')}")

        # All tool instances, organized by their method name to make dynamic assignment easier
        self._all_tool_instances = {
            # Basic Tools
            "plan_actions": self.planning_tools.plan_actions,
            "select_agent_type": self.planning_tools.select_agent_type,
            "analyze_project": self.code_analysis_tools.analyze_project,
            "read_file": self.file_system_tools.read_file,
            "read_files": self.file_system_tools.read_files,
            "write_file": self.file_system_tools.write_file,
            "delete_file": self.file_system_tools.delete_file,
            "file_diff": self.file_system_tools.file_diff,
            "summarize_file": self.file_system_tools.summarize_file,
            "summarize_files": self.file_system_tools.summarize_files,
            "search_code": self.code_analysis_tools.search_code,
            "run_command": self.command_line_tools.run_command,
            "run_tests": self.command_line_tools.run_tests,
            "validate_change": self.command_line_tools.validate_change,
            "git_status": self.git_operations_tools.git_status,
            "git_commit": self.git_operations_tools.git_commit,
            "git_push": self.git_operations_tools.git_push,
            "list_directory": self.file_system_tools.list_directory,
            "ping_host": self.network_tools.ping_host,
            "traceroute_host": self.network_tools.traceroute_host,
            "list_active_connections": self.network_tools.list_active_connections,
            "check_port_status": self.network_tools.check_port_status,
            "get_system_info": self.system_tools.get_system_info,
            "list_processes": self.system_tools.list_processes,
            "install_package": self.system_tools.install_package,
            "read_log_file": self.system_tools.read_log_file,
            "scan_ports": self.cybersecurity_tools.scan_ports,
            "check_file_hash": self.cybersecurity_tools.check_file_hash,
            "analyze_security_log": self.cybersecurity_tools.analyze_security_log,
            "recommend_security_hardening": self.cybersecurity_tools.recommend_security_hardening,
            
            # Advanced Tools (Orchestration/Meta)
            "evaluate_plan_risk": self.orchestration_tools.evaluate_plan_risk,
            "detect_user_intent": self.orchestration_tools.detect_user_intent,
            "require_human_gate": self.orchestration_tools.require_human_gate,
            "summarize_session_state": self.orchestration_tools.summarize_session_state,
            "explain_decision": self.orchestration_tools.explain_decision,
            "validate_environment_expectations": self.orchestration_tools.validate_environment_expectations,
            "detect_configuration_drift": self.orchestration_tools.detect_configuration_drift,
            "evaluate_compliance": self.orchestration_tools.evaluate_compliance, # Added
            "generate_audit_report": self.orchestration_tools.generate_audit_report, # Added
            "propose_governance_policy": self.orchestration_tools.propose_governance_policy, # Added

            # Advanced Tools (Code)
            "detect_code_smells": self.advanced_code_tools.detect_code_smells,
            "suggest_refactor": self.advanced_code_tools.suggest_refactor,
            "map_code_dependencies": self.advanced_code_tools.map_code_dependencies,
            "compare_configs": self.advanced_code_tools.compare_configs,

            # Advanced Tools (System)
            "check_disk_health": self.advanced_system_tools.check_disk_health,
            "monitor_resource_spikes": self.advanced_system_tools.monitor_resource_spikes,
            "analyze_startup_services": self.advanced_system_tools.analyze_startup_services,
            "rollback_last_change": self.advanced_system_tools.rollback_last_change,

            # Advanced Tools (Network)
            "analyze_network_latency": self.advanced_network_tools.analyze_network_latency,
            "detect_unexpected_services": self.advanced_network_tools.detect_unexpected_services,
            "map_internal_network": self.advanced_network_tools.map_internal_network,

            # Advanced Tools (Cybersecurity)
            "assess_attack_surface": self.advanced_cybersecurity_tools.assess_attack_surface,
            "detect_ioc": self.advanced_cybersecurity_tools.detect_ioc,
            "analyze_permissions": self.advanced_cybersecurity_tools.analyze_permissions,
            "security_posture_score": self.advanced_cybersecurity_tools.security_posture_score,
            
            # Bonus Tools
            "estimate_change_blast_radius": self.bonus_tools.estimate_change_blast_radius,
            "generate_runbook": self.bonus_tools.generate_runbook,
            "analyze_sentiment": self.bonus_tools.analyze_sentiment, # Added
            "generate_creative_content": self.bonus_tools.generate_creative_content, # Added
            "translate_text": self.bonus_tools.translate_text, # Added
        }

        # Mapping of agent types to their relevant tool names
        self._agent_tool_name_mappings = {
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
        
        self.active_agent_type = "orchestrator"
        self.active_tool_names = self._agent_tool_name_mappings[self.active_agent_type]
        self.tool_functions = {name: self._all_tool_instances[name] for name in self.active_tool_names}

    def _detect_loop(self) -> bool:
        """
        Detects loops:
        1. Exact repetition of N actions.
        2. Specific semantic loops (e.g., repeated low-confidence intent detection).
        3. Stagnation (no meaningful progress) over a time window.
        """
        current_time = datetime.now()

        # 1. Exact repetition (current logic, comparing full history entry)
        history_length = len(self.loop_detection_history)
        if history_length < self.loop_detection_threshold:
            pass # Not enough history yet for repetition or semantic loop detection
        else:
            last_actions = self.loop_detection_history[history_length - self.loop_detection_threshold:]
            
            # For exact repetition, we need to compare tool_name, args, and result (for now, full dict comparison)
            # This is a strict check:
            if all(action["tool_name"] == last_actions[0]["tool_name"] and
                   action["args"] == last_actions[0]["args"] and
                   action["result"] == last_actions[0]["result"] for action in last_actions):
                self.logger.warning(f"{Fore.RED}⚠️ Loop (exact repetition) detected! The agent has performed the same action {self.loop_detection_threshold} times consecutively.{Style.RESET_ALL}")
                return True

            # 2. Specific semantic loop: repeated low-confidence detect_user_intent calls
            # Check if the last N calls are detect_user_intent AND they all resulted in low confidence 'exploration'
            recent_relevant_actions = [
                a for a in self.loop_detection_history[history_length - self.loop_detection_threshold:]
                if a["tool_name"] == "detect_user_intent"
            ]
            if len(recent_relevant_actions) == self.loop_detection_threshold:
                # Check if all these detect_user_intent calls resulted in low confidence exploration
                if all(a["result"].get("result", {}).get("intent") == "exploration" and
                       a["result"].get("result", {}).get("confidence", 0.0) < 0.6
                       for a in recent_relevant_actions):
                    self.logger.warning(f"{Fore.RED}⚠️ Semantic loop (ambiguous intent) detected! Agent repeatedly calling 'detect_user_intent' with low confidence exploration. Human intervention required.{Style.RESET_ALL}")
                    return True

        # 3. Stagnation over time: If no meaningful progress in a time window
        # This condition is checked regardless of history length for specific repetition types
        if (current_time - self.last_meaningful_action_time > self.stagnation_timeout):
            self.logger.warning(f"{Fore.RED}⚠️ Stagnation detected! No meaningful action for {self.stagnation_timeout}. Human intervention required.{Style.RESET_ALL}")
            return True

        return False

    def _update_progress_score(self, tool_name: str, tool_result: Dict):
        """
        Updates a heuristic progress score based on tool execution.
        Higher score means more progress towards a goal.
        """
        initial_progress_score = self.progress_score
        
        # Example heuristics (can be refined):
        if tool_result.get("ok", False):
            if tool_name == "select_agent_type":
                self.progress_score += 1.0 # Significant progress: agent type changed
            elif tool_name == "plan_actions":
                self.progress_score += 0.5 # Planning is progress
            elif tool_name == "detect_user_intent":
                intent = tool_result.get("result", {}).get("intent")
                confidence = tool_result.get("result", {}).get("confidence", 0.0)
                if intent != "exploration" and confidence > 0.7:
                    self.progress_score += 0.3 # Clear intent detected
                elif intent == "exploration" and confidence < 0.6:
                    self.progress_score -= 0.1 # Minor negative progress for ambiguity
            # Add more rules for other tools that indicate progress (e.g., file written, command successful)
            # For simplicity, other successful tools might give minor progress
            else:
                self.progress_score += 0.1
        else: # Tool failed
            self.progress_score -= 0.2 # Negative progress for failures

        # Update last_meaningful_action_time if progress changed significantly
        if abs(self.progress_score - initial_progress_score) > 0.05: # Threshold for "significant"
            self.last_meaningful_action_time = datetime.now()

    def _summarize_context_for_domain(self, domain_type: str) -> str:
        """
        Uses the LLM to summarize the current active context for a given domain,
        based on the recent conversation history.
        """
        self.logger.info(f"Generating context summary for domain: {domain_type}")
        # Create a mini-conversation with the LLM just for summarization
        # Use a specific prompt to guide the LLM to summarize.
        # This will be a temporary call to the LLM, so it should not be added to self.conversation.
        
        # Craft a prompt for summarization based on the current conversation.
        # Limit the conversation history to avoid hitting token limits.
        recent_conversation_history = self.conversation[-5:] # Last 5 turns, for example

        summarize_prompt = {
            "role": "system",
            "content": (f"You are a helpful assistant. Based on the following conversation history for the '{domain_type}' domain, "
                        "provide a very concise summary (1-2 sentences) of the current task, relevant findings, "
                        "and what the agent was working on or trying to achieve. Focus on actionable context for resuming work.")
        }
        
        summarization_messages = [summarize_prompt] + recent_conversation_history
        
        try:
            # Call Ollama directly, bypassing tool execution, for summarization
            response_data, _ = self.ollama.chat(summarization_messages, tools=[]) # No tools for summarization
            summary = response_data.get("message", {}).get("content", "No summary available.")
            self.logger.debug(f"Generated summary for {domain_type}: {summary}")
            return summary
        except Exception as e:
            self.logger.error(f"Failed to generate context summary for {domain_type}: {e}")
            return f"Error generating summary for {domain_type}."


    def chat(self, instruction: str) -> str:
        """Main chat loop with enhanced logging and error handling"""
        self.conversation.append({"role": "user", "content": instruction})

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.conversation
        ]

        iterations = 0

        while iterations < self.max_iterations:
            iterations += 1
            self.logger.info(f"\n{Fore.MAGENTA}━━━ Iteration {iterations}/{self.max_iterations} ━━━{Style.RESET_ALL}")

            try:
                # Log API request
                self.logger.api_request(len(messages), len(self.tool_functions)) # We use the size of current tool_functions
                
                # Make API call
                response, usage = self.ollama.chat(messages, self.tool_executor.get_tool_definitions(self.active_tool_names))
                
                # Track tokens
                self.token_tracker.add_usage(
                    usage["prompt_tokens"],
                    usage["completion_tokens"]
                )
                
                # Display current usage
                self.token_tracker.display_current()
                
                msg = response["message"]

                # Check if final answer
                if "tool_calls" not in msg:
                    self.logger.api_response(False)
                    final_response = msg.get("content", "")
                    self.conversation.append(msg)
                    self.logger.info(f"{Fore.GREEN}✅ Final answer generated{Style.RESET_ALL}")
                    return final_response

                # Process tool calls
                tool_calls = msg["tool_calls"]
                self.logger.api_response(True, len(tool_calls))
                self.conversation.append(msg)

                # Execute each tool call
                for i, tc in enumerate(tool_calls, 1):
                    name = tc["function"]["name"]
                    args = tc["function"]["arguments"]
                    
                    print(f"\n{Fore.CYAN}┌─ Tool Call {i}/{len(tool_calls)} ─────────────────{Style.RESET_ALL}")
                    self.logger.tool_call(name, args)
                    
                    try:
                        # Check if tool exists
                        if name not in self.tool_functions:
                            error_msg = f"Tool '{name}' not implemented"
                            self.logger.error(error_msg)
                            result = {
                                "ok": False,
                                "error": "tool_not_found",
                                "message": error_msg,
                                "available_tools": list(self.tool_functions.keys())
                            }
                        else:
                            # Execute tool
                            result = self.tool_functions[name](**args)
                            
                            # --- Loop Detection Logic ---
                            # Only add successful tool results to history for loop detection
                            if result.get("ok", True): # Assume ok if not specified
                                # Store relevant info for loop detection, including the full result for semantic analysis
                                self.loop_detection_history.append({
                                    "tool_name": name,
                                    "args": args, # Store args directly for semantic comparison if needed
                                    "result": result, # Store full result for semantic comparison
                                    "timestamp": datetime.now()
                                })
                                
                                # Update heuristic progress score
                                self._update_progress_score(name, result)
                                
                                if self._detect_loop():
                                    loop_message = f"Detected a loop! The agent is repeatedly calling '{name}' with similar arguments/results. Human intervention required."
                                    self.logger.error(loop_message)
                                    # Trigger human gate
                                    return self.orchestration_tools.require_human_gate(
                                        action_description=loop_message,
                                        reason="Loop detected, agent is stuck in a repetitive action sequence."
                                    )
                            # --- End Loop Detection Logic ---

                            if name == "plan_actions" and result.get("ok"):
                                self._current_plan = result.get("plan_data") # Store the plan data
                            elif name == "select_agent_type" and result.get("ok"):
                                new_agent_type = result.get("new_agent_type")
                                new_system_prompt = result.get("system_prompt")
                                if new_agent_type and new_system_prompt:
                                    self.active_agent_type = new_agent_type
                                    self.system_prompt = new_system_prompt
                                    self.active_tool_names = self._agent_tool_name_mappings[self.active_agent_type]
                                    self.tool_functions = {name: self._all_tool_instances[name] for name in self.active_tool_names}
                                    self.logger.info(f"{Fore.GREEN}Switched agent type to '{self.active_agent_type}'. System prompt and available tools updated.{Style.RESET_ALL}")
                        
                        success = result.get("ok", True) if isinstance(result, dict) else True
                        
                        self.logger.tool_result(name, result, success)
                        
                        # Add result to conversation
                        self.conversation.append({
                            "role": "tool",
                            "content": json.dumps(result)
                        })
                        
                    except Exception as e:
                        error_msg = f"Tool execution failed: {str(e)}"
                        self.logger.error(error_msg, e)
                        
                        # Add error to conversation
                        self.conversation.append({
                            "role": "tool",
                            "content": json.dumps({
                                "ok": False,
                                "error": error_msg,
                                "traceback": traceback.format_exc()
                            })
                        })
                    
                    print(f"{Fore.CYAN}└────────────────────────────────────────{Style.RESET_ALL}")

            except requests.exceptions.HTTPError as e:
                self.logger.error("HTTP Error from Ollama API", e)
                error_str = str(e)
                
                # Provide helpful error messages
                if "tool" in error_str.lower() and "not found" in error_str.lower():
                    return (f"❌ API Error: The model tried to use a tool that doesn't exist.\n\n"
                           f"This usually means:\n"
                           f"1. Your system prompt mentions a tool that isn't defined\n"
                           f"2. There's a mismatch between TOOLS_DEFINITION and tool_functions\n\n"
                           f"Available tools: {', '.join(self.tool_functions.keys())}\n\n"
                           f"Check agent.log for details.")
                else:
                    return f"❌ API Error: {error_str}\n\nCheck agent.log for details."
            
            except requests.exceptions.ConnectionError:
                self.logger.error("Cannot connect to Ollama")
                return ("❌ Connection Error: Cannot connect to Ollama.\n\n"
                       "Make sure Ollama is running: 'ollama serve'\n"
                       f"Configured URL: {self.config.get('ollama_url')}")
            
            except Exception as e:
                self.logger.error(f"Unexpected error in iteration {iterations}", e)
                return f"❌ Unexpected error: {str(e)}\n\nCheck agent.log for details."

        self.logger.warning("Max iterations reached")
        return f"⚠️  Reached maximum iterations ({self.max_iterations})"

    # ==================================================
    # INTERACTIVE MODE
    # ==================================================

    def chat_mode(self):
        """Interactive chat mode with enhanced UX"""
        print(f"\n{Fore.GREEN}{'='*60}")
        print("🤖 CODE AGENT - Enhanced Interactive Mode")
        print(f"{'='*60}{Style.RESET_ALL}")
        print(f"📁 Project: {Fore.CYAN}{self.project_root}{Style.RESET_ALL}")
        print(f"📝 Logs: {Fore.CYAN}{self.project_root / 'agent.log'}{Style.RESET_ALL}")
        print(f"💡 Commands: {Fore.YELLOW}exit, quit, help{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")

        while True:
            try:
                q = input(f"\n{Fore.GREEN}👤 You: {Style.RESET_ALL}").strip()
                
                if q.lower() in {"exit", "quit", "salir"}:
                    print(self.token_tracker.get_session_summary())
                    self.logger.info("Session ended by user")
                    print(f"\n{Fore.GREEN}👋 Goodbye!{Style.RESET_ALL}\n")
                    break
                
                if q.lower() == "help":
                    print(f"\n{Fore.CYAN}Available commands:{Style.RESET_ALL}")
                    print("  • Type your request naturally")
                    print("  • 'exit' or 'quit' - End session")
                    print("  • 'help' - Show this message")
                    print(f"\n{Fore.CYAN}Available tools:{Style.RESET_ALL}")
                    for tool in sorted(self.tool_functions.keys()):
                        print(f"  • {tool}")
                    continue
                
                if not q:
                    continue
                    
                print(f"\n{Fore.MAGENTA}🤖 Agent:{Style.RESET_ALL}")
                response = self.chat(q)
                print(f"\n{response}\n")
                
            except KeyboardInterrupt:
                print(self.token_tracker.get_session_summary())
                self.logger.info("Session interrupted by user")
                print(f"\n\n{Fore.GREEN}👋 Goodbye!{Style.RESET_ALL}\n")
                break
            except Exception as e:
                self.logger.error("Error in chat mode", e)
                print(f"\n{Fore.RED}❌ Error: {e}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Check agent.log for details{Style.RESET_ALL}")


# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    try:
        agent = DefaultAgent()
        agent.chat_mode()
    except Exception as e:
        print(f"{Fore.RED}❌ Fatal error: {e}{Style.RESET_ALL}")
        logging.exception("Fatal error")