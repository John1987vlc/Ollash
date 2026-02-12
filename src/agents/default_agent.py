import json
import logging
import os
import requests
import traceback
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid

# Core Agent and Kernel
from src.agents.core_agent import CoreAgent
from src.core.kernel import AgentKernel # Import AgentKernel
from src.core.config_schemas import LLMModelsConfig, ToolSettingsConfig # For type hinting

# Utils from Core
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.file_manager import FileManager
from src.utils.core.command_executor import CommandExecutor, SandboxLevel
from src.utils.core.git_manager import GitManager
from src.utils.core.code_analyzer import CodeAnalyzer
from src.utils.core.memory_manager import MemoryManager
from src.utils.core.tool_registry import ToolRegistry
from src.utils.core.loop_detector import LoopDetector
from src.utils.core.async_tool_executor import AsyncToolExecutor # Still used for parallel execution
from src.utils.core.confirmation_manager import ConfirmationManager # New: For confirmation gates
from src.utils.core.permission_profiles import PolicyEnforcer # Used for confirmation gates policies
from src.utils.core.llm_recorder import LLMRecorder # NEW
from src.utils.core.tool_span_manager import ToolSpanManager # NEW


# Mixins
from src.agents.mixins.intent_routing_mixin import IntentRoutingMixin
from src.agents.mixins.tool_loop_mixin import ToolLoopMixin
from src.agents.mixins.context_summarizer_mixin import ContextSummarizerMixin

# Interfaces (for type hinting, if needed for clarity on injected components)
from src.interfaces.imodel_provider import IModelProvider
from src.interfaces.itool_executor import IToolExecutor

# Tool implementations (still needed for ToolRegistry)
import src.utils.domains # This import triggers the tool registration decorators
from src.utils.core.tool_interface import ToolExecutor # Concrete ToolExecutor

from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Maximum instruction length to prevent prompt injection / context flooding
MAX_INSTRUCTION_LENGTH = 10000


class DefaultAgent(CoreAgent, IntentRoutingMixin, ToolLoopMixin, ContextSummarizerMixin):
    """
    The DefaultAgent orchestrates tasks, utilizing mixins for specific functionalities
    like intent routing, tool execution loops, and context summarization.
    It inherits core functionalities from CoreAgent.
    """
    def __init__(self,
                 project_root: str | None = None,
                 auto_confirm: bool = False,
                 base_path: Path = Path.cwd(),
                 event_bridge=None,
                 kernel: Optional[AgentKernel] = None, # Inject AgentKernel
                 llm_manager: Optional[IModelProvider] = None, # Inject LLMClientManager (as IModelProvider)
                 tool_executor: Optional[IToolExecutor] = None, # Inject ToolExecutor
                 loop_detector: Optional[LoopDetector] = None, # Inject LoopDetector
                 confirmation_manager: Optional[ConfirmationManager] = None, # Inject ConfirmationManager
                 policy_enforcer: Optional[PolicyEnforcer] = None, # Inject PolicyEnforcer
                 llm_recorder: Optional[LLMRecorder] = None, # NEW
                 tool_span_manager: Optional[ToolSpanManager] = None, # NEW
                 ):

        # Initialize AgentKernel if not provided (should ideally be provided)
        # Assuming config_dir is 'config' relative to base_path
        self.kernel = kernel if kernel else AgentKernel(config_dir=base_path / "config", ollash_root_dir=Path(project_root) if project_root else None)
        
        # Initialize LLMRecorder and ToolSpanManager if not injected
        self.llm_recorder = llm_recorder if llm_recorder else LLMRecorder(logger=self.kernel.get_logger())
        self.tool_span_manager = tool_span_manager if tool_span_manager else ToolSpanManager(logger=self.kernel.get_logger())

        # Call parent constructor, passing the kernel and llm_manager
        super().__init__(kernel=self.kernel, logger_name="DefaultAgent", llm_manager=llm_manager, llm_recorder=self.llm_recorder)

        # Access config and logger from Kernel (they are set by CoreAgent's __init__)
        # No need to re-assign self.logger, self.config here as CoreAgent does it
        # However, these are still needed for direct access in DefaultAgent
        self.llm_models_config: LLMModelsConfig = self.kernel.get_llm_models_config()
        self.tool_settings_config: ToolSettingsConfig = self.kernel.get_tool_settings_config()

        self._base_path = base_path
        self.project_root = Path(project_root or self._base_path)
        self.auto_confirm = auto_confirm
        self._event_bridge = event_bridge
        
        self.max_iterations = self.tool_settings_config.max_iterations # Get from tool_settings_config

        self.logger.info(f"\n{Fore.GREEN}{'='*60}")
        self.logger.info("Default Agent Initialized")
        self.logger.info(f"{'='*60}{Style.RESET_ALL}")
        self.logger.info(f"📁 Project: {self.project_root}")

        # Core Services (some might be from CoreAgent, others instantiated here for DefaultAgent's specific needs)
        self.file_manager = FileManager(str(self.project_root))
        self.command_executor = CommandExecutor(str(self.project_root), SandboxLevel.LIMITED, logger=self.logger, use_docker_sandbox=self.tool_settings_config.use_docker_sandbox) # Use tool_settings_config
        self.git_manager = GitManager(str(self.project_root))
        self.code_analyzer = CodeAnalyzer(str(self.project_root))
        
        # --- Dependencies for Mixins & CoreAgent (injected or initialized) ---
        # self.llm_manager is from CoreAgent, now injected or created in super()
        # MemoryManager (still directly instantiated for now, could be its own service)
        self.memory_manager = MemoryManager(self.project_root, self.logger, config=self.kernel.get_full_config(), llm_recorder=self.llm_recorder) # Pass full raw config
        self.token_tracker = self.token_tracker # From CoreAgent, used by ContextSummarizerMixin
        self.event_publisher = self.event_publisher # From CoreAgent, used by mixins

        # Confirmation & Policy for ToolLoopMixin
        self.confirmation_manager = confirmation_manager if confirmation_manager else ConfirmationManager(logger=self.logger, auto_confirm=self.auto_confirm)
        self.policy_enforcer = policy_enforcer if policy_enforcer else PolicyEnforcer(
            profile_manager=self.permission_manager,
            logger=self.logger,
            tool_settings_config=self.tool_settings_config, # NEW
        )
        # Set active profile after initialization
        self.policy_enforcer.set_active_profile("developer")

        # Tool Registry & Executor
        # Tool Registry & Executor
        # Initialize ToolRegistry with all required managers and a placeholder for tool_executor
        self._tool_registry = ToolRegistry(
            logger=self.logger,
            project_root=self.project_root,
            file_manager=self.file_manager,
            command_executor=self.command_executor,
            git_manager=self.git_manager,
            code_analyzer=self.code_analyzer,
            tool_executor=None, # Temporarily set to None to avoid circular dependency
        )
        self._all_tool_instances_mapping = self._tool_registry.get_tool_mapping()
        self._agent_tool_name_mappings = self._tool_registry.get_agent_tools()

        # Initialize ToolExecutor with the fully initialized ToolRegistry and agent_instance
        self.tool_executor = tool_executor if tool_executor else ToolExecutor(
            tool_registry=self._tool_registry,
            agent_instance=self, # Pass self as the agent_instance
        )
        # Now set the tool_executor in ToolRegistry to resolve the circular dependency
        self._tool_registry.tool_executor = self.tool_executor

        self.async_tool_executor = AsyncToolExecutor(
            self._execute_single_tool,
            tool_registry=self._tool_registry, # Pass the initialized ToolRegistry
        )

        # Loop Detector (injected or initialized)
        self.loop_detector = loop_detector if loop_detector else LoopDetector(
            logger=self.logger,
            embedding_client=self.llm_manager.get_client("default"), # Use llm_manager for embedding client
            threshold=self.tool_settings_config.loop_detection_threshold, # From tool_settings_config
            similarity_threshold=self.tool_settings_config.semantic_similarity_threshold, # From tool_settings_config
            stagnation_timeout_minutes=2
        )

        # Load system prompt from file
        default_prompt_path = self.tool_settings_config.default_system_prompt_path # From tool_settings_config
        try:
            full_prompt_path = self._base_path / default_prompt_path
            with open(full_prompt_path, "r", encoding="utf-8") as f:
                prompt_data = json.load(f)
            self.system_prompt = prompt_data.get("prompt", "")
            if not self.system_prompt:
                self.logger.warning(f"System prompt 'prompt' field empty in {full_prompt_path}. Using default fallback.")
                self.system_prompt = self._get_fallback_system_prompt()
        except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
            self.logger.error(f"Error loading system prompt from {full_prompt_path}: {e}. Using default fallback.")
            self.system_prompt = self._get_fallback_system_prompt()

        self.conversation: List[Dict] = self.memory_manager.get_conversation_history()
        self.domain_context_memory: Dict[str, str] = self.memory_manager.get_domain_context_memory()
        self.checkpoint_counter: int = 0
        self.active_agent_type = "orchestrator"
        self.active_tool_names = self._agent_tool_name_mappings[self.active_agent_type]

        self.logger.info(f"Ollama URL: {self.llm_models_config.ollama_url}") # Access from llm_models_config
        self.logger.info(f"Default Model: {self.llm_models_config.default_model} (Initial)")


    def _get_fallback_system_prompt(self) -> str:
        return """You are a disciplined coding agent. 
RULES:
1. ALWAYS start with plan_actions to show what you'll do
2. ASK for confirmation before: write_file, delete_file, git_commit, git_push
3. Use read_files (plural) to read multiple files at once efficiently
4. Use summarize_files (plural) to summarize multiple files at once
5. Use analyze_project to get a comprehensive overview of the project
6. Be clear and concise in your explanations"""




    def _create_checkpoint(self):
        """Creates a git checkpoint of the current project state."""
        self.logger.info("Creating a new checkpoint...")
        try:
            self.git_manager.stage_all()
            commit_message = f"Checkpoint {self.checkpoint_counter}"
            self.git_manager.commit(commit_message)
            self.logger.info(f"Successfully created checkpoint: {commit_message}")
            self.checkpoint_counter += 1
        except Exception as e:
            self.logger.error(f"Failed to create checkpoint: {e}")
            
    async def _preprocess_instruction(self, instruction: str) -> tuple[str, str]:
        """
        Detects the language, translates to English, and refines the instruction.
        Returns (refined_english_instruction, original_language).
        """
        self.logger.info("Refining user instruction...")
        
        refine_prompt = [
            {"role": "system", "content": "You are a prompt engineer. Translate the user's request to English if it's in another language. Then, expand and clarify the request to be more effective for a coding agent. Return ONLY the refined English text."},
            {"role": "user", "content": f"Refine this: {instruction}"}
        ]
        
        try:
            preprocess_client = self.llm_manager.get_client("orchestration") # Use llm_manager
            response, _ = await preprocess_client.achat(refine_prompt, tools=[])
            refined_text = response.get("message", {}).get("content", instruction)
            
            original_lang = "es" if any(ord(c) > 127 for c in instruction) else "en" # Very basic
            
            return refined_text, original_lang
        except Exception as e:
            self.logger.error(f"Error in pre-processing: {e}")
            return instruction, "en" # Fallback to original instruction and English

    async def _translate_to_user_language(self, text: str, target_lang: str) -> str:
        """Translates the final response to the user's original language."""
        if target_lang == "en":
            return text
            
        translation_prompt = [
            {"role": "system", "content": f"Translate the following technical response to {target_lang}. Maintain code blocks and technical terms as they are."},
            {"role": "user", "content": text}
        ]
        
        try:
            translate_client = self.llm_manager.get_client("orchestration") # Use llm_manager
            response, _ = await translate_client.achat(translation_prompt, tools=[])
            return response.get("message", {}).get("content", text)
        except Exception as e:
            self.logger.error(f"Error in final translation: {e}")
            return text

    @property
    def tool_functions(self):
        """
        Returns the OpenAPI-like definitions for the currently active tool functions.
        """
        return self.tool_executor.get_tool_definitions(self.active_tool_names)

    @property
    def preference_manager(self):
        """
        Dynamically provides the currently active preference manager for the agent.
        """
        return self.memory_manager.get_preference_manager()

    async def _execute_single_tool(self, tool_call: Dict) -> Any:
        """
        Wrapper method to execute a single tool call asynchronously.
        Expected by AsyncToolExecutor.
        """
        tool_name = tool_call["function"]["name"]
        tool_args = tool_call["function"]["arguments"]
        return await self.tool_executor.execute_tool(tool_name, **tool_args)

    async def chat(self, instruction: str, auto_confirm: bool = False) -> str:
        correlation_id: Optional[str] = None
        try:
            # Start interaction context with a correlation ID
            correlation_id = self.kernel.start_interaction_context()

            # 0. Input validation
            if not instruction or not instruction.strip():
                return "Please provide an instruction."
            if len(instruction) > MAX_INSTRUCTION_LENGTH:
                return f"Instruction too long ({len(instruction)} chars). Maximum is {MAX_INSTRUCTION_LENGTH}."

            self.loop_detector.reset()

            # 1. Pre-processing Phase (Input)
            english_instruction, original_lang = await self._preprocess_instruction(instruction)
            self.logger.info(f"Original Instruction: {instruction}")
            self.logger.info(f"Refined Instruction (EN): {english_instruction}")

            if not self.conversation or self.conversation[-1]["role"] != "user":
                self.conversation.append({"role": "user", "content": english_instruction})
            
            # --- Intent Routing Mixin Usage ---
            intent_for_this_turn = await self._classify_intent(english_instruction) # Use mixin method
            selected_model_client = self._select_model_for_intent(intent_for_this_turn) # Use mixin method
            
            # Override default client for this turn, or use it for routing later
            # For now, let's assume the mixin returns the client directly, which DefaultAgent then uses.
            self.logger.info(f"🧠 Current turn model selected based on intent '{intent_for_this_turn}': {selected_model_client.model}")

            messages = [
                {"role": "system", "content": self.system_prompt},
                *self.conversation
            ]

            iterations = 0
            last_error_context = None

            while iterations < self.max_iterations:
                iterations += 1
                self.logger.info(f"\n{Fore.MAGENTA}━━━ Iteration {iterations}/{self.max_iterations} ━━━{Style.RESET_ALL}")
                if self._event_bridge:
                    self._event_bridge.push_event("iteration", {"current": iterations, "max": self.max_iterations})

                # --- Context Summarizer Mixin Usage ---
                messages = await self._manage_context_window(messages) # Use mixin method
                self.conversation = [msg for msg in messages if msg["role"] != "system"] # Update conversation based on summarized messages
                self.system_prompt = messages[0]["content"] if messages and messages[0]["role"] == "system" else self.system_prompt


                try:
                    # self.logger.api_request(len(messages), len(self.tool_functions)) # REMOVED, LLMRecorder handles
                    
                    # Directly use the selected_model_client (IModelProvider client)
                    response, _ = await selected_model_client.achat(
                        messages=messages,
                        tools=self.tool_executor.get_tool_definitions(self.active_tool_names),
                    )
                    
                    # Track tokens from the chosen response
                    chosen_usage = response.get("usage", {})
                    self.token_tracker.add_usage(
                        chosen_usage.get("prompt_tokens", 0),
                        chosen_usage.get("completion_tokens", 0)
                    )
                    
                    self.token_tracker.display_current()
                    
                    msg = response["message"]

                    if "tool_calls" not in msg:
                        # self.logger.api_response(False) # REMOVED, LLMRecorder handles
                        final_response_en = msg.get("content", "") 
                        
                        if last_error_context:
                            # Assuming memory_manager now exists on self (from CoreAgent or injected)
                            self.memory_manager.add_to_reasoning_cache(last_error_context["error"], final_response_en)
                            last_error_context = None

                        final_response_translated = await self._translate_to_user_language(final_response_en, original_lang)
                        self.conversation.append({"role": "assistant", "content": final_response_en})
                        self.logger.info(f"{Fore.GREEN}✅ Final answer generated{Style.RESET_ALL}")
                        return final_response_translated 

                    tool_calls = msg["tool_calls"]
                    # self.logger.api_response(True, len(tool_calls)) # REMOVED, LLMRecorder handles
                    self.conversation.append(msg)
                    
                    # --- Tool Loop Mixin Usage ---
                    tool_outputs = await self._execute_tool_loop(tool_calls, english_instruction) # Use mixin method
                    
                    for result in tool_outputs:
                        self.conversation.append({
                            "role": "tool",
                            "content": json.dumps(result)
                        })
                        
                        if isinstance(result, dict) and not result.get("ok"):
                            error_msg = result.get("error", "Unknown tool error")
                            tool_name = result.get("tool_name", "unknown") # ToolLoopMixin now includes tool_name in output
                            
                            if self._event_bridge:
                                self._event_bridge.push_event("error", {"message": error_msg, "tool": tool_name})
                            
                            original_tool_call = next((tc for tc in tool_calls if tc.get("id") == result.get("tool_call_id")), {})
                            last_error_context = {"error": error_msg, "tool_call": original_tool_call}
                            
                            # --- Error Handling (still in DefaultAgent, could be a mixin) ---
                            # This part of error handling (retrying with smaller model, etc.)
                            # could also be abstracted into a mixin if it becomes more complex.
                            # For now, it remains in DefaultAgent.
                            self.logger.info("Handling tool error with layered orchestration...")

                            cached_solution = self.memory_manager.search_reasoning_cache(error_msg)
                            if cached_solution:
                                self.logger.info("Found a similar error in the reasoning cache. Applying cached solution.")
                                try:
                                    tool_calls_from_cache = json.loads(cached_solution)
                                    self.conversation.append({
                                        "role": "assistant",
                                        "content": "I've seen a similar error before. Trying a known solution.",
                                        "tool_calls": tool_calls_from_cache
                                    })
                                    continue # Continue the loop to execute cached solution
                                except json.JSONDecodeError as e:
                                    self.logger.error(f"Failed to decode cached solution: {e}. Solution: {cached_solution}")

                            self.logger.info(f"Escalating to small model for error analysis.")
                            correction_client = self.llm_manager.get_client("self_correction")
                            if correction_client:
                                correction_prompt = [
                                    {"role": "system", "content": "You are a self-correction AI. Analyze the following error and provide a single tool call to fix it. Respond in JSON format with 'tool_calls' and a 'confidence' score (0.0 to 1.0)."},
                                    {"role": "user", "content": f"The tool call {json.dumps(original_tool_call)} failed with this error:\n{error_msg}"}
                                ]
                                try:
                                    response, _ = await correction_client.achat(correction_prompt, tools=[])
                                    response_content = response.get("message", {}).get("content", "")
                                    solution_data = json.loads(response_content)
                                    confidence = solution_data.get("confidence", 0.0)
                                    tool_calls_from_correction = solution_data.get("tool_calls")

                                    if confidence > 0.8 and tool_calls_from_correction:
                                        self.logger.info(f"Small model provided a high-confidence solution (confidence: {confidence}). Applying fix.")
                                        self.conversation.append({
                                            "role": "assistant",
                                            "content": "I have a potential fix for the error.",
                                            "tool_calls": tool_calls_from_correction
                                        })
                                        continue # Continue the loop to execute the corrected solution
                                except (json.JSONDecodeError, AttributeError, Exception) as err:
                                    self.logger.warning(f"Small model did not provide a valid JSON response or error during correction: {err}")
                            else:
                                self.logger.warning("Self-correction LLM client not available.")

                            self.logger.info(f"Escalating to large model for deeper error analysis.")
                            # If self-correction fails, then we allow the original message
                            # to be re-processed or indicate human intervention.
                            if auto_confirm:
                                return f"❌ Critical error during tool execution in auto-mode: {error_msg}. Human intervention required."
                            # If not auto_confirm, the agent will go through another loop,
                            # potentially trying to fix it or ask the user.


                except requests.exceptions.HTTPError as e:
                    self.logger.error("HTTP Error from Ollama API", e)
                    error_str = str(e)
                    
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
                    # This line uses self.ollama, which is not defined.
                    # It should use self.llm_manager.ollama_url
                    ollama_url = self.llm_models_config.ollama_url # Use llm_models_config
                    return ("❌ Connection Error: Cannot connect to Ollama.\n\n"
                           "Make sure Ollama is running: 'ollama serve'\n"
                           f"Configured URL: {ollama_url}")
                
                except Exception as e:
                    self.logger.error(f"Unexpected error in iteration {iterations}", e)
                    return f"❌ Unexpected error: {str(e)}\n\nCheck agent.log for details."

            self.logger.warning("Max iterations reached")
            return f"⚠️  Reached maximum iterations ({self.max_iterations})"
        finally:
            if correlation_id:
                self.kernel.end_interaction_context(correlation_id)

    def chat_mode(self):
        """Interactive chat mode with enhanced UX"""
        print(f"\n{Fore.GREEN}{'='*60}")
        print("🤖 DEFAULT AGENT - Enhanced Interactive Mode")
        print(f"{'='*60}{Style.RESET_ALL}")
        print(f"📁 Project: {Fore.CYAN}{self.project_root}{Style.RESET_ALL}")
        print(f"📝 Logs: {Fore.CYAN}{self.tool_settings_config.log_file}{Style.RESET_ALL}") # Use tool_settings_config
        print(f"💡 Commands: {Fore.YELLOW}exit, quit, help{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")

        while True:
            try:
                q = input(f"\n{Fore.GREEN}👤 You: {Style.RESET_ALL}").strip()
                
                if q.lower() in {"exit", "quit", "salir"}:
                    self.memory_manager.update_conversation_history(self.conversation)
                    self.memory_manager.update_domain_context_memory(self.domain_context_memory)
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
                response = asyncio.run(self.chat(q, auto_confirm=self.auto_confirm)) # Pass auto_confirm to chat
                print(f"\n{response}\n")
                
            except KeyboardInterrupt:
                self.memory_manager.update_conversation_history(self.conversation)
                self.memory_manager.update_domain_context_memory(self.domain_context_memory)
                print(self.token_tracker.get_session_summary())
                self.logger.info("Session interrupted by user")
                print(f"\n\n{Fore.GREEN}👋 Goodbye!{Style.RESET_ALL}\n")
                break
            except Exception as e:
                self.logger.error("Error in chat mode", e)
                print(f"\n{Fore.RED}❌ Error: {e}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Check agent.log for details{Style.RESET_ALL}")


    def run(self, *args, **kwargs):
        """
        Placeholder run method to satisfy the abstract method requirement from CoreAgent.
        DefaultAgent uses chat_mode for interaction.
        """
        raise NotImplementedError("DefaultAgent is interactive via chat_mode, not meant to be called with run directly.")

