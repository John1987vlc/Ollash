"""Blueprint for integrated web terminal (WebSocket-based).

Provides a bidirectional terminal connection using flask-sock,
streaming command output to the xterm.js frontend.
"""

import logging
import os
import shlex
import subprocess

from flask import Blueprint

logger = logging.getLogger(__name__)

bp = Blueprint("terminal_bp", __name__)

_allowed_working_dirs = set()
_max_output_size = 50000  # 50KB per command


def init_app(app):
    """Initialize terminal blueprint with allowed working directories."""
    global _allowed_working_dirs
    project_dir = app.config.get("GENERATED_PROJECTS_DIR", "")
    if project_dir:
        _allowed_working_dirs.add(os.path.abspath(project_dir))
    _allowed_working_dirs.add(os.getcwd())
    logger.info("Terminal blueprint initialized")


try:
    from flask_sock import Sock

    _sock_available = True
except ImportError:
    _sock_available = False
    logger.info("flask-sock not installed. Terminal WebSocket disabled.")


def register_websocket(app):
    """Register WebSocket routes. Call after app creation."""
    if not _sock_available:
        return

    sock = Sock(app)

    @sock.route("/ws/terminal")
    def terminal_ws(ws):
        """Bidirectional terminal WebSocket handler."""
        logger.info("Terminal WebSocket connection opened")
        working_dir = os.getcwd()

        try:
            while True:
                message = ws.receive()
                if message is None:
                    break

                message = message.strip()
                if not message:
                    continue

                # Handle special commands
                if message.startswith("cd "):
                    target = message[3:].strip()
                    new_dir = os.path.abspath(os.path.join(working_dir, target))
                    if os.path.isdir(new_dir):
                        working_dir = new_dir
                        ws.send(f"\r\n$ cd {target}\r\n")
                    else:
                        ws.send(f"\r\nDirectory not found: {target}\r\n")
                    continue

                # Execute command
                ws.send(f"\r\n$ {message}\r\n")

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

                    output_size = 0
                    for line in iter(process.stdout.readline, ""):
                        if output_size > _max_output_size:
                            ws.send("\r\n[Output truncated]\r\n")
                            process.kill()
                            break
                        ws.send(line.replace("\n", "\r\n"))
                        output_size += len(line)

                    process.wait(timeout=120)

                    if process.returncode != 0:
                        ws.send(f"\r\n[Exit code: {process.returncode}]\r\n")

                except subprocess.TimeoutExpired:
                    process.kill()
                    ws.send("\r\n[Command timed out after 120s]\r\n")
                except FileNotFoundError:
                    ws.send(f"\r\nCommand not found: {message.split()[0]}\r\n")
                except Exception as e:
                    ws.send(f"\r\nError: {e}\r\n")

        except Exception as e:
            logger.debug(f"Terminal WebSocket closed: {e}")
        finally:
            logger.info("Terminal WebSocket connection closed")
