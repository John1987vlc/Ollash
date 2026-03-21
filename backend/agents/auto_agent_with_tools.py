"""AutoAgentWithTools — hybrid tool-calling project generator.

Unlike AutoAgent's fixed pipeline, this agent uses two LLMs in tandem:
- Orchestrator (Mistral): handles the tool loop — plans, decides which files to write,
  and provides a spec per file. Reliable tool-call formatting.
- Code generator (Qwen3.5:9b): called internally for each write_project_file() to
  produce the actual file content from the spec. Superior code quality.

Design decisions:
- No CoreAgent/ToolLoopMixin inheritance — thin, purpose-built async loop
- No ConfirmationManager gate — tools are sandboxed to project_root by construction
- Same 5-arg constructor as AutoAgent for DI container compatibility
- async run() — caller must use asyncio.run() when dispatching from a sync thread
- stream_end SSE is pushed by the router, not by this agent (consistent with AutoAgent)
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.utils.domains.auto_generation.tools.project_creation_tools import ProjectCreationTools


class AutoAgentWithTools:
    """Hybrid tool-calling project generator.

    Two LLMs work in tandem:
    - Orchestrator (_ROLE = "tool_agent", Mistral): drives the tool loop, decides which
      files to create and writes a spec per file. Reliable tool-call JSON formatting.
    - Code generator (_CODE_ROLE = "code_generator", Qwen3.5:9b): invoked internally
      on every write_project_file() call to produce the actual source code from the spec.

    Supported tools: plan_project, write_project_file, read_project_file,
    list_project_files, run_linter, run_project_tests, generate_infrastructure,
    finish_project.
    """

    MAX_ITERATIONS: int = 30

    # Orchestrator: Mistral handles tool-call formatting
    _ROLE: str = "tool_agent"
    _LLM_OPTIONS: dict = {"num_predict": -1, "num_ctx": 16384, "think": False}

    # Code generator: Qwen3.5:9b produces file content from spec
    _CODE_ROLE: str = "code_generator"
    _CODE_LLM_OPTIONS: dict = {"num_predict": -1, "num_ctx": 16384, "think": False}

    def __init__(
        self,
        llm_manager: Any,  # IModelProvider / LLMClientManager
        file_manager: Any,  # LockedFileManager (not used directly, kept for DI compat)
        event_publisher: Any,  # EventPublisher
        logger: Any,  # AgentLogger
        generated_projects_dir: Path,
    ) -> None:
        self.llm_manager = llm_manager
        self.file_manager = file_manager
        self.event_publisher = event_publisher
        self.logger = logger
        self.generated_projects_dir = Path(generated_projects_dir)
        self.generated_projects_dir.mkdir(parents=True, exist_ok=True)

        # Resolved during run(); kept as instance attrs for dispatch/unload
        self._client: Any = None
        self._code_client: Any = None

        # Metrics — populated during run()
        self._total_tokens: int = 0
        self._iteration_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        description: str,
        project_name: str,
        project_root: Optional[Path] = None,
        on_blueprint_ready: Optional[Callable[[Dict[str, Any]], bool]] = None,
        max_duration_seconds: Optional[int] = None,
    ) -> Path:
        """Run the tool-calling agent loop. Returns project_root on completion.

        This is an async method — callers in sync contexts must use asyncio.run().

        Args:
            description: Natural-language project description.
            project_name: Unique project name (alphanumeric + dash/underscore).
            project_root: Override project location. Defaults to generated_projects_dir/project_name.
            on_blueprint_ready: Optional callback invoked when plan_project() is called.
                Receives the parsed blueprint dict; return False to abort.
            max_duration_seconds: Soft wall-clock limit for the tool loop. When elapsed time
                exceeds this value the current iteration finishes and the loop exits cleanly.
                None = no limit. Typical values: 300 (easy), 720 (medium), 1500 (hard).
        """
        if project_root is None:
            project_root = self.generated_projects_dir / project_name

        start_time = time.time()
        self._total_tokens = 0
        self._iteration_count = 0

        # Resolve both LLM clients early so we can log model names and unload after the run
        self._client = self._get_client()
        self._code_client = self._get_code_client()
        orchestrator_name = getattr(self._client, "model", self._ROLE)
        code_name = getattr(self._code_client, "model", self._CODE_ROLE)

        limit_str = f"{max_duration_seconds}s" if max_duration_seconds else "unlimited"
        self.logger.info(
            f"[AutoAgentWithTools] Starting '{project_name}' | "
            f"orchestrator: {orchestrator_name} | code: {code_name} | limit: {limit_str}"
        )

        # Instantiate the stateful toolset for this run
        self._tools = ProjectCreationTools(
            project_root=project_root,
            event_publisher=self.event_publisher,
            logger=self.logger,
            on_blueprint_ready=on_blueprint_ready,
            orchestrator_model=orchestrator_name,
            code_model=code_name,
        )

        # Load system prompt
        system_prompt, user_prompt_template = await self._load_prompt()
        user_message = user_prompt_template.format(
            project_name=project_name,
            description=description,
        )

        # Publish run-started event
        await self._publish("phase_start", {"phase": "Initializing tool agent..."})

        # Run the tool loop
        try:
            await self._tool_loop(system_prompt, user_message, start_time, max_duration_seconds)
        except Exception as exc:
            self.logger.error(f"[AutoAgentWithTools] Loop error: {exc}", exc_info=True)
            await self._publish("error_event", {"message": str(exc)})
            raise
        finally:
            # Unload both models from Ollama RAM immediately after the run (free VRAM/RAM).
            # This is especially important in sequential benchmarks to avoid OOM when the
            # next agent loads a different model.
            for client, name in [
                (self._client, orchestrator_name),
                (self._code_client, code_name),
            ]:
                if client is None:
                    continue
                try:
                    client.unload_model()
                    self.logger.info(f"[AutoAgentWithTools] Model '{name}' unloaded from RAM.")
                except Exception as _ue:
                    self.logger.warning(f"[AutoAgentWithTools] unload_model failed for '{name}': {_ue}")
                try:
                    await client.close()
                except Exception:
                    pass

        elapsed = time.time() - start_time
        self.logger.info(
            f"[AutoAgentWithTools] '{project_name}' done | "
            f"orchestrator: {orchestrator_name} | code: {code_name} | "
            f"{self._iteration_count} iterations | "
            f"{self._total_tokens} tokens | "
            f"{elapsed:.1f}s"
        )

        return project_root

    # ------------------------------------------------------------------
    # Core tool loop
    # ------------------------------------------------------------------

    async def _tool_loop(
        self,
        system_prompt: str,
        user_message: str,
        run_start_time: float,
        max_duration_seconds: Optional[int],
    ) -> None:
        """Main async loop: LLM → dispatch tools → observe results → repeat."""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        tool_definitions = ProjectCreationTools.TOOL_DEFINITIONS
        client = self._client  # resolved once in run(), reused across all iterations

        nudge_count = 0  # consecutive text-only responses (resets after any tool call)
        total_nudges = 0  # total nudges in the whole run (catches alternating tool/text patterns)
        last_had_tool_error = False  # True when the previous iteration had a tool that returned ok=False

        for iteration in range(self.MAX_ITERATIONS):
            # ── Soft time limit check (before starting a new LLM call) ──────
            if max_duration_seconds is not None:
                elapsed = time.time() - run_start_time
                if elapsed >= max_duration_seconds:
                    self.logger.warning(
                        f"[AutoAgentWithTools] Time limit reached: {elapsed:.0f}s"
                        f" >= {max_duration_seconds}s — stopping loop cleanly"
                    )
                    await self._publish(
                        "phase_complete",
                        {
                            "phase": "Time limit reached",
                            "elapsed_seconds": round(elapsed, 1),
                            "limit_seconds": max_duration_seconds,
                        },
                    )
                    break
            self._iteration_count = iteration + 1

            try:
                response, usage = await client.stream_chat(
                    messages=messages,
                    tools=tool_definitions,
                    options_override=self._LLM_OPTIONS,
                )
            except Exception as exc:
                self.logger.error(f"[AutoAgentWithTools] LLM call failed at iteration {iteration}: {exc}")
                await self._publish("error_event", {"message": f"LLM error: {exc}"})
                break

            self._total_tokens += usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

            tool_calls: List[Dict[str, Any]] = response.get("tool_calls", [])
            content: str = response.get("content", "") or ""

            # ── Per-iteration diagnostic logging ──────────────────────────────
            if tool_calls:
                names = [tc.get("function", {}).get("name", "?") for tc in tool_calls]
                self.logger.info(f"[AAWT iter={iteration + 1}] tool_calls={names}")
            else:
                self.logger.info(f"[AAWT iter={iteration + 1}] text-only: {content[:120]!r}")

            if not tool_calls:
                # LLM produced text instead of tool calls
                if self._tools.finished:
                    break  # Legitimate: agent finished, providing a summary

                # If the previous iteration had a tool error, give the model one free
                # "thinking" response before counting nudges — it may be recovering.
                if last_had_tool_error:
                    last_had_tool_error = False
                    self.logger.info("[AAWT] Skipping nudge count after tool error — prompting recovery")
                    if content:
                        messages.append({"role": "assistant", "content": content})
                    messages.append(
                        {"role": "user", "content": f"Tool error occurred. Try again.\n{self._tools.state_hint()}"}
                    )
                    continue

                nudge_count += 1
                total_nudges += 1

                self.logger.warning(
                    f"[AutoAgentWithTools] Text-only response "
                    f"(consecutive={nudge_count}, total={total_nudges}, iter={iteration + 1}): "
                    f"{content[:160]!r}"
                )

                # Hard limits: abort if stuck
                if nudge_count >= 3:
                    self.logger.warning("[AutoAgentWithTools] 3 consecutive text-only responses — aborting loop")
                    break
                if total_nudges >= 7:
                    self.logger.warning("[AutoAgentWithTools] 7 total nudges exceeded — aborting loop")
                    break

                # Build a state-aware, escalating nudge message
                state = self._tools.state_hint()
                nudge_msg = _NUDGE_MESSAGES[min(nudge_count - 1, len(_NUDGE_MESSAGES) - 1)].format(state_hint=state)

                if content:
                    messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": nudge_msg})
                continue

            nudge_count = 0  # reset consecutive counter on any tool call
            last_had_tool_error = False  # reset; will be set below if any tool returns ok=False

            # Append assistant message with tool_calls
            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                }
            )

            # Execute each tool call
            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name: str = fn.get("name", "")
                tool_args: Dict[str, Any] = fn.get("arguments", {})
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                await self._publish("tool_code", {"tool_name": tool_name, "tool_args": tool_args})

                result = await self._dispatch_tool_call(tool_name, tool_args)

                # Track whether any tool call returned an error so the next text-only
                # response gets a grace pass instead of counting as a nudge.
                if isinstance(result, dict) and result.get("ok") is False:
                    last_had_tool_error = True
                    self.logger.warning(
                        f"[AAWT iter={iteration + 1}] tool '{tool_name}' error: {result.get('error', '')!r}"
                    )

                await self._publish("tool_output", {"tool_name": tool_name, "output": result})

                # Feed result back in Ollama tool-result format
                messages.append(
                    {
                        "role": "tool",
                        "content": json.dumps({"result": result}),
                    }
                )

                if self._tools._aborted:
                    self.logger.info("[AutoAgentWithTools] Pipeline aborted by on_blueprint_ready callback.")
                    return

                if self._tools.finished:
                    break  # finish_project was called

            if self._tools.finished:
                break

        if not self._tools.finished:
            self.logger.warning(
                f"[AutoAgentWithTools] Loop ended without finish_project() call "
                f"(iterations={self._iteration_count}, finished={self._tools.finished})"
            )

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    async def _dispatch_tool_call(self, name: str, args: Dict[str, Any]) -> Any:
        """Call the named tool method on ProjectCreationTools. Returns serializable result.

        write_project_file is intercepted: the orchestrator (Mistral) provides a `spec`,
        and we call the code generator (Qwen) to produce the actual file content before
        forwarding to ProjectCreationTools.write_project_file(content=...).
        """
        if name == "write_project_file":
            relative_path = args.get("relative_path", "")
            # Accept multiple arg name variations that models sometimes use
            spec = (
                args.get("spec")
                or args.get("content")
                or args.get("code")
                or args.get("file_content")
                or args.get("body")
                or ""
            )
            if not relative_path:
                return {"ok": False, "error": "write_project_file requires 'relative_path'"}
            # If spec is still empty, try to derive from blueprint purpose
            if not spec and self._tools._blueprint:
                planned = {f["path"]: f.get("purpose", "") for f in self._tools._blueprint.get("files", [])}
                derived = planned.get(relative_path, "")
                if derived:
                    spec = f"Implement {relative_path}: {derived}"
                    self.logger.info(f"[AAWT] Derived spec from blueprint for {relative_path!r}")
            if not spec:
                return {
                    "ok": False,
                    "error": "write_project_file requires 'spec' (or 'content'/'code'/'file_content'/'body')",
                }

            await self._publish(
                "phase_start",
                {
                    "phase": f"Generating {relative_path}",
                    "model": getattr(self._code_client, "model", self._CODE_ROLE),
                },
            )
            content = await self._generate_file_content(relative_path, spec)
            return await self._tools.write_project_file(relative_path=relative_path, content=content)

        method = getattr(self._tools, name, None)
        if method is None:
            return {"ok": False, "error": f"Unknown tool: '{name}'"}
        try:
            result = await method(**args)
            return result
        except TypeError as e:
            # Wrong arguments — return descriptive error so LLM can retry
            return {"ok": False, "error": f"Tool call error for '{name}': {e}"}
        except Exception as e:
            self.logger.error(f"[AutoAgentWithTools] Tool '{name}' raised: {e}", exc_info=True)
            return {"ok": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        """Get the orchestrator LLM client (Mistral — tool-call formatting)."""
        try:
            return self.llm_manager.get_client(self._ROLE)
        except Exception:
            self.logger.warning("[AutoAgentWithTools] tool_agent role not found, falling back to generalist")
            return self.llm_manager.get_client("generalist")

    def _get_code_client(self) -> Any:
        """Get the code-generator LLM client (Qwen3.5:9b — file content generation)."""
        try:
            return self.llm_manager.get_client(self._CODE_ROLE)
        except Exception:
            self.logger.warning("[AutoAgentWithTools] code_generator role not found, falling back to coder")
            try:
                return self.llm_manager.get_client("coder")
            except Exception:
                return self._client  # last resort: reuse orchestrator

    async def _generate_file_content(self, relative_path: str, spec: str) -> str:
        """Call Qwen to generate complete file content from a spec.

        Builds context from the current blueprint and already-written files so Qwen
        understands the project structure, then returns the raw file content (fences stripped).
        """
        blueprint = self._tools._blueprint or {}
        project_type = blueprint.get("project_type", "unknown")
        tech_stack = ", ".join(blueprint.get("tech_stack", [])) or "unknown"
        written = list(self._tools._files_written.keys())

        context_lines = [
            f"Project type: {project_type}",
            f"Tech stack: {tech_stack}",
        ]
        if written:
            context_lines.append(f"Files already written: {', '.join(written[:15])}")
        # Include sibling file purposes from the blueprint for extra context
        planned = blueprint.get("files", [])
        sibling_specs = [
            f"  {f['path']}: {f.get('purpose', '')}"
            for f in planned
            if f.get("path") != relative_path and f.get("purpose")
        ]
        if sibling_specs:
            context_lines.append("Other files in project:\n" + "\n".join(sibling_specs[:8]))

        context = "\n".join(context_lines)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a code generator. Generate complete, production-ready code for a single file.\n"
                    "Return ONLY the raw file content — no markdown fences, no explanations, no preamble.\n"
                    "No TODOs or placeholders. Every function must be fully implemented."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    f"File to generate: {relative_path}\n"
                    f"Requirements: {spec}\n\n"
                    f"Generate the complete file content now."
                ),
            },
        ]

        try:
            response, usage = await self._code_client.stream_chat(
                messages=messages,
                tools=None,
                options_override=self._CODE_LLM_OPTIONS,
            )
            self._total_tokens += usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            content = response.get("content", "") or ""
            return _strip_code_fences(content)
        except Exception as exc:
            self.logger.error(
                f"[AutoAgentWithTools] Code generation failed for '{relative_path}': {exc}",
                exc_info=True,
            )
            return f"# Code generation failed: {exc}\n# TODO: implement {relative_path}\n"

    async def _load_prompt(self) -> tuple[str, str]:
        """Load the project_creator prompt from YAML. Returns (system, user_template)."""
        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader

            loader = PromptLoader()
            # load_prompt returns the full YAML dict; the file has a top-level "project_creator" key
            content = await loader.load_prompt("domains/auto_generation/tool_agent_system")
            pair = content.get("project_creator", {}) if content else {}
            if pair:
                return pair.get("system", _DEFAULT_SYSTEM), pair.get("user", _DEFAULT_USER)
        except Exception as e:
            self.logger.warning(f"[AutoAgentWithTools] PromptLoader failed, using inline prompt: {e}")

        return _DEFAULT_SYSTEM, _DEFAULT_USER

    async def _publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish SSE event, swallowing errors."""
        try:
            await self.event_publisher.publish(event_type, data)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Code-fence stripper — Qwen sometimes wraps output in ```lang fences
# ---------------------------------------------------------------------------


def _strip_code_fences(content: str) -> str:
    """Remove outermost markdown code fences if present."""
    content = content.strip()
    m = re.match(r"^```[a-zA-Z0-9_\-]*\n(.*?)```\s*$", content, re.DOTALL)
    if m:
        return m.group(1)
    return content


# ---------------------------------------------------------------------------
# Escalating nudge messages — injected when the model replies with text only.
# {state_hint} is filled in by ProjectCreationTools.state_hint().
# ---------------------------------------------------------------------------

_NUDGE_MESSAGES = [
    # Nudge 1 — gentle, state-aware
    ("You must call a tool. Do not write explanations or plain text.\nCurrent state: {state_hint}\nCall the tool now."),
    # Nudge 2 — stronger
    (
        "STOP. Only tool calls are accepted — not text.\n"
        "Current state: {state_hint}\n"
        "I cannot continue without a tool call. Call the correct tool immediately."
    ),
    # Nudge 3 — final warning before abort
    (
        "FINAL WARNING: I will abort if you do not call a tool right now.\n"
        "Current state: {state_hint}\n"
        "If the project is complete call finish_project(). Otherwise call write_project_file()."
    ),
]


# ---------------------------------------------------------------------------
# Inline fallback prompts (used if YAML loader fails)
# ---------------------------------------------------------------------------

_DEFAULT_SYSTEM = """\
You are a project orchestrator. You plan projects and delegate code generation using tools.
A separate code-generation model writes the actual file contents — you only need to provide specs.

# WORKFLOW
1. PLAN   — Call plan_project() with a JSON blueprint listing all files and their purpose.
2. WRITE  — Call write_project_file(relative_path, spec) for each file.
             spec = 2-4 sentences describing what the file contains, what it exports,
             what libraries it uses, and how it fits the project. Be specific.
             Do NOT write actual code — the code generator handles that.
3. LINT   — After each file, call run_linter(). If errors, call write_project_file again
             with an updated spec that includes the fix instructions.
4. INFRA  — Call generate_infrastructure().
5. TEST   — Call run_project_tests() if relevant.
6. FINISH — Call finish_project(summary). MUST be the last tool call.

# RULES
- Always call a tool. Never respond with plain text.
- Paths are always relative (e.g. "src/main.py").
- blueprint_json must be valid JSON string (no markdown fences).
- Max 30 tool calls total.

# PLAN FORMAT
{"project_type":"api","tech_stack":["python"],"files":[{"path":"main.py","purpose":"entry"}]}
"""

_DEFAULT_USER = """\
Build this project:
Name: {project_name}
Description: {description}

Start with plan_project(). Do not explain. Call the tool now.
"""
