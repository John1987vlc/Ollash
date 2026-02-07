import json
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional

from src.utils.agent_logger import AgentLogger
from src.utils.token_tracker import TokenTracker
from src.utils.file_manager import FileManager
from src.utils.command_executor import CommandExecutor, SandboxLevel
from src.utils.git_manager import GitManager
from src.utils.code_analyzer import CodeAnalyzer

# Tool implementations
from src.utils.tool_interface import ToolExecutor
from src.utils.file_system_tools import FileSystemTools
from src.utils.code_analysis_tools import CodeAnalysisTools
from src.utils.command_line_tools import CommandLineTools
from src.utils.git_operations_tools import GitOperationsTools
from src.utils.planning_tools import PlanningTools
from src.utils.network_tools import NetworkTools         # Added
from src.utils.system_tools import SystemTools           # Added
from src.utils.cybersecurity_tools import CybersecurityTools # Added

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

class CodeAgent:
    def __init__(self, project_root: str | None = None):
        self.project_root = Path(project_root or Path.cwd())
        self.conversation: List[Dict] = []
        self._current_plan: Optional[Dict] = None # Keeping it here for now as discussed for reporting.

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
            "prompts/code/default_code_agent.json" # Default path if not specified
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
            self.command_executor = CommandExecutor(str(self.project_root), SandboxLevel.LIMITED)
            self.git_manager = GitManager(str(self.project_root))
            self.code_analyzer = CodeAnalyzer(str(self.project_root))
        except Exception as e:
            self.logger.error(f"Failed to initialize core services: {e}", e)
            raise

        # ---------------- TOOL EXECUTOR & TOOL SETS
        self.tool_executor = ToolExecutor(logger=self.logger) # Pass the logger instance
        
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
            project_root=self.project_root
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

        # ---------------- OLLAMA
        self.ollama = OllamaClient(
            url=self.config.get("ollama_url", "http://localhost:11434"),
            model=self.config.get("model", "qwen3-coder-next"),
            timeout=self.config.get("timeout", 300),
            logger=self.logger
        )
        
        self.logger.info(f"🔗 Ollama: {self.config.get('ollama_url')}")
        self.logger.info(f"🧠 Model: {self.config.get('model')}")

        # ---------------- TOOLS FUNCTIONS MAP
        self.tool_functions = {
            "plan_actions": self.planning_tools.plan_actions,
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
            "select_agent_type": self.planning_tools.select_agent_type,
            # Network Tools
            "ping_host": self.network_tools.ping_host,
            "traceroute_host": self.network_tools.traceroute_host,
            "list_active_connections": self.network_tools.list_active_connections,
            "check_port_status": self.network_tools.check_port_status,
            # System Tools
            "get_system_info": self.system_tools.get_system_info,
            "list_processes": self.system_tools.list_processes,
            "install_package": self.system_tools.install_package,
            "read_log_file": self.system_tools.read_log_file,
            # Cybersecurity Tools
            "scan_ports": self.cybersecurity_tools.scan_ports,
            "check_file_hash": self.cybersecurity_tools.check_file_hash,
            "analyze_security_log": self.cybersecurity_tools.analyze_security_log,
            "recommend_security_hardening": self.cybersecurity_tools.recommend_security_hardening,
        }

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
                self.logger.api_request(len(messages), len(self.tool_executor.get_tool_definitions()))
                
                # Make API call
                response, usage = self.ollama.chat(messages, self.tool_executor.get_tool_definitions())
                
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
                            if name == "plan_actions" and result.get("ok"):
                                self._current_plan = result.get("plan_data") # Store the plan data
                            elif name == "select_agent_type" and result.get("ok") and result.get("system_prompt"):
                                self.system_prompt = result.get("system_prompt")
                        
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
        agent = CodeAgent()
        agent.chat_mode()
    except Exception as e:
        print(f"{Fore.RED}❌ Fatal error: {e}{Style.RESET_ALL}")
        logging.exception("Fatal error")