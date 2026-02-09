import json
import os
import requests
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional

from src.utils.core.agent_logger import AgentLogger
from src.utils.core.token_tracker import TokenTracker
from src.utils.core.file_manager import FileManager
from src.utils.core.command_executor import CommandExecutor, SandboxLevel
from src.utils.core.git_manager import GitManager
from src.utils.core.code_analyzer import CodeAnalyzer
from src.utils.core.ollama_client import OllamaClient
from src.utils.core.memory_manager import MemoryManager
from src.utils.core.policy_manager import PolicyManager
from src.utils.core.tool_registry import ToolRegistry
from src.utils.core.loop_detector import LoopDetector

# Tool implementations
from src.utils.core.tool_interface import ToolConfirmationManager, ToolExecutor  # ToolExecutor kept as alias
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
from src.utils.core.all_tool_definitions import get_filtered_tool_definitions

# Maximum instruction length to prevent prompt injection / context flooding
MAX_INSTRUCTION_LENGTH = 10000 

# Initialize colorama (needed for print statements in some tool methods)
from colorama import init, Fore, Style
init(autoreset=True)


# ======================================================
# CODE AGENT (ENHANCED & FIXED)
# ======================================================

class DefaultAgent:
    def __init__(self, project_root: str | None = None, auto_confirm: bool = False, base_path: Path = Path.cwd()):
        self._base_path = base_path # The base path where the agent's own config and prompts are located
        self.project_root = Path(project_root or self._base_path) # The project root for the current task
        self.auto_confirm = auto_confirm # Store the auto_confirm flag
        
        # ---------------- LOGGING
        self.logger = AgentLogger(
            log_file=str(self.project_root / "agent.log")
        )
        self.logger.info(f"\n{Fore.GREEN}{'='*60}")
        self.logger.info(f"🤖 Code Agent Initialized")
        self.logger.info(f"{'='*60}{Style.RESET_ALL}")
        self.logger.info(f"📁 Project: {self.project_root}")

        # ---------------- CONFIG LOAD (relative to _base_path)
        config_path = self._base_path / "config" / "settings.json"
        if not config_path.exists():
            self.logger.error(f"Config file not found: {config_path}")
            raise FileNotFoundError(f"No existe config: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.max_iterations = self.config.get("max_iterations", 30)

        # ---------------- MEMORY MANAGEMENT
        self.memory_manager = MemoryManager(self.project_root, self.logger, config=self.config)
        self.conversation: List[Dict] = self.memory_manager.get_conversation_history()
        self.domain_context_memory: Dict[str, str] = self.memory_manager.get_domain_context_memory()

        # Checkpoint counter
        self.checkpoint_counter: int = 0

        # Hybrid Brain Model Configuration (centralized in settings.json "models" section)
        models_config = self.config.get("models", {})
        self.reasoning_model = models_config.get("reasoning", self.config.get("reasoning_model", "gpt-oss:20b"))
        self.coding_model = models_config.get("coding", self.config.get("coding_model", "qwen3-coder:30b"))
        self.self_correction_model = models_config.get("self_correction", self.config.get("self_correction_model", "ministral-3:8b"))
        self.orchestration_model = models_config.get("orchestration", self.config.get("orchestration_model", "ministral-3:8b"))
        self.summarization_model = models_config.get("summarization", self.config.get("summarization_model", "gpt-oss:20b"))
        self.current_llm_model = models_config.get("default", self.config.get("model", "qwen3-coder-next"))

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
        self.tool_executor = ToolExecutor(logger=self.logger, config=self.config, auto_confirm=self.auto_confirm) # Pass the logger and config instance and auto_confirm
        
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
                "init_args": {"logger": self.logger, "project_root": self.project_root} # agent_instance will be passed later
            },
            "network_tools": {
                "class": NetworkTools,
                "init_args": {"command_executor": self.command_executor, "logger": self.logger}
            },
            "system_tools": {
                "class": SystemTools,
                "init_args": {"command_executor": self.command_executor, "file_manager": self.file_manager, "logger": self.logger}
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

        # ---------------- OLLAMA
        ollama_url = os.environ.get("MOLTBOT_OLLAMA_URL", self.config.get("ollama_url", "http://localhost:11434"))
        self.ollama = OllamaClient(
            url=ollama_url,
            model=self.current_llm_model,
            timeout=self.config.get("timeout", 300),
            logger=self.logger,
            config=self.config
        )

        self.logger.info(f"Ollama: {ollama_url}")
        self.logger.info(f"Model: {self.current_llm_model} (Initial)")

        # ---------------- TOOL REGISTRY (extracted from inline dicts)
        self._tool_registry = ToolRegistry()
        self._all_tool_instances_mapping = ToolRegistry.TOOL_MAPPING
        self._agent_tool_name_mappings = ToolRegistry.AGENT_TOOLS

        self.active_agent_type = "orchestrator"
        self.active_tool_names = self._agent_tool_name_mappings[self.active_agent_type]

        # ---------------- LOOP DETECTOR (extracted from inline logic)
        self.loop_detector = LoopDetector(
            logger=self.logger,
            embedding_client=self.ollama,
            threshold=self.config.get("loop_detection_threshold", 3),
            similarity_threshold=self.config.get("semantic_similarity_threshold", 0.95),
            stagnation_timeout_minutes=2
        )

    def _calculate_message_tokens(self, messages: List[Dict]) -> int:
        """Estimates the total number of tokens in a list of messages. Delegates to MemoryManager."""
        return MemoryManager.estimate_tokens(messages)


    def _preprocess_instruction(self, instruction: str) -> tuple[str, str]:
        """
        Detects the language, translates to English, and refines the instruction.
        Returns (refined_english_instruction, original_language).
        """
        self.logger.info("Refining user instruction...")
        
        # Prompt for a quick model (can use the same or a smaller one like tinyllama)
        refine_prompt = [
            {"role": "system", "content": "You are a prompt engineer. Translate the user's request to English if it's in another language. Then, expand and clarify the request to be more effective for a coding agent. Return ONLY the refined English text."},
            {"role": "user", "content": f"Refine this: {instruction}"}
        ]
        
        try:
            # Use the orchestration model for pre-processing
            preprocess_client = OllamaClient(
                url=self.ollama.base_url,
                model=self.orchestration_model,
                timeout=self.ollama.timeout,
                logger=self.logger,
                config=self.config
            )
            response, _ = preprocess_client.chat(refine_prompt, tools=[])
            refined_text = response.get("message", {}).get("content", instruction)
            
            # Simple language detection (can use libraries like langdetect for more accuracy)
            # For now, assume if original input has non-English characters, it's the target language.
            original_lang = "es" if any(ord(c) > 127 for c in instruction) else "en" # Very basic
            
            return refined_text, original_lang
        except Exception as e:
            self.logger.error(f"Error in pre-processing: {e}")
            return instruction, "en" # Fallback to original instruction and English

    def _translate_to_user_language(self, text: str, target_lang: str) -> str:
        """Translates the final response to the user's original language."""
        if target_lang == "en":
            return text
            
        translation_prompt = [
            {"role": "system", "content": f"Translate the following technical response to {target_lang}. Maintain code blocks and technical terms as they are."},
            {"role": "user", "content": text}
        ]
        
        try:
            # Use the orchestration model for translation
            translate_client = OllamaClient(
                url=self.ollama.base_url,
                model=self.orchestration_model,
                timeout=self.ollama.timeout,
                logger=self.logger,
                config=self.config
            )
            response, _ = translate_client.chat(translation_prompt, tools=[])
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

    def _classify_intent(self, instruction: str) -> str:
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
            # Use a dedicated OllamaClient instance for classification using the orchestration model
            classification_ollama_client = OllamaClient(
                url=self.ollama.base_url,
                model=self.orchestration_model,
                timeout=self.ollama.timeout,
                logger=self.logger,
                config=self.config
            )
            response_data, _ = classification_ollama_client.chat(classification_prompt, tools=[])
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

            # Special handling for agent_instance for PlanningTools
            if toolset_identifier == "planning_tools":
                init_args["agent_instance"] = self

            # Special handling for orchestration_tools for require_human_gate
            # We need the orchestration_tools instance for the loop detection logic directly.
            # So, if this is orchestration_tools, we will just pass its instance directly.
            # This is a bit of a circular dependency, but orchestration_tools should be lightweight.
            # This block can be removed if orchestration_tools are just lazily loaded like others.
            # For now, keeping it explicit as orchestration_tools is critical for some agent decisions.
            if toolset_identifier == "orchestration_tools" and not hasattr(self, 'orchestration_tools'):
                self.orchestration_tools = toolset_class(**init_args)
                self._loaded_toolsets[toolset_identifier] = self.orchestration_tools
            elif toolset_identifier == "orchestration_tools": # If it's orchestration_tools but already loaded by some other path
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
            # Use the git_manager to stage and commit
            self.git_manager.stage_all()
            commit_message = f"Checkpoint {self.checkpoint_counter}"
            self.git_manager.commit(commit_message)
            self.logger.info(f"Successfully created checkpoint: {commit_message}")
            self.checkpoint_counter += 1
        except Exception as e:
            self.logger.error(f"Failed to create checkpoint: {e}")
            
    def _handle_tool_error(self, error_msg: str, original_tool_call: Dict):
        """
        Handles a tool execution error with a layered orchestration approach.
        """
        self.logger.info("Handling tool error with layered orchestration...")

        # Step 1: Search reasoning cache
        cached_solution = self.memory_manager.search_reasoning_cache(error_msg)
        if cached_solution:
            self.logger.info("Found a similar error in the reasoning cache. Applying cached solution.")
            try:
                # Assuming the cached solution is a JSON string of tool calls
                tool_calls = json.loads(cached_solution)
                self.conversation.append({
                    "role": "assistant",
                    "content": "I've seen a similar error before. Trying a known solution.",
                    "tool_calls": tool_calls
                })
                return True # Indicates that a solution has been queued
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to decode cached solution: {e}. Solution: {cached_solution}")

        # Step 2: Escalate to a small model for a quick fix attempt
        self.logger.info(f"Escalating to small model ({self.self_correction_model}) for error analysis.")
        correction_prompt = [
            {"role": "system", "content": "You are a self-correction AI. Analyze the following error and provide a single tool call to fix it. Respond in JSON format with 'tool_calls' and a 'confidence' score (0.0 to 1.0)."},
            {"role": "user", "content": f"The tool call {json.dumps(original_tool_call)} failed with this error:\n{error_msg}"}
        ]
        
        try:
            correction_client = OllamaClient(url=self.ollama.base_url, model=self.self_correction_model, timeout=self.config.get("timeout", 300), logger=self.logger, config=self.config)
            response, _ = correction_client.chat(correction_prompt, tools=[])
            
            response_content = response.get("message", {}).get("content", "")
            
            # Try to parse the JSON response from the small model
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
                    # Store the successful solution in the cache after it's been validated by execution
                    # This logic will be added in the main chat loop
                    return True
            except (json.JSONDecodeError, AttributeError):
                self.logger.warning("Small model did not provide a valid JSON response for error correction.")

        except Exception as e:
            self.logger.error(f"Error during small model self-correction: {e}")

        # Step 3: Escalate to a large model if the small model fails or has low confidence
        self.logger.info(f"Escalating to large model ({self.reasoning_model}) for deeper error analysis.")
        # The main loop will naturally handle this by re-prompting with the error message
        # We just need to add the error to the conversation
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

        # Filter conversation for messages that reference domain-specific tools
        relevant_snippets = []
        for msg in self.conversation:
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            # Check tool call messages
            for tc in tool_calls:
                tool_name = tc.get("function", {}).get("name", "")
                if tool_name in domain_tools:
                    relevant_snippets.append(f"[tool_call] {tool_name}: {json.dumps(tc['function'].get('arguments', {}))[:200]}")

            # Check tool result messages that follow domain tool calls
            if msg.get("role") == "tool" and content:
                relevant_snippets.append(f"[tool_result] {content[:300]}")

        if not relevant_snippets:
            return f"No prior activity found for domain '{domain_type}'."

        # Build a concise summary from the snippets (cap at 2000 chars)
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
                # Optionally, re-raise or handle more gracefully. For now, skip this tool.
        return active_tool_funcs

    def chat(self, instruction: str, auto_confirm: bool = False) -> str:
        # 0. Input validation
        if not instruction or not instruction.strip():
            return "Please provide an instruction."
        if len(instruction) > MAX_INSTRUCTION_LENGTH:
            return f"Instruction too long ({len(instruction)} chars). Maximum is {MAX_INSTRUCTION_LENGTH}."

        # Reset loop detector for each new user turn
        self.loop_detector.reset()

        # 1. Pre-processing Phase (Input)
        english_instruction, original_lang = self._preprocess_instruction(instruction)
        self.logger.info(f"Original Instruction: {instruction}")
        self.logger.info(f"Refined Instruction (EN): {english_instruction}")

        # Append the refined English instruction to the conversation
        if not self.conversation or self.conversation[-1]["role"] != "user":
            self.conversation.append({"role": "user", "content": english_instruction})
        
        # Classify intent for the current turn to select the appropriate model
        # Use the initial English instruction to classify intent for the current turn's primary action
        intent_for_this_turn = self._classify_intent(english_instruction)
        selected_model_for_this_turn = self._get_model_for_intent(intent_for_this_turn)
        
        # Set the OllamaClient's model for this specific chat call
        self.ollama.model = selected_model_for_this_turn
        self.logger.info(f"🧠 Current turn model selected based on intent '{intent_for_this_turn}': {selected_model_for_this_turn}")

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.conversation
        ]

        iterations = 0
        last_error_context = None # To store context of the last error

        while iterations < self.max_iterations:
            iterations += 1
            self.logger.info(f"\n{Fore.MAGENTA}━━━ Iteration {iterations}/{self.max_iterations} ━━━{Style.RESET_ALL}")

            # --- Intelligent Memory Management (Task 5) ---
            if self.memory_manager.needs_summarization(self.conversation, self.system_prompt):
                self.logger.info("Context token limit approaching. Delegating summarization to MemoryManager.")
                self.conversation = self.memory_manager.summarize_and_clean(self.conversation)
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    *self.conversation
                ]
            # --- End Intelligent Memory Management ---

            try:
                # Log API request
                self.logger.api_request(len(messages), len(self.tool_functions)) 
                
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

                # If the LLM responds with a plain message, treat it as a final answer.
                if "tool_calls" not in msg:
                    self.logger.api_response(False)
                    final_response_en = msg.get("content", "") 
                    
                    # If there was a previous error, and we got a final answer, store the solution
                    if last_error_context:
                        self.memory_manager.add_to_reasoning_cache(last_error_context["error"], final_response_en)
                        last_error_context = None

                    final_response_translated = self._translate_to_user_language(final_response_en, original_lang)
                    self.conversation.append({"role": "assistant", "content": final_response_en})
                    self.logger.info(f"{Fore.GREEN}✅ Final answer generated{Style.RESET_ALL}")
                    return final_response_translated 

                # Process tool calls
                tool_calls = msg["tool_calls"]
                self.logger.api_response(True, len(tool_calls))
                self.conversation.append(msg) # Add LLM's tool call message to conversation history

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
                            # Execute tool using lazy loading
                            result = self._get_tool_from_toolset(name)(**args)
                            
                            # --- Checkpoint after state-modifying tools ---
                            state_modifying_tools = ["write_file", "delete_file", "run_command", "install_package"]
                            if name in state_modifying_tools and result.get("ok", True):
                                self._create_checkpoint()

                                # If there was a previous error, and this tool call succeeded, store the solution
                                if last_error_context:
                                    solution = json.dumps([{"function": {"name": name, "arguments": args}}])
                                    self.memory_manager.add_to_reasoning_cache(last_error_context["error"], solution)
                                    last_error_context = None
                            
                            # --- Loop Detection (delegated to LoopDetector) ---
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
                            # --- End Loop Detection ---

                            # Old logic related to select_agent_type, keep it
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
                        
                        # Add result to conversation
                        self.conversation.append({
                            "role": "tool",
                            "content": json.dumps(result)
                        })
                        
                    except Exception as e:
                        error_msg = f"Tool execution failed: {str(e)}"
                        self.logger.error(error_msg, e)
                        
                        last_error_context = {"error": error_msg, "tool_call": tc}
                        
                        if self._handle_tool_error(error_msg, tc):
                            continue
                        
                        # If auto_confirm is True and a tool fails, it's a critical error for the current step.
                        if auto_confirm:
                            return f"❌ Critical error during tool execution in auto-mode: {error_msg}. Human intervention required."
                    
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
                       f"Configured URL: {self.ollama.base_url}") # Use base_url from ollama client.
            
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
                response = self.chat(q)
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