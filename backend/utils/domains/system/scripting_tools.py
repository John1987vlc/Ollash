from typing import Dict, Any, Optional
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.tools.tool_decorator import ollash_tool
from backend.utils.core.tools.scripting_sandbox import ScriptingSandbox


class ScriptingTools:
    """
    Tools for creating, testing, and verifying scripts in an isolated environment.
    Supports Bash and PowerShell.
    """

    def __init__(self, logger: AgentLogger):
        self.logger = logger
        self.sandbox = ScriptingSandbox(logger=logger)
        # Sandbox is lazy-initialized on first use

    @ollash_tool(
        name="init_scripting_environment",
        description="Initializes a clean, isolated environment (sandbox) for script development.",
        parameters={"type": "object", "properties": {}},
        toolset_id="scripting_tools",
        agent_types=["system"],
    )
    def init_environment(self) -> Dict[str, Any]:
        """Starts the sandbox environment."""
        try:
            self.sandbox.start()
            return {"ok": True, "message": "Scripting sandbox initialized successfully."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="write_script",
        description="Writes content to a script file in the sandbox.",
        parameters={
            "filename": {"type": "string", "description": "Name of the file (e.g., test.ps1, script.sh)"},
            "content": {"type": "string", "description": "The content of the script."},
        },
        toolset_id="scripting_tools",
        agent_types=["system"],
        required=["filename", "content"],
    )
    def write_script(self, filename: str, content: str) -> Dict[str, Any]:
        try:
            if not self.sandbox._is_active:
                self.sandbox.start()

            self.sandbox.write_file(filename, content)

            # Auto-chmod for shell scripts
            if filename.endswith(".sh"):
                self.sandbox.execute_command(["chmod", "+x", filename])

            return {"ok": True, "message": f"File '{filename}' written successfully."}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="execute_script",
        description="Executes a script in the sandbox and returns the output.",
        parameters={
            "filename": {"type": "string", "description": "The file to execute."},
            "args": {"type": "array", "items": {"type": "string"}, "description": "Arguments for the script."},
        },
        toolset_id="scripting_tools",
        agent_types=["system"],
        required=["filename"],
    )
    def execute_script(self, filename: str, args: Optional[list] = None) -> Dict[str, Any]:
        try:
            if not self.sandbox._is_active:
                return {"ok": False, "error": "Sandbox not initialized. Write a script first."}

            args = args or []
            cmd = []

            if filename.endswith(".ps1"):
                cmd = ["pwsh", "-File", filename] + args
            elif filename.endswith(".sh"):
                cmd = ["./" + filename] + args
            else:
                # Fallback execution
                cmd = ["sh", filename] + args if not filename.startswith("./") else [filename] + args

            result = self.sandbox.execute_command(cmd)
            return {"ok": True, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @ollash_tool(
        name="cleanup_environment",
        description="Destroys the sandbox environment and all files within it.",
        parameters={"type": "object", "properties": {}},
        toolset_id="scripting_tools",
        agent_types=["system"],
    )
    def cleanup_environment(self) -> Dict[str, Any]:
        try:
            self.sandbox.stop()
            return {"ok": True, "message": "Sandbox destroyed."}
        except Exception as e:
            return {"ok": False, "error": str(e)}
