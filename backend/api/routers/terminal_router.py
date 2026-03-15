"""
Terminal router — migrated from frontend/blueprints/terminal_views.py.

Provides a bidirectional terminal connection using FastAPI WebSockets,
streaming command output to the xterm.js frontend.
"""

import asyncio
import logging
import os
import shlex
import subprocess

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/terminal", tags=["terminal"])

logger = logging.getLogger(__name__)

_MAX_OUTPUT_SIZE = 50_000  # 50 KB per command
_COMMAND_TIMEOUT = 120  # seconds


def _get_allowed_dirs(app_state) -> set[str]:
    """Return the set of directories from which commands may run."""
    dirs = {os.getcwd()}
    generated_dir = getattr(app_state, "generated_projects_dir", None)
    if generated_dir:
        dirs.add(os.path.abspath(str(generated_dir)))
    return dirs


@router.websocket("/ws")
async def terminal_ws(websocket: WebSocket):
    """Bidirectional terminal WebSocket handler."""
    await websocket.accept()
    logger.info("Terminal WebSocket connection opened")

    allowed_dirs = _get_allowed_dirs(websocket.app.state)
    working_dir = os.getcwd()

    try:
        while True:
            try:
                message = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            message = message.strip()
            if not message:
                continue

            # Handle cd command (no subprocess needed)
            if message.startswith("cd "):
                target = message[3:].strip()
                new_dir = os.path.abspath(os.path.join(working_dir, target))
                # Guard: only allow navigation within the workspace (allowed_dirs subtree).
                if os.path.isdir(new_dir) and any(
                    new_dir == d or new_dir.startswith(d + os.sep) for d in allowed_dirs
                ):
                    working_dir = new_dir
                    await websocket.send_text(f"\r\n$ cd {target}\r\n")
                elif not os.path.isdir(new_dir):
                    await websocket.send_text(f"\r\nDirectory not found: {target}\r\n")
                else:
                    await websocket.send_text("\r\nAccess denied: outside workspace\r\n")
                continue

            logger.info("TERM_EXEC cwd=%s cmd=%.200s", working_dir, message)
            await websocket.send_text(f"\r\n$ {message}\r\n")

            try:
                output = await asyncio.to_thread(_run_command, message, working_dir, allowed_dirs)
                await websocket.send_text(output)
            except Exception as exc:
                await websocket.send_text(f"\r\nError: {exc}\r\n")

    except Exception as exc:
        logger.debug("Terminal WebSocket closed: %s", exc)
    finally:
        logger.info("Terminal WebSocket connection closed")


def _run_command(message: str, working_dir: str, allowed_dirs: set[str]) -> str:
    """Execute a shell command synchronously and return its output as a string.

    Runs in a thread pool via asyncio.to_thread to avoid blocking the event loop.
    """
    output_parts: list[str] = []
    output_size = 0

    try:
        process = subprocess.Popen(
            shlex.split(message) if os.name != "nt" else message,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=working_dir,
            text=True,
            shell=os.name == "nt",
            bufsize=1,
        )

        for line in iter(process.stdout.readline, ""):
            if output_size > _MAX_OUTPUT_SIZE:
                output_parts.append("\r\n[Output truncated]\r\n")
                process.kill()
                break
            output_parts.append(line.replace("\n", "\r\n"))
            output_size += len(line)

        process.wait(timeout=_COMMAND_TIMEOUT)

        if process.returncode != 0:
            output_parts.append(f"\r\n[Exit code: {process.returncode}]\r\n")

    except subprocess.TimeoutExpired:
        process.kill()
        output_parts.append("\r\n[Command timed out after 120s]\r\n")
    except FileNotFoundError:
        cmd_name = message.split()[0] if message.split() else message
        output_parts.append(f"\r\nCommand not found: {cmd_name}\r\n")

    return "".join(output_parts)
