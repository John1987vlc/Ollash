import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from colorama import Fore, Style, init

# Core Agent and Kernel
from backend.agents.core_agent import CoreAgent
from backend.agents.mixins.context_summarizer_mixin import ContextSummarizerMixin

# Mixins
from backend.agents.mixins.intent_routing_mixin import IntentRoutingMixin
from backend.agents.mixins.tool_loop_mixin import ToolLoopMixin
from backend.core.config_schemas import (
    LLMModelsConfig,  # For type hinting
    ToolSettingsConfig,
)
from backend.core.kernel import AgentKernel  # Import AgentKernel

# Interfaces (for type hinting, if needed for clarity on injected components)
from backend.interfaces.imodel_provider import IModelProvider
from backend.interfaces.itool_executor import IToolExecutor
from backend.utils.core.tools.async_tool_executor import AsyncToolExecutor  # Still used for parallel execution
from backend.utils.core.analysis.code_analyzer import CodeAnalyzer
from backend.utils.core.command_executor import CommandExecutor, SandboxLevel
from backend.utils.core.system.confirmation_manager import ConfirmationManager  # New: For confirmation gates

# Utils from Core
from backend.utils.core.io.file_manager import FileManager
from backend.utils.core.io.git_manager import GitManager
from backend.utils.core.llm.llm_recorder import LLMRecorder  # NEW
from backend.utils.core.llm.llm_response_parser import LLMResponseParser
from backend.utils.core.llm.prompt_loader import PromptLoader
from backend.utils.core.system.loop_detector import LoopDetector
from backend.utils.core.memory.memory_manager import MemoryManager
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.core.system.permission_profiles import PolicyEnforcer  # Used for confirmation gates policies

# Tool implementations (still needed for ToolRegistry)
from backend.utils.core.tools.tool_interface import ToolExecutor  # Concrete ToolExecutor
from backend.utils.core.tools.tool_registry import ToolRegistry
from backend.utils.core.tools.tool_span_manager import ToolSpanManager  # NEW

from backend.services.language_manager import LanguageManager

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

    def __init__(
        self,
        project_root: str | None = None,
        auto_confirm: bool = False,
        base_path: Path = Path.cwd(),
        event_bridge=None,
        kernel: Optional[AgentKernel] = None,  # Inject AgentKernel
        llm_manager: Optional[IModelProvider] = None,  # Inject LLMClientManager (as IModelProvider)
        tool_executor: Optional[IToolExecutor] = None,  # Inject ToolExecutor
        loop_detector: Optional[LoopDetector] = None,  # Inject LoopDetector
        confirmation_manager: Optional[ConfirmationManager] = None,  # Inject ConfirmationManager
        policy_enforcer: Optional[PolicyEnforcer] = None,  # Inject PolicyEnforcer
        llm_recorder: Optional[LLMRecorder] = None,  # NEW
        tool_span_manager: Optional[ToolSpanManager] = None,  # NEW
        event_publisher: Optional[EventPublisher] = None,  # NEW
    ):
        # Initialize AgentKernel if not provided (should ideally be provided)
        # The kernel now loads configuration from environment variables.
        self.kernel = kernel if kernel else AgentKernel(ollash_root_dir=Path(project_root) if project_root else None)

        # Initialize LLMRecorder and ToolSpanManager if not injected
        self.llm_recorder = llm_recorder if llm_recorder else LLMRecorder(logger=self.kernel.get_logger())
        self.tool_span_manager = (
            tool_span_manager if tool_span_manager else ToolSpanManager(logger=self.kernel.get_logger())
        )

        # Call parent constructor, passing the kernel and llm_manager
        super().__init__(
            kernel=self.kernel,
            logger_name="DefaultAgent",
            llm_manager=llm_manager,
            llm_recorder=self.llm_recorder,
            event_publisher=event_publisher,
        )

        # Language standardization
        self.language_manager = LanguageManager(self.llm_manager)

        # Access config and logger from Kernel (they are set by CoreAgent's __init__)
        # No need to re-assign self.logger, self.config here as CoreAgent does it
        # However, these are still needed for direct access in DefaultAgent
        self.llm_models_config: LLMModelsConfig = self.kernel.get_llm_models_config()
        self.tool_settings_config: ToolSettingsConfig = self.kernel.get_tool_settings_config()

        self._base_path = base_path
        self.project_root = Path(project_root or self._base_path)
        self.auto_confirm = auto_confirm
        self._event_bridge = event_bridge

        self.max_iterations = self.tool_settings_config.max_iterations  # Get from tool_settings_config

        self.logger.info(f"\n{Fore.GREEN}{'=' * 60}")
        self.logger.info("Default Agent Initialized")
        self.logger.info(f"{'=' * 60}{Style.RESET_ALL}")
        self.logger.info(f"📁 Project: {self.project_root}")

        # Core Services (some might be from CoreAgent, others instantiated here for DefaultAgent's specific needs)
        self.file_manager = FileManager(str(self.project_root))
        self.command_executor = CommandExecutor(
            str(self.project_root),
            SandboxLevel.LIMITED,
            logger=self.logger,
            use_docker_sandbox=self.tool_settings_config.use_docker_sandbox,
        )  # Use tool_settings_config
        self.git_manager = GitManager(str(self.project_root))
        self.code_analyzer = CodeAnalyzer(str(self.project_root))

        # --- Dependencies for Mixins & CoreAgent (injected or initialized) ---
        # self.llm_manager is from CoreAgent, now injected or created in super()
        # MemoryManager (still directly instantiated for now, could be its own service)
        self.memory_manager = MemoryManager(
            self.project_root,
            self.logger,
            config=self.kernel.get_full_config(),
            llm_recorder=self.llm_recorder,
        )  # Pass full raw config
        self.token_tracker = self.token_tracker  # From CoreAgent, used by ContextSummarizerMixin
        self.event_publisher = self.event_publisher  # From CoreAgent, used by mixins

        # Confirmation & Policy for ToolLoopMixin
        self.confirmation_manager = (
            confirmation_manager
            if confirmation_manager
            else ConfirmationManager(
                logger=self.logger,
                auto_confirm=self.auto_confirm,
                config=self.tool_settings_config,
                event_publisher=self.event_publisher,  # F31: Pass event_publisher
            )
        )
        self.policy_enforcer = (
            policy_enforcer
            if policy_enforcer
            else PolicyEnforcer(
                profile_manager=self.permission_manager,
                logger=self.logger,
                tool_settings_config=self.tool_settings_config,  # NEW
            )
        )
        # Link policy_enforcer to command_executor
        self.command_executor.policy_manager = self.policy_enforcer

        # F33: Set initial profile to developer for testing
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
            tool_executor=None,  # Temporarily set to None to avoid circular dependency
            confirmation_manager=self.confirmation_manager,  # Pass confirmation_manager
        )
        self._all_tool_instances_mapping = self._tool_registry.get_tool_mapping()
        self._agent_tool_name_mappings = self._tool_registry.get_agent_tools()

        # Initialize ToolExecutor with the fully initialized ToolRegistry and agent_instance
        self.tool_executor = (
            tool_executor
            if tool_executor
            else ToolExecutor(
                tool_registry=self._tool_registry,
                agent_instance=self,  # Pass self as the agent_instance
            )
        )
        # Now set the tool_executor in ToolRegistry to resolve the circular dependency
        self._tool_registry.tool_executor = self.tool_executor

        self.async_tool_executor = AsyncToolExecutor(
            self._execute_single_tool,
            tool_registry=self._tool_registry,  # Pass the initialized ToolRegistry
        )

        # Loop Detector (injected or initialized)
        self.loop_detector = (
            loop_detector
            if loop_detector
            else LoopDetector(
                logger=self.logger,
                embedding_client=self.llm_manager.get_client("default"),  # Use llm_manager for embedding client
                threshold=10,  # F33: Increased for mass testing
                similarity_threshold=self.tool_settings_config.semantic_similarity_threshold,  # From tool_settings_config
                stagnation_timeout_minutes=5,  # F33: Increased
            )
        )

        # Load system prompt from file
        default_prompt_path = self.tool_settings_config.default_system_prompt_path  # From tool_settings_config
        try:
            loader = PromptLoader(prompts_dir=self._base_path / "prompts")
            prompt_data = loader.load_prompt_sync(default_prompt_path)

            self.system_prompt = prompt_data.get("prompt", "")
            if not self.system_prompt:
                # Fallback check for 'system' key if 'prompt' is missing
                self.system_prompt = prompt_data.get("system", "")

            if not self.system_prompt:
                self.logger.warning(f"System prompt field empty in {default_prompt_path}. Using default fallback.")
                self.system_prompt = self._get_fallback_system_prompt()
        except Exception as e:
            self.logger.error(f"Error loading system prompt from {default_prompt_path}: {e}. Using default fallback.")
            self.system_prompt = self._get_fallback_system_prompt()

        self.conversation: List[Dict] = []
        self.domain_context_memory: Dict[str, str] = self.memory_manager.get_domain_context_memory()
        self.checkpoint_counter: int = 0
        self.active_agent_type = "orchestrator"
        self.active_tool_names = self._agent_tool_name_mappings[self.active_agent_type]

        # F32: Plan Execution Driver State
        self._active_plan: List[str] = []
        self._current_step_index: int = 0
        self._plan_goal: str = ""

        # F33: Persist failed calls history across iterations within a single chat turn
        self._failed_calls_tracker: Dict[str, int] = {}

        self.logger.info(f"Ollama URL: {self.llm_models_config.ollama_url}")  # Access from llm_models_config
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

        try:
            loader = PromptLoader()
            prompts = loader.load_prompt_sync("core/services.yaml")

            system = prompts.get("prompt_engineering", {}).get("system", "")
            user_template = prompts.get("prompt_engineering", {}).get("user", "")
            user = user_template.format(text=instruction)

            preprocess_client = await self.llm_manager.get_client("orchestration")  # Use llm_manager
            response, _ = await preprocess_client.achat(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], tools=[]
            )
            refined_text = response.get("message", {}).get("content", instruction)

            original_lang = "es" if any(ord(c) > 127 for c in instruction) else "en"  # Very basic

            return refined_text, original_lang
        except Exception as e:
            self.logger.error(f"Error in pre-processing: {e}")
            return instruction, "en"  # Fallback to original instruction and English

    async def _translate_to_user_language(self, text: str, target_lang: str) -> str:
        """Translates the final response to the user's original language."""
        if target_lang == "en":
            return text

        try:
            loader = PromptLoader()
            _prompts = loader.load_prompt_sync("core/services.yaml")

            # Use translation standardization as base for final translation
            system = "You are a professional translator."
            user = f"Translate the following technical response to {target_lang}. Maintain code blocks and technical terms as they are.\n\nText: {text}"

            translate_client = self.llm_manager.get_client("orchestration")  # Use llm_manager
            response, _ = await translate_client.achat(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], tools=[]
            )
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

    async def _audit_mission_progress(self, user_instruction: str) -> Dict[str, Any]:
        """Calls the mission control model to evaluate progress and provide guidance."""
        client = self.llm_manager.get_client("orchestration")
        if not client:
            return {}

        try:
            loader = PromptLoader()
            prompts = loader.load_prompt_sync("core/services.yaml")

            audit_def = prompts.get("mission_audit", {})
            system = audit_def.get("system", "")
            user_template = audit_def.get("user", "")

            # Prepare compact history for auditor (last 5 tool results)
            tool_history = [msg for msg in self.conversation if msg["role"] == "tool"][-5:]

            user = user_template.format(
                goal=user_instruction, plan=json.dumps(self._active_plan), history=json.dumps(tool_history)
            )

            response, _ = await client.achat(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                tools=[],
                options_override={"temperature": 0.0},  # Maximum precision
            )

            content = response.get("message", {}).get("content", "")
            # Robust JSON extraction
            if "{" in content:
                content = content[content.find("{") : content.rfind("}") + 1]

            audit_result = json.loads(content)
            self.logger.info(
                f"🛰️ Mission Audit: {audit_result.get('mission_status')} - {audit_result.get('next_action_guidance')}"
            )
            return audit_result
        except Exception as e:
            self.logger.warning(f"Failed to perform mission audit: {e}")
            return {}

    async def _select_dynamic_tools(self, user_instruction: str) -> List[str]:
        """
        Intermediary step: Selects the most relevant tools for the current prompt
        to minimize context overhead.
        """
        client = self.llm_manager.get_client("orchestration")
        if not client:
            return self.active_tool_names

        try:
            # 1. Get lightweight summaries of currently active toolset
            summaries = self.tool_executor.tool_registry.get_tool_summaries(self.active_tool_names)

            # 2. Prepare Tool Selection Prompt
            loader = PromptLoader()
            prompts = loader.load_prompt_sync("core/services.yaml")

            sel_def = prompts.get("tool_selection", {})
            system = sel_def.get("system", "")
            user_template = sel_def.get("user", "")

            user = user_template.format(text=user_instruction, tools=json.dumps(summaries, indent=2))

            response, _ = await client.achat(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], tools=[]
            )

            if response and response.get("message") and response["message"].get("content"):
                content = response["message"]["content"].strip()
                # Clean potential markdown noise
                clean_json, _ = LLMResponseParser.remove_think_blocks(content)
                clean_json = clean_json.replace("```json", "").replace("```", "").strip()

                try:
                    selected = json.loads(clean_json)
                except (json.JSONDecodeError, ValueError):
                    # Fallback for Malformed JSON from some SMLs
                    selected = [t for t in self.active_tool_names if t in clean_json]

                if isinstance(selected, list):
                    # F33: Safety - Always ensure core orchestration and shell tools are present if they were in the original set
                    mandatory = [
                        "plan_actions",
                        "select_agent_type",
                        "run_shell_command",
                        "run_command",
                        "analyze_project",
                        "traceroute_host",
                    ]
                    for tool in mandatory:
                        if tool in self.active_tool_names and tool not in selected:
                            selected.append(tool)

                    # Filter only valid tools from the active set
                    final_tools = [t for t in selected if t in self.active_tool_names]

                    self.logger.info(
                        f"🎯 JIT Tool Selection: {len(final_tools)}/{len(self.active_tool_names)} tools enabled."
                    )
                    return final_tools

        except Exception as e:
            self.logger.warning(f"Tool Selection failed: {e}. Falling back to full toolset.")

        return self.active_tool_names

    async def chat(self, instruction: str, auto_confirm: bool = False) -> str:
        correlation_id: Optional[str] = None
        start_turn_time = time.time()
        start_tokens = self.token_tracker.session_total_tokens

        try:
            # Start interaction context with a correlation ID
            correlation_id = self.kernel.start_interaction_context()

            # 0. Input validation & Robust Normalization (F33)
            if not instruction or not instruction.strip():
                return "Please provide an instruction."

            # Remove ONLY control characters, keep all printable (including international)
            clean_instruction = "".join(ch for ch in instruction if ch.isprintable() or ch in "\n\r\t")
            # Minimal replacement
            clean_instruction = (
                clean_instruction.replace("\u201c", '"').replace("\u201d", '"').replace("\u2013", "-").strip()
            )

            if len(clean_instruction) > MAX_INSTRUCTION_LENGTH:
                return f"Instruction too long ({len(clean_instruction)} chars). Maximum is {MAX_INSTRUCTION_LENGTH}."

            self.loop_detector.reset()

            # 1. Direct Instruction usage (F33: Skip brittle preprocessing for scenarios)
            english_instruction = instruction
            original_lang = "es" if any(ord(c) > 127 for c in instruction) else "en"

            self.logger.info(f"Original Instruction: {instruction}")

            # 2. Prepare Clean System Prompt
            import platform

            os_name = platform.system()
            os_release = platform.release()
            shell_name = "PowerShell" if os_name == "Windows" else "Bash"
            os_info = f"Current Operating System: {os_name} {os_release}. ACTIVE SHELL: {shell_name}"

            # Do NOT modify self.system_prompt permanently here to avoid cumulative corruption
            current_system_prompt = await self.language_manager.standardize_prompt(self.system_prompt)
            current_system_prompt = (
                "# MANDATORY: DATA FRESHNESS\n"
                "Technical data (IPs, processes, files, disk space) from conversation history may be STALE. Always run tools to get the CURRENT state if the user asks for it.\n\n"
            ) + (
                f"# CRITICAL ENVIRONMENT INFO\n"
                f"You are running on: {os_info}\n"
                f"Available tools are context-aware for this OS. Always prioritize {shell_name} commands if on {os_name}.\n\n"
                f"{current_system_prompt}"
            )

            # Mandatory rule for English output (only if not already there)
            english_rule = "\n\nMANDATORY RULE: All internal reasoning, thinking process, and tool calls MUST be in English. Reasoning must be inside <thinking_process> tags. Code must be inside <code_created> tags."
            if "MANDATORY RULE" not in current_system_prompt:
                current_system_prompt += english_rule

            # F33: Explicit Shell Syntax Rule
            shell_rule = f"\n\n# SHELL SYNTAX RULE\nSince you are on {os_name}, you MUST use {shell_name} syntax for all run_command calls. Do not use Bash features (like 'for' loops or pipes) if you are on Windows unless they are supported by PowerShell."
            current_system_prompt += shell_rule

            if not self.conversation or self.conversation[-1]["role"] != "user":
                self.conversation.append({"role": "user", "content": english_instruction})

            # --- Intent Routing Mixin Usage ---
            intent_for_this_turn = await self._classify_intent(english_instruction)  # Use mixin method

            # F31: Switch toolset to the classified intent IMMEDIATELY

            # F31: Switch toolset to the classified intent (or reset to orchestrator)
            target_agent = (
                intent_for_this_turn if intent_for_this_turn in self._agent_tool_name_mappings else "orchestrator"
            )
            if target_agent in self._agent_tool_name_mappings:
                self.active_agent_type = target_agent
                specialist_tools = self._agent_tool_name_mappings[target_agent]
                core_tools = self._agent_tool_name_mappings.get("orchestrator", [])
                self.active_tool_names = list(set(specialist_tools + core_tools))
                self.logger.info(f"🛠️ Toolset switched to: {target_agent} (merged with orchestrator tools)")

            # F33: Always use orchestration client for routing and flow control
            _orchestration_client = self.llm_manager.get_client("orchestration")
            selected_model_client = self._select_model_for_intent(intent_for_this_turn)

            # F30: Notify UI about the routing decision immediately
            if self._event_bridge:
                self._event_bridge.push_event(
                    "routing",
                    {
                        "intent": intent_for_this_turn,
                        "model": selected_model_client.model,
                        "message": f"Routing request to {intent_for_this_turn} specialist...",
                    },
                )

            # --- Specialist Prompt Injection ---
            # If we switched to a specialist, load their prompt and prepend it
            specialist_base_prompt = ""
            if intent_for_this_turn != "orchestrator":
                try:
                    loader = PromptLoader()
                    specialist_data = loader.load_prompt_sync(
                        f"{intent_for_this_turn}/default_{intent_for_this_turn}_agent.yaml"
                    )
                    specialist_base_prompt = specialist_data.get("prompt") or specialist_data.get("system", "")
                    if specialist_base_prompt:
                        self.logger.info(f"💉 Specialist prompt prepared for: {intent_for_this_turn}")
                except Exception as e:
                    self.logger.warning(f"Failed to load specialist prompt: {e}")

            # F33: Unified Robust System Prompt

            # F31: Clean unified prompt - if specialist, prioritize their context
            if specialist_base_prompt:
                # Remove redundant "You are..." context from base prompt to avoid confusion
                # We assume the base prompt has instructions and rules we want to keep
                clean_base = current_system_prompt
                # Remove redundant headers to keep only technical rules for the specialist
                if "RULES:" in clean_base:
                    clean_base = "RULES:\n" + clean_base.split("RULES:", 1)[-1]
                elif "# INSTRUCTIONS" in clean_base:
                    clean_base = "# INSTRUCTIONS\n" + clean_base.split("# INSTRUCTIONS", 1)[-1]
                current_system_prompt = f"{specialist_base_prompt}\n\n---\n\n{clean_base}"

            current_system_prompt += "\n\nMANDATORY: You MUST call a tool (e.g. plan_actions) in your FIRST turn. Text responses are forbidden."

            # Override default client for this turn, or use it for routing later
            self.logger.info(f"🧠 Phase: Intent Classification -> Result: '{intent_for_this_turn}'")
            self.logger.info(f"🧠 Routing: Using model {selected_model_client.model} for this turn.")

            iterations = 0
            last_error_context = None
            self._active_plan = []  # Reset for new chat
            self._current_step_index = 0
            self._failed_calls_tracker = {}  # F33: Reset failure memory for this turn

            # F33: State trackers to avoid redundant operations in loop
            last_jit_agent_type = None
            current_turn_tools = []
            cached_memory_context = None

            while iterations < self.max_iterations:
                iterations += 1
                self.logger.info(
                    f"\n{Fore.MAGENTA}━━━ Iteration {iterations}/{self.max_iterations} ━━━{Style.RESET_ALL}"
                )
                if self._event_bridge:
                    self._event_bridge.push_event("iteration", {"current": iterations, "max": self.max_iterations})
                
                if self.event_publisher:
                    await self.event_publisher.publish("thinking", {"message": f"Starting iteration {iterations}..."})

                # F33: JIT Tool Selection - Only re-select if agent type changed or first iteration
                if self.active_agent_type != last_jit_agent_type:
                    if self.event_publisher:
                        await self.event_publisher.publish("thinking", {"message": f"Selecting relevant tools for {self.active_agent_type}..."})
                    self.logger.debug(f"DEBUG - Entering JIT Tool Selection for agent type: {self.active_agent_type}")
                    current_turn_tools = await self._select_dynamic_tools(english_instruction)
                    last_jit_agent_type = self.active_agent_type
                    self.logger.debug(f"DEBUG - JIT Tool Selection completed. Tools: {current_turn_tools}")

                # F31: Strictly limit session window to last 10 messages for extreme focus
                session_history = self.conversation[-10:]

                # F33: Clean old Guidance noise from session history before sending to LLM
                # This prevents "Guidance Stack" where old instructions pollute the context
                cleaned_history = []
                for msg in session_history:
                    clean_msg = msg.copy()
                    if isinstance(clean_msg.get("content"), str):
                        # Strip all legacy guidance blocks
                        if "[MISSION CONTROL GUIDANCE]" in clean_msg["content"]:
                            clean_msg["content"] = clean_msg["content"].split("[MISSION CONTROL GUIDANCE]")[0].strip()
                        if "[MISSION CONTROL GUIDANCE - MANDATORY]" in clean_msg["content"]:
                            clean_msg["content"] = (
                                clean_msg["content"].split("[MISSION CONTROL GUIDANCE - MANDATORY]")[0].strip()
                            )
                    cleaned_history.append(clean_msg)

                # F31: Retrieval from Long-Term Memory - Only search once per turn
                if cached_memory_context is None:
                    try:
                        self.logger.info("🧠 Searching memory for relevant patterns...")
                        query = english_instruction
                        past_context = self.memory_manager.search_message_memory(query, threshold=0.4)
                        if past_context:
                            cached_memory_context = (
                                f"\n\n[PAST INTERACTION CONTEXT - DO NOT ASSUME VALUES ARE CURRENT]\n{past_context}\n"
                            )
                            self.logger.info("🛰️ Relevant past context injected.")
                        else:
                            cached_memory_context = ""  # Mark as searched but empty
                    except Exception:
                        cached_memory_context = ""

                iteration_messages = [
                    {"role": "system", "content": current_system_prompt + (cached_memory_context or "")},
                    *cleaned_history,
                ]

                # F33: Keep tools synchronized with current agent type
                self.active_tool_names = list(
                    set(
                        self._agent_tool_name_mappings.get(self.active_agent_type, [])
                        + self._agent_tool_name_mappings.get("orchestrator", [])
                        + ["run_shell_command"]  # FORCE Universal availability
                    )
                )

                self.logger.debug(f"Context depth: {len(iteration_messages)} messages")
                # --- Context Summarizer Mixin Usage ---
                iteration_messages = await self._manage_context_window(iteration_messages)  # Use mixin method

                # F31: Get schema-valid tools for this turn ONLY
                turn_tool_definitions = self.tool_executor.get_tool_definitions(current_turn_tools)

                # F32: Inject Plan Route Guidance (only to the runtime messages, not the persistent conversation)
                runtime_messages = iteration_messages.copy()
                if self._active_plan:
                    if self._current_step_index < len(self._active_plan):
                        current_step = self._active_plan[self._current_step_index]

                        # F33: Incorporate Mission Auditor guidance if available
                        audit_instruction = (
                            getattr(self, "_audit_guidance", None) or "Execute the next tool required for this step."
                        )

                        guidance = (
                            f"\n\n[MISSION CONTROL GUIDANCE]\n"
                            f"Goal: {self._plan_goal}\n"
                            f"Current Step ({self._current_step_index + 1}/{len(self._active_plan)}): {current_step}\n"
                            f"Auditor Note: {audit_instruction}\n"
                            f"Status: EXECUTION. Call the tool or answer user based on Auditor Note."
                        )
                    else:
                        guidance = "\n\n[MISSION CONTROL GUIDANCE - MANDATORY] Goal achieved. Information is sufficient. Do NOT call more tools. Summarize findings and provide the final answer to the user IMMEDIATELY."

                    if runtime_messages:
                        # Append to the last user/assistant message to keep context strong
                        last_idx = -1
                        while abs(last_idx) <= len(runtime_messages):
                            if runtime_messages[last_idx]["role"] in ["user", "assistant"]:
                                runtime_messages[last_idx] = runtime_messages[last_idx].copy()
                                runtime_messages[last_idx]["content"] += guidance
                                break
                            last_idx -= 1

                try:
                    self.logger.debug(f"Total prompt messages sent to LLM: {len(runtime_messages)}")
                    # F33: Use synchronous chat to avoid streaming hangs in some environments
                    self.logger.info(f"📡 Calling {selected_model_client.model} (Synchronous)...")
                    
                    if self.event_publisher:
                        await self.event_publisher.publish("thinking", {"message": f"Agent is processing with {selected_model_client.model}..."})

                    # Perform synchronous chat
                    response_data, usage = await selected_model_client.achat(
                        messages=runtime_messages, tools=turn_tool_definitions
                    )

                    msg = {
                        "role": "assistant",
                        "content": response_data.get("content", ""),
                        "tool_calls": response_data.get("tool_calls", []),
                    }
                    
                    self.logger.info(f"DEBUG: RAW LLM response content length: {len(msg['content'])}")
                    if len(msg["content"]) < 100:
                        self.logger.info(f"DEBUG: RAW LLM response content: '{msg['content']}'")

                    # F33: Clean reasoning noise for humans, but keep message structure for Ollama
                    content = msg.get("content", "")

                    if content and not msg.get("tool_calls"):
                        # F33: Use shared parser for consistency
                        cleaned_content, reasoning = LLMResponseParser.remove_think_blocks(content)

                        # If there was reasoning, publish it as a single block for the UI
                        if reasoning and self.event_publisher:
                            await self.event_publisher.publish("token", {"text": f"\n\n> {reasoning}\n\n"})

                        # Only update if there is actual text left, otherwise keep original to avoid empty UI
                        if cleaned_content.strip():
                            msg["content"] = cleaned_content

                        # Extra cleaning for legacy noise
                        if "Output:**" in msg["content"]:
                            msg["content"] = msg["content"].split("Output:**")[-1].strip()
                    
                    # F31: Robust Manual tool detection fallback using unified parser
                    if not msg.get("tool_calls"):
                        extracted_calls = LLMResponseParser.parse_tool_calls(content)
                        if extracted_calls:
                            msg["tool_calls"] = extracted_calls
                            self.logger.info(f"?? Parsed {len(extracted_calls)} tool call(s) from text output.")

                    # F20: Track tokens from the usage dictionary returned by the client
                    self.token_tracker.add_usage(
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0),
                    )

                    self.token_tracker.display_current()

                    if not msg.get("tool_calls"):
                        self.logger.thinking("Analyzing final answer from LLM...")
                        
                        # F33: Get the ALREADY CLEANED content from msg
                        final_response_en = msg.get("content", "")
                        
                        self.logger.info(f"DEBUG: LLM Content raw length: {len(final_response_en)}")

                        if last_error_context:
                            self.memory_manager.add_to_reasoning_cache(last_error_context["error"], final_response_en)
                            last_error_context = None

                        # F33: Technical Passthrough - Do not translate if response contains code or tool blocks
                        # to avoid "translation manual" hallucinations.
                        is_technical = (
                            "```" in final_response_en or "[TOOL" in final_response_en or "{" in final_response_en
                        )

                        if is_technical:
                            final_response = final_response_en
                        else:
                            # F29: Translate the final response back to the user's language
                            self.logger.info(f"Translating response to {original_lang}...")
                            final_response = await self._translate_to_user_language(final_response_en, original_lang)

                        # F33: Safety fallback - if translation or cleaning returned empty, use original content
                        if not final_response and final_response_en:
                            self.logger.warning("Final response was empty after processing, using original content.")
                            final_response = final_response_en
                        
                        if not final_response:
                            # F33: If we get multiple empty responses, stop to avoid infinite loops
                            if iterations > 3:
                                final_response = "I'm sorry, I'm having trouble generating a response with the current model. Please try a more capable model or rephrase your request."
                            else:
                                final_response = "I'm sorry, I generated an empty response. Please try again or rephrase your request."

                        self.logger.info(f"DEBUG: Final response length: {len(final_response)}")
                        self.conversation.append({"role": "assistant", "content": final_response})
                        self.logger.info(f"{Fore.GREEN}✅ Final answer generated{Style.RESET_ALL}")

                        # F20: Prepare detailed metrics for this turn
                        elapsed = time.time() - start_turn_time
                        token_delta = self.token_tracker.session_total_tokens - start_tokens

                        turn_data = {
                            "text": final_response,
                            "metrics": {
                                "duration": round(elapsed, 2),
                                "tokens": token_delta,
                                "iterations": iterations,
                            },
                        }
                        return turn_data

                    tool_calls = msg["tool_calls"]
                    # self.logger.api_response(True, len(tool_calls)) # REMOVED, LLMRecorder handles
                    self.conversation.append(msg)

                    # --- Tool Loop Mixin Usage ---
                    self.logger.info(f"🧠 Phase: Executing {len(tool_calls)} Tool(s)")
                    tool_outputs = await self._execute_tool_loop(tool_calls, english_instruction)  # Use mixin method

                    for result in tool_outputs:
                        self.conversation.append({"role": "tool", "content": json.dumps(result)})

                        # F32: Basic plan capture (no driver)
                        if result.get("tool_name") == "plan_actions" and result.get("ok"):
                            output_data = result.get("output", {})
                            if isinstance(output_data, dict) and output_data.get("ok"):
                                plan_details = output_data.get("result", {})
                                self._active_plan = plan_details.get("steps", [])
                                self._plan_goal = plan_details.get("goal", "")
                                self.logger.info(f"📍 Plan captured: {len(self._active_plan)} steps.")

                        if isinstance(result, dict) and not result.get("ok"):
                            # F33: Better error extraction from tool result
                            error_msg = result.get("error")
                            if not error_msg:
                                tool_out = result.get("output")
                                if isinstance(tool_out, str):
                                    error_msg = tool_out
                                elif isinstance(tool_out, dict):
                                    error_msg = tool_out.get("error") or tool_out.get("message") or "Unknown tool error"
                                else:
                                    error_msg = "Unknown tool error"
                            
                            tool_name = result.get("tool_name", "unknown")

                            if self._event_bridge:
                                self._event_bridge.push_event("error", {"message": error_msg, "tool": tool_name})

                            original_tool_call = next(
                                (tc for tc in tool_calls if tc.get("id") == result.get("tool_call_id")),
                                {},
                            )
                            last_error_context = {
                                "error": error_msg,
                                "tool_call": original_tool_call,
                            }

                            self.logger.info("Handling tool error with layered orchestration...")
                            # (Rest of error logic follows correctly indented)

                            cached_solution = self.memory_manager.search_reasoning_cache(error_msg)
                            if cached_solution:
                                self.logger.info(
                                    "Found a similar error in the reasoning cache. Applying cached solution."
                                )
                                try:
                                    tool_calls_from_cache = json.loads(cached_solution)
                                    self.conversation.append(
                                        {
                                            "role": "assistant",
                                            "content": "I've seen a similar error before. Trying a known solution.",
                                            "tool_calls": tool_calls_from_cache,
                                        }
                                    )
                                    continue  # Continue the loop to execute cached solution
                                except json.JSONDecodeError as e:
                                    self.logger.error(
                                        f"Failed to decode cached solution: {e}. Solution: {cached_solution}"
                                    )

                            self.logger.info("Escalating to small model for error analysis.")
                            correction_client = self.llm_manager.get_client("self_correction")
                            if correction_client:
                                try:
                                    loader = PromptLoader()
                                    prompts = loader.load_prompt_sync("core/services.yaml")
                                    system = prompts.get("self_correction", {}).get("system", "")
                                    user_template = prompts.get("self_correction", {}).get("user", "")
                                    user = user_template.format(
                                        error=f"The tool call {json.dumps(original_tool_call)} failed with this error:\n{error_msg}"
                                    )

                                    response, _ = await correction_client.achat(
                                        messages=[
                                            {"role": "system", "content": system},
                                            {"role": "user", "content": user},
                                        ],
                                        tools=[],
                                    )
                                    response_content = response.get("message", {}).get("content", "")
                                    solution_data = json.loads(response_content)
                                    confidence = solution_data.get("confidence", 0.0)
                                    tool_calls_from_correction = solution_data.get("tool_calls")

                                    if confidence > 0.8 and tool_calls_from_correction:
                                        self.logger.info(
                                            f"Small model provided a high-confidence solution (confidence: {confidence}). Applying fix."
                                        )
                                        self.conversation.append(
                                            {
                                                "role": "assistant",
                                                "content": "I have a potential fix for the error.",
                                                "tool_calls": tool_calls_from_correction,
                                            }
                                        )
                                        continue  # Continue the loop to execute the corrected solution
                                except (
                                    json.JSONDecodeError,
                                    AttributeError,
                                    Exception,
                                ) as err:
                                    self.logger.warning(
                                        f"Small model did not provide a valid JSON response or error during correction: {err}"
                                    )
                            else:
                                self.logger.warning("Self-correction LLM client not available.")

                            self.logger.info("Escalating to large model for deeper error analysis.")
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
                        return (
                            f"❌ API Error: The model tried to use a tool that doesn't exist.\n\n"
                            f"This usually means:\n"
                            f"1. Your system prompt mentions a tool that isn't defined\n"
                            f"2. There's a mismatch between TOOLS_DEFINITION and tool_functions\n\n"
                            f"Available tools: {', '.join(self.tool_functions.keys())}\n\n"
                            f"Check agent.log for details."
                        )
                    else:
                        return f"❌ API Error: {error_str}\n\nCheck agent.log for details."

                except requests.exceptions.ConnectionError:
                    self.logger.error("Cannot connect to Ollama")
                    # This line uses self.ollama, which is not defined.
                    # It should use self.llm_manager.ollama_url
                    ollama_url = self.llm_models_config.ollama_url  # Use llm_models_config
                    return (
                        "❌ Connection Error: Cannot connect to Ollama.\n\n"
                        "Make sure Ollama is running: 'ollama serve'\n"
                        f"Configured URL: {ollama_url}"
                    )

                except Exception as e:
                    import traceback

                    error_trace = traceback.format_exc()
                    self.logger.error(f"Unexpected error in iteration {iterations}: {e}")
                    self.logger.error(error_trace)
                    return f"❌ Unexpected error: {str(e)}\n\nCheck agent.log for details.\n\n{error_trace if iterations == 1 else ''}"

            self.logger.warning("Max iterations reached")
            return f"⚠️  Reached maximum iterations ({self.max_iterations})"
        finally:
            # F33: Ensure all sessions are closed
            await self.llm_manager.close_all_sessions_async()
            if correlation_id:
                self.kernel.end_interaction_context(correlation_id)

    def chat_mode(self):
        """Interactive chat mode with enhanced UX"""
        print(f"\n{Fore.GREEN}{'=' * 60}")
        print("🤖 DEFAULT AGENT - Enhanced Interactive Mode")
        print(f"{'=' * 60}{Style.RESET_ALL}")
        print(f"📁 Project: {Fore.CYAN}{self.project_root}{Style.RESET_ALL}")
        print(f"📝 Logs: {Fore.CYAN}{self.tool_settings_config.log_file}{Style.RESET_ALL}")  # Use tool_settings_config
        print(f"💡 Commands: {Fore.YELLOW}exit, quit, help{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'=' * 60}{Style.RESET_ALL}\n")

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
                result = asyncio.run(self.chat(q, auto_confirm=self.auto_confirm))  # Pass auto_confirm to chat
                if isinstance(result, dict):
                    print(f"\n{result.get('text', '')}\n")
                    metrics = result.get("metrics", {})
                    print(
                        f"{Fore.CYAN}[Time: {metrics.get('duration_sec')}s | Tokens: {metrics.get('total_tokens')}]{Style.RESET_ALL}"
                    )
                else:
                    print(f"\n{result}\n")

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
        raise NotImplementedError(
            "DefaultAgent is interactive via chat_mode, not meant to be called with run directly."
        )
