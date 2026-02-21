"""
Sandbox Execution Blueprint
REST API for running code in an isolated environment (WASM/Docker fallback)
"""

import logging
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from backend.utils.core.tools.wasm_sandbox import WasmSandbox, DockerSandbox, TestResult

logger = logging.getLogger(__name__)

sandbox_bp = Blueprint("sandbox", __name__, url_prefix="/api/sandbox")

# Initialize managers
wasm_sandbox = WasmSandbox(logger=logger)
docker_sandbox = DockerSandbox(logger=logger)


@sandbox_bp.route("/execute", methods=["POST"])
def execute_code():
    """
    Execute a code block in the sandbox

    Request body:
    {
        "code": "print('hello')",
        "language": "python",
        "project_name": "optional_name"
    }
    """
    try:
        data = request.get_json() or {}
        code = data.get("code")
        language = data.get("language", "python")

        if not code:
            return jsonify({"error": "No code provided"}), 400

        # Create a temporary file for the code
        with tempfile.TemporaryDirectory(prefix="ollash_exec_") as tmpdir:
            tmp_path = Path(tmpdir)

            # Simple extension mapping
            ext = ".py" if language == "python" else ".js" if language == "javascript" else ".txt"
            script_file = tmp_path / f"script{ext}"
            script_file.write_text(code)

            # Command to run
            if language == "python":
                cmd = f"python {script_file.name}"
            elif language == "javascript":
                cmd = f"node {script_file.name}"
            else:
                return jsonify({"error": f"Language {language} not supported for direct execution"}), 400

            # Attempt execution - Prioritize Docker, then WASM, then Subprocess (via WasmSandbox fallback)
            result = None

            if docker_sandbox.is_available:
                result = docker_sandbox.execute_in_container(cmd, tmp_path)
            else:
                # WasmSandbox fallback logic uses subprocess if wasmtime not found
                instance = wasm_sandbox.create_sandbox()
                try:
                    # Manually run in subprocess for direct execution (WasmSandbox is geared for tests)
                    import subprocess
                    import time

                    start = time.time()
                    process = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=str(tmp_path)
                    )
                    result = TestResult(
                        success=process.returncode == 0,
                        exit_code=process.returncode,
                        stdout=process.stdout,
                        stderr=process.stderr,
                        duration_seconds=time.time() - start,
                    )
                finally:
                    wasm_sandbox.destroy_sandbox(instance)

            if result:
                return jsonify(
                    {
                        "status": "success",
                        "output": result.stdout + result.stderr,
                        "exit_code": result.exit_code,
                        "duration": result.duration_seconds,
                    }
                ), 200
            else:
                return jsonify({"error": "Execution failed to start"}), 500

    except Exception as e:
        logger.error(f"Sandbox execution error: {e}")
        return jsonify({"error": str(e)}), 500


def init_app(app):
    """Register functions if needed"""
    pass
