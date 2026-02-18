"""Blueprint for system health monitoring endpoints.

Provides CPU, RAM, disk, and optional GPU metrics for the sidebar dashboard.
"""

import subprocess
from pathlib import Path

from flask import Blueprint, jsonify

system_health_bp = Blueprint("system_health", __name__)

_ollash_root_dir: Path = None


def init_app(app):
    global _ollash_root_dir
    _ollash_root_dir = app.config.get("ollash_root_dir", Path("."))


@system_health_bp.route("/api/system/health")
def system_health():
    """Return CPU, RAM, disk, and optional GPU metrics."""
    result = {
        "cpu_percent": 0.0,
        "ram_total_gb": 0.0,
        "ram_used_gb": 0.0,
        "ram_percent": 0.0,
        "disk_total_gb": 0.0,
        "disk_used_gb": 0.0,
        "disk_percent": 0.0,
        "gpu": None,
    }

    try:
        import psutil

        result["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        result["ram_total_gb"] = round(mem.total / (1024**3), 1)
        result["ram_used_gb"] = round(mem.used / (1024**3), 1)
        result["ram_percent"] = mem.percent
        disk = psutil.disk_usage("/")
        result["disk_total_gb"] = round(disk.total / (1024**3), 1)
        result["disk_used_gb"] = round(disk.used / (1024**3), 1)
        result["disk_percent"] = round(disk.percent, 1)
    except ImportError:
        pass
    except Exception:
        pass

    # Try nvidia-smi for GPU info
    try:
        out = (
            subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                timeout=5,
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        parts = out.split(",")
        if len(parts) >= 3:
            result["gpu"] = {
                "util_percent": float(parts[0].strip()),
                "mem_used_mb": float(parts[1].strip()),
                "mem_total_mb": float(parts[2].strip()),
            }
    except Exception:
        pass

    return jsonify(result)
