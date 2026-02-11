import json
import logging
import os
import requests
import traceback
import asyncio
from pathlib import Path
from typing import Dict, List, Optional

from src.utils.core.agent_logger import AgentLogger
from src.utils.core.file_manager import FileManager
from src.utils.core.command_executor import CommandExecutor, SandboxLevel
from src.utils.core.git_manager import GitManager
from src.utils.core.code_analyzer import CodeAnalyzer
from src.utils.core.ollama_client import OllamaClient
from src.utils.core.memory_manager import MemoryManager
from src.utils.core.tool_registry import ToolRegistry
from src.utils.core.loop_detector import LoopDetector
from src.agents.core_agent import CoreAgent # Import CoreAgent
from src.utils.core.model_router import ModelRouter
from src.utils.core.async_tool_executor import AsyncToolExecutor
from src.utils.core.model_health_monitor import ModelHealthMonitor
import src.utils.domains # This import triggers the tool registration decorators


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
from src.utils.domains.orchestration.orchestration_tools import OrchestrationTools
from src.utils.domains.code.advanced_code_tools import AdvancedCodeTools
from src.utils.domains.system.advanced_system_tools import AdvancedSystemTools
from src.utils.domains.network.advanced_network_tools import AdvancedNetworkTools
from src.utils.domains.cybersecurity.advanced_cybersecurity_tools import AdvancedCybersecurityTools
from src.utils.domains.bonus.bonus_tools import BonusTools
from colorama import init, Fore, Style

# Initialize colorama (needed for print statements in some tool methods)
init(autoreset=True)

# Maximum instruction length to prevent prompt injection / context flooding
MAX_INSTRUCTION_LENGTH = 10000


# ======================================================
# CODE AGENT (ENHANCED & FIXED)
# ======================================================

class DefaultAgent(CoreAgent): # Inherit from CoreAgent
    def __init__(self, project_root: str | None = None, auto_confirm: bool = False, base_path: Path = Path.cwd(), event_bridge=None):
        super().__init__(config_path=str(base_path / "config" / "settings.json"), ollash_root_dir=Path(project_root) if project_root else None, logger_name="DefaultAgent")
        
        self._base_path = base_path # The base path where the agent's own config and prompts are located
        self.project_root = Path(project_root or self._base_path) # The project root for the current task
        self.auto_confirm = auto_confirm # Store the auto_confirm flag
        self._event_bridge = event_bridge  # Optional ChatEventBridge for web UI streaming
        
        # ---------------- LOGGING
        self.logger.info(f"\n{Fore.GREEN}{'='*60}")
        self.logger.info("Code Agent Initialized")
        self.logger.info(f"{'='*60}{Style.RESET_ALL}")
        self.logger.info(f"📁 Project: {self.project_root}")

        # ---------------- CONFIG LOAD (already handled by CoreAgent)
        self.max_iterations = self.config.get("max_iterations", 30)

        # ---------------- MEMORY MANAGEMENT
        # MemoryManager needs a specific logger, can't directly use self.logger (which might be for CoreAgent)
        # Re-initialize memory_manager here with the correct project_root and logger instance.
        self.memory_manager = MemoryManager(self.project_root, self.logger, config=self.config)
        self.conversation: List[Dict] = self.memory_manager.get_conversation_history()
        self.domain_context_memory: Dict[str, str] = self.memory_manager.get_domain_context_memory()

        # Checkpoint counter
        self.checkpoint_counter: int = 0

        # Hybrid Brain Model Configuration (centralized in settings.json "models" section)
        # These are already in CoreAgent.LLM_ROLES, just setting local vars for convenience.
        self.reasoning_model = self.config.get("models", {}).get("reasoning", self.config.get("reasoning_model", "gpt-oss:20b"))
        self.coding_model = self.config.get("models", {}).get("coding", self.config.get("coding_model", "qwen3-coder:30b"))
        self.self_correction_model = self.config.get("models", {}).get("self_correction", self.config.get("self_correction_model", "ministral-3:8b"))
        self.orchestration_model = self.config.get("models", {}).get("orchestration", self.config.get("orchestration_model", "ministral-3:8b"))
        self.summarization_model = self.config.get("models", {}).get("summarization", self.config.get("summarization_model", "gpt-oss:20b"))
        self.current_llm_model = self.config.get("models", {}).get("default", self.config.get("model", "qwen3-coder-next"))

        # Load system prompt from file (relative to _base_path)
        default_prompt_path = self.config.get(
            "default_system_prompt_path",
            "prompts/code/default_agent.json" # Default path if not specified
        )
        try:
            full_prompt_path = self._base_path / default_prompt_path
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


        # ---------------- TOKEN TRACKING (already handled by CoreAgent)

        # ---------------- CORE SERVICES
        # These services are now part of CoreAgent, just referencing them from self.
        try:
            self.file_manager = FileManager(str(self.project_root)) # FileManager still needs to be instantiated here as it's not in CoreAgent
            # CommandExecutor is already in CoreAgent, but DefaultAgent has a more specific SandboxLevel.
            # Re-initialize or update the sandbox level. For now, re-initialize.
            self.command_executor = CommandExecutor(str(self.project_root), SandboxLevel.LIMITED, logger=self.logger, use_docker_sandbox=self.config.get("use_docker_sandbox", False))
            self.git_manager = GitManager(str(self.project_root))
            self.code_analyzer = CodeAnalyzer(str(self.project_root))
        except Exception as e:
            self.logger.error(f"Failed to initialize core services: {e}", e)
            raise

        self.model_health_monitor = ModelHealthMonitor(self.logger, self.config)

        # ---------------- TOOL REGISTRY (extracted from inline dicts)
        self._tool_registry = ToolRegistry()
        self._all_tool_instances_mapping = self._tool_registry.get_tool_mapping()
        self._agent_tool_name_mappings = self._tool_registry.get_agent_tools()

        # ---------------- TOOL EXECUTOR & TOOL SETS
        self.tool_executor = ToolExecutor(logger=self.logger, config=self.config, auto_confirm=self.auto_confirm, tool_registry=self._tool_registry) # Pass the logger, config, auto_confirm, and tool_registry instance
        self.async_tool_executor = AsyncToolExecutor(self._execute_single_tool)
        
        # Toolset configurations for lazy loading
        self._toolset_configs = {
            "file_system_tools": {
                "class": FileSystemTools,
                "init_args": {"project_root": self.project_root, "file_manager": self.file_manager, "logger": self.logger, "tool_executor": self.tool_executor}
            },
            "code_analysis_tools": {
                "class": CodeAnalysisTools,
                "init_args": {"project_root": self.project_root, "code_analyzer": self.code_analyzer, "command_executor": self.command_executor, "logger": self.logger}
            },
            "command_line_tools": {
                "class": CommandLineTools,
                "init_args": {"command_executor": self.command_executor, "logger": self.logger}
            },
            "git_operations_tools": {
                "class": GitOperationsTools,
                "init_args": {"git_manager": self.git_manager, "logger": self.logger, "tool_executor": self.tool_executor}
            },
            "planning_tools": {
                "class": PlanningTools,
                "init_args": {"logger": self.logger, "project_root": self.project_root, "agent_instance": self}
            },
            "network_tools": {
                "class": NetworkTools,
                "init_args": {"command_executor": self.command_executor, "logger": self.logger}
            },
            "system_tools": {
                "class": SystemTools,
                "init_args": {"command_executor": self.command_executor, "file_manager": self.file_manager, "logger": self.logger, "agent_instance": self}
            },
            "cybersecurity_tools": {
                "class": CybersecurityTools,
                "init_args": {"command_executor": self.command_executor, "file_manager": self.file_manager, "logger": self.logger}
            },
            "orchestration_tools": {
                "class": OrchestrationTools,
                "init_args": {"logger": self.logger}
            },
            "advanced_code_tools": {
                "class": AdvancedCodeTools,
                "init_args": {"project_root": self.project_root, "code_analyzer": self.code_analyzer, "command_executor": self.command_executor, "logger": self.logger}
            },
            "advanced_system_tools": {
                "class": AdvancedSystemTools,
                "init_args": {"command_executor": self.command_executor, "logger": self.logger}
            },
            "advanced_network_tools": {
                "class": AdvancedNetworkTools,
                "init_args": {"command_executor": self.command_executor, "logger": self.logger}
            },
            "advanced_cybersecurity_tools": {
                "class": AdvancedCybersecurityTools,
                "init_args": {"command_executor": self.command_executor, "file_manager": self.file_manager, "logger": self.logger}
            },
            "bonus_tools": {
                "class": BonusTools,
                "init_args": {"logger": self.logger}
            }
        }
        self._loaded_toolsets = {} # Cache for loaded toolset instances

        # ---------------- OLLAMA (already handled by CoreAgent)
        # self.ollama is initialized in CoreAgent.__init__
        self.logger.info(f"Ollama: {self.llm_clients['default'].url}")
        self.logger.info(f"Model: {self.current_llm_model} (Initial)")

        # Initialize ModelRouter
        self.model_router = ModelRouter(
            llm_clients=self.llm_clients, # Pass the llm_clients dictionary from CoreAgent
            logger=self.logger,
            response_parser=self.response_parser,
            event_publisher=self.event_publisher,
            senior_reviewer_model_name="senior_reviewer", # Using the senior_reviewer role for selection
            config=self.config
        )

        self.active_agent_type = "orchestrator"
        self.active_tool_names = self._agent_tool_name_mappings[self.active_agent_type]

        # ---------------- LOOP DETECTOR
        self.loop_detector = LoopDetector(
            logger=self.logger,
            embedding_client=self.llm_clients["default"],
            threshold=self.config.get("loop_detection_threshold", 3),
            similarity_threshold=self.config.get("semantic_similarity_threshold", 0.95),
            stagnation_timeout_minutes=2
        )

    async def _execute_single_tool(self, tool_call: Dict) -> Dict:
        name = tool_call["function"]["name"]
        args = tool_call["function"]["arguments"]

        print(f"\n{Fore.CYAN}┌─ Tool Call ─────────────────{Style.RESET_ALL}")
        self.logger.tool_call(name, args)
        if self._event_bridge:
            self._event_bridge.push_event("tool_call", {"name": name, "args": args})

        try:
            if name not in self.tool_functions:
                error_msg = f"Tool '{name}' not implemented"
                self.logger.error(error_msg)
                return {
                    "ok": False,
                    "error": "tool_not_found",
                    "message": error_msg,
                    "available_tools": list(self.tool_functions.keys())
                }

            tool_func = self._get_tool_from_toolset(name)
            result = tool_func(**args)

            state_modifying_tools = ["write_file", "delete_file", "run_command", "install_package"]
            if name in state_modifying_tools and result.get("ok", True):
                self._create_checkpoint()

            if result.get("ok", True):
                self.loop_detector.record_action(name, args, result)
                self.loop_detector.update_progress(name, result)

                if self.loop_detector.detect_loop():
                    loop_message = f"Detected a loop! The agent is repeatedly calling '{name}' with similar arguments/results. Human intervention required."
                    self.logger.error(loop_message)
                    return self._get_tool_from_toolset("require_human_gate")(
                        action_description=loop_message,
                        reason="Loop detected, agent is stuck in a repetitive action sequence."
                    )

            if name == "select_agent_type" and result.get("ok"):
                new_agent_type = result.get("new_agent_type")
                new_system_prompt = result.get("system_prompt")
                if new_agent_type and new_system_prompt:
                    self.active_agent_type = new_agent_type
                    self.system_prompt = new_system_prompt
                    self.active_tool_names = self._agent_tool_name_mappings[self.active_agent_type]
                    self.logger.info(f"{Fore.GREEN}Switched agent type to '{self.active_agent_type}'. System prompt and available tools updated.{Style.RESET_ALL}")

            success = result.get("ok", True) if isinstance(result, dict) else True
            self.logger.tool_result(name, result, success)
            if self._event_bridge:
                result_str = json.dumps(result) if isinstance(result, dict) else str(result)
                if len(result_str) > 2000:
                    result_str = result_str[:2000] + "... [truncated]"
                self._event_bridge.push_event("tool_result", {"name": name, "success": success, "result": result_str})

            return result

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            self.logger.error(error_msg, e)
            if self._event_bridge:
                self._event_bridge.push_event("error", {"message": error_msg, "tool": name})

            # In async context, we return the error instead of handling it here
            return {
                "ok": False,
                "error": error_msg,
                "traceback": traceback.format_exc()
            }
        finally:
            print(f"{Fore.CYAN}└────────────────────────────────────────{Style.RESET_ALL}")

    def _calculate_message_tokens(self, messages: List[Dict]) -> int:
        """Estimates the total number of tokens in a list of messages. Delegates to MemoryManager."""
        return self.memory_manager.estimate_tokens(messages) # Corrected to use self.memory_manager

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
            # Use the orchestration model for pre-processing
            preprocess_client = self.llm_clients["orchestration"]
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
            translate_client = self.llm_clients["orchestration"]
            response, _ = await translate_client.achat(translation_prompt, tools=[])
            return response.get("message", {}).get("content", text)
        except Exception as e:
            self.logger.error(f"Error in final translation: {e}")
            return text
    
    def _get_model_for_intent(self, intent: str) -> str:
        """
        Selects the appropriate model based on the classified intent.
        """
        if intent == "Reasoning/Architecture":
            return self.reasoning_model
        elif intent == "Code Generation":
            return self.coding_model
        elif intent == "Self-Correction":
            return self.self_correction_model
        else:
            return self.current_llm_model # Default model for general or unclassified tasks

    async def _classify_intent(self, instruction: str) -> str:
        """
        Uses an LLM call to classify the intent of the instruction.
        """
        classification_prompt = [
            {"role": "system", "content": (
                "You are an intelligent orchestrator. Classify the following user instruction "
                "into one of these categories: 'Reasoning/Architecture', 'Code Generation', "
                "'Self-Correction', or 'General'. Respond with only the category name."
            )},
            {"role": "user", "content": instruction}
        ]
        
        try:
            classification_ollama_client = self.llm_clients["orchestration"]
            response_data, _ = await classification_ollama_client.achat(classification_prompt, tools=[])
            intent = response_data.get("message", {}).get("content", "General").strip()
            self.logger.info(f"Classified intent: {intent}")
            return intent
        except Exception as e:
            self.logger.error(f"Failed to classify intent: {e}. Defaulting to 'General'.")
            return "General"
            
    def _get_tool_from_toolset(self, tool_name: str):
        """
        Lazily loads and returns a specific tool function from its toolset.
        """
        if tool_name not in self._all_tool_instances_mapping:
            raise ValueError(f"Tool '{tool_name}' not found in any toolset mapping.")

        toolset_identifier, method_name_in_toolset = self._all_tool_instances_mapping[tool_name]

        if toolset_identifier not in self._loaded_toolsets:
            self.logger.debug(f"Lazily loading toolset: {toolset_identifier}")
            toolset_config = self._toolset_configs.get(toolset_identifier)
            if not toolset_config:
                raise ValueError(f"Toolset configuration for '{toolset_identifier}' not found.")
            
            toolset_class = toolset_config["class"]
            init_args = toolset_config["init_args"].copy() # Use a copy to avoid modifying original

            if toolset_identifier == "planning_tools":
                init_args["agent_instance"] = self

            if toolset_identifier == "orchestration_tools" and not hasattr(self, 'orchestration_tools'):
                self.orchestration_tools = toolset_class(**init_args)
                self._loaded_toolsets[toolset_identifier] = self.orchestration_tools
            elif toolset_identifier == "orchestration_tools":
                 self._loaded_toolsets[toolset_identifier] = getattr(self, 'orchestration_tools', toolset_class(**init_args))
            else:
                self._loaded_toolsets[toolset_identifier] = toolset_class(**init_args)
        
        toolset_instance = self._loaded_toolsets[toolset_identifier]
        tool_func = getattr(toolset_instance, method_name_in_toolset, None)

        if not tool_func:
            raise AttributeError(f"Tool '{method_name_in_toolset}' not found in toolset '{toolset_identifier}'.")
            
        return tool_func

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
            
    async def _handle_tool_error(self, error_msg: str, original_tool_call: Dict):
        """
        Handles a tool execution error with a layered orchestration approach.
        """
        self.logger.info("Handling tool error with layered orchestration...")

        cached_solution = self.memory_manager.search_reasoning_cache(error_msg)
        if cached_solution:
            self.logger.info("Found a similar error in the reasoning cache. Applying cached solution.")
            try:
                tool_calls = json.loads(cached_solution)
                self.conversation.append({
                    "role": "assistant",
                    "content": "I've seen a similar error before. Trying a known solution.",
                    "tool_calls": tool_calls
                })
                return True # Indicates that a solution has been queued
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to decode cached solution: {e}. Solution: {cached_solution}")

        self.logger.info(f"Escalating to small model ({self.self_correction_model}) for error analysis.")
        correction_prompt = [
            {"role": "system", "content": "You are a self-correction AI. Analyze the following error and provide a single tool call to fix it. Respond in JSON format with 'tool_calls' and a 'confidence' score (0.0 to 1.0)."},
            {"role": "user", "content": f"The tool call {json.dumps(original_tool_call)} failed with this error:\n{error_msg}"}
        ]
        
        try:
            correction_client = self.llm_clients["self_correction"]
            response, _ = await correction_client.achat(correction_prompt, tools=[])
            
            response_content = response.get("message", {}).get("content", "")
            
            try:
                solution_data = json.loads(response_content)
                confidence = solution_data.get("confidence", 0.0)
                tool_calls = solution_data.get("tool_calls")

                if confidence > 0.8 and tool_calls:
                    self.logger.info(f"Small model provided a high-confidence solution (confidence: {confidence}). Applying fix.")
                    self.conversation.append({
                        "role": "assistant",
                        "content": "I have a potential fix for the error.",
                        "tool_calls": tool_calls
                    })
                    return True
            except (json.JSONDecodeError, AttributeError):
                self.logger.warning("Small model did not provide a valid JSON response for error correction.")

        except Exception as e:
            self.logger.error(f"Error during small model self-correction: {e}")

        self.logger.info(f"Escalating to large model ({self.reasoning_model}) for deeper error analysis.")
        self.conversation.append({
            "role": "tool",
            "content": json.dumps({
                "ok": False,
                "error": error_msg,
                "traceback": traceback.format_exc()
            })
        })
        return False # Indicates that no immediate solution was found, main loop should continue

    def _summarize_context_for_domain(self, domain_type: str) -> str:
        """
        Summarizes the conversation history related to a specific domain type
        by filtering for messages that reference tools from that domain.
        """
        self.logger.info(f"Summarizing context for domain: {domain_type}")

        domain_tools = set(self._agent_tool_name_mappings.get(domain_type, []))
        if not domain_tools:
            return f"No tools registered for domain '{domain_type}'."

        relevant_snippets = []
        for msg in self.conversation:
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            for tc in tool_calls:
                tool_name = tc.get("function", {}).get("name", "")
                if tool_name in domain_tools:
                    relevant_snippets.append(f"[tool_call] {tool_name}: {json.dumps(tc['function'].get('arguments', {}))[:200]}")

            if msg.get("role") == "tool" and content:
                relevant_snippets.append(f"[tool_result] {content[:300]}")

        if not relevant_snippets:
            return f"No prior activity found for domain '{domain_type}'."

        combined = "\n".join(relevant_snippets)
        if len(combined) > 2000:
            combined = combined[:2000] + "\n... (truncated)"

        return f"Domain '{domain_type}' activity summary:\n{combined}"

    @property
    def tool_functions(self):
        """
        Dynamically provides the currently active tool functions for the agent.
        Tools are lazily loaded.
        """
        active_tool_funcs = {}
        for tool_name in self.active_tool_names:
            try:
                active_tool_funcs[tool_name] = self._get_tool_from_toolset(tool_name)
            except (ValueError, AttributeError) as e:
                self.logger.error(f"Failed to load active tool '{tool_name}': {e}")
        return active_tool_funcs

    @property
    def preference_manager(self):
        """
        Dynamically provides the currently active preference manager for the agent.
        """
        return self.memory_manager.get_preference_manager()

    async def chat(self, instruction: str, auto_confirm: bool = False) -> str:
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
        
        intent_for_this_turn = await self._classify_intent(english_instruction)
        selected_model_for_this_turn = self._get_model_for_intent(intent_for_this_turn)
        
        self.llm_clients["default"].model = selected_model_for_this_turn
        self.logger.info(f"🧠 Current turn model selected based on intent '{intent_for_this_turn}': {selected_model_for_this_turn}")

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

            if self.memory_manager.needs_summarization(self.conversation, self.system_prompt):
                self.logger.info("Context token limit approaching. Delegating summarization to MemoryManager.")
                self.conversation = self.memory_manager.summarize_and_clean(self.conversation)
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    *self.conversation
                ]

            try:
                self.logger.api_request(len(messages), len(self.tool_functions)) 
                
                # Determine candidate model roles based on intent
                candidate_model_roles: List[str] = []
                if intent_for_this_turn == "Code Generation":
                    candidate_model_roles = ["coder", "prototyper"]
                elif intent_for_this_turn == "Reasoning/Architecture":
                    candidate_model_roles = ["reasoning", "planner"]
                elif intent_for_this_turn == "Self-Correction":
                    candidate_model_roles = ["self_correction", "coder"]
                else: # General or unclassified intent
                    candidate_model_roles = ["default", "generalist"]
                
                # Ensure the selected model for this turn is always a candidate
                # This ensures direct routing if only one is selected by _get_model_for_intent
                if selected_model_for_this_turn not in [self.llm_clients[r].model for r in candidate_model_roles]:
                    # Find the role for selected_model_for_this_turn and add it if not already there
                    for role, model_key, default_model, _ in CoreAgent.LLM_ROLES:
                        if self.llm_clients[role].model == selected_model_for_this_turn:
                            if role not in candidate_model_roles:
                                candidate_model_roles.append(role)
                            break
                            
                # Use the model router to get the response
                response, all_candidate_responses = await self.model_router.aroute_and_aggregate(
                    messages=messages,
                    candidate_model_roles=candidate_model_roles,
                    tool_definitions=self.tool_executor.get_tool_definitions(self.active_tool_names),
                    user_prompt_for_reviewer=english_instruction, # Original user instruction
                    task_description=f"User wants to {intent_for_this_turn} for the project."
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
                    self.logger.api_response(False)
                    final_response_en = msg.get("content", "") 
                    
                    if last_error_context:
                        self.memory_manager.add_to_reasoning_cache(last_error_context["error"], final_response_en)
                        last_error_context = None

                    final_response_translated = await self._translate_to_user_language(final_response_en, original_lang)
                    self.conversation.append({"role": "assistant", "content": final_response_en})
                    self.logger.info(f"{Fore.GREEN}✅ Final answer generated{Style.RESET_ALL}")
                    return final_response_translated 

                tool_calls = msg["tool_calls"]
                self.logger.api_response(True, len(tool_calls))
                self.conversation.append(msg)
                
                results = await self.async_tool_executor.execute_in_parallel(tool_calls)

                for result in results:
                    self.conversation.append({
                        "role": "tool",
                        "content": json.dumps(result)
                    })
                    
                    if isinstance(result, dict) and not result.get("ok"):
                        error_msg = result.get("error", "Unknown tool error")
                        tool_name = "unknown" # This needs to be improved
                        
                        if self._event_bridge:
                            self._event_bridge.push_event("error", {"message": error_msg, "tool": tool_name})
                        
                        original_tool_call = {} # This needs to be improved
                        last_error_context = {"error": error_msg, "tool_call": original_tool_call}
                        
                        if await self._handle_tool_error(error_msg, original_tool_call):
                            continue # Try to recover
                        
                        if auto_confirm:
                            return f"❌ Critical error during tool execution in auto-mode: {error_msg}. Human intervention required."


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
                return ("❌ Connection Error: Cannot connect to Ollama.\n\n"
                       "Make sure Ollama is running: 'ollama serve'\n"
                       f"Configured URL: {self.ollama.base_url}")
            
            except Exception as e:
                self.logger.error(f"Unexpected error in iteration {iterations}", e)
                return f"❌ Unexpected error: {str(e)}\n\nCheck agent.log for details."

        self.logger.warning("Max iterations reached")
        return f"⚠️  Reached maximum iterations ({self.max_iterations})"

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
                response = asyncio.run(self.chat(q))
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


# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    try:
        agent = DefaultAgent()
        agent.chat_mode()
    except Exception as e:
        print(f"{Fore.RED}❌ Fatal error: {e}{Style.RESET_ALL}")
        logging.exception("fatal error")