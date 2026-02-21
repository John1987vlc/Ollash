"""Blueprint for system health monitoring endpoints.

Provides CPU, RAM, disk, and optional GPU metrics for the sidebar dashboard.
"""

import subprocess
import os
import logging
from pathlib import Path

from flask import Blueprint, jsonify
from backend.core.containers import main_container

logger = logging.getLogger(__name__)

try:
    import psutil
except ImportError:
    psutil = None
    print("WARNING: psutil not found. System metrics (CPU/RAM) will be disabled.")

system_health_bp = Blueprint("system_health", __name__)

_ollash_root_dir: Path = None


def init_app(app):
    global _ollash_root_dir
    _ollash_root_dir = app.config.get("ollash_root_dir", Path("."))


@system_health_bp.route("/api/system/health")
def system_health():
    """Return CPU, RAM, disk, GPU, Rate Limiter, and LLM Latency metrics."""
    global psutil
    result = {
        "status": "ok",
        "cpu_percent": 0.0,
        "ram_total_gb": 0.0,
        "ram_used_gb": 0.0,
        "ram_percent": 0.0,
        "disk_total_gb": 0.0,
        "disk_used_gb": 0.0,
        "disk_percent": 0.0,
        "net_sent_mb": 0.0,
        "net_recv_mb": 0.0,
        "gpu": None,
        "llm_health": {"rate_limiter": {"rpm": 0, "status": "unknown"}, "latency": {"avg_ms": 0, "status": "unknown"}},
    }

    # --- System Metrics (psutil) ---
    if psutil:
        try:
            # CPU
            result["cpu_percent"] = psutil.cpu_percent(interval=None)

            # RAM
            mem = psutil.virtual_memory()
            result["ram_total_gb"] = round(mem.total / (1024**3), 1)
            result["ram_used_gb"] = round(mem.used / (1024**3), 1)
            result["ram_percent"] = mem.percent

            # Disk
            try:
                drive = os.path.splitdrive(os.getcwd())[0] or "C:"
                disk = psutil.disk_usage(drive)
                result["disk_total_gb"] = round(disk.total / (1024**3), 1)
                result["disk_used_gb"] = round(disk.used / (1024**3), 1)
                result["disk_percent"] = round(disk.percent, 1)
            except Exception:
                pass

            # Network
            try:
                net = psutil.net_io_counters()
                result["net_sent_mb"] = round(net.bytes_sent / (1024**2), 2)
                result["net_recv_mb"] = round(net.bytes_recv / (1024**2), 2)
            except Exception:
                pass

        except Exception as e:
            print(f"Error gathering system health: {e}")
    else:
        try:
            import psutil as ps

            psutil = ps
        except ImportError:
            pass

    # --- GPU Metrics (nvidia-smi) ---
    try:
        out = (
            subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                timeout=1,
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

    # --- LLM Health & Rate Limiter Metrics ---
    try:
        llm_manager = main_container.auto_agent_module.llm_client_manager()
        clients = llm_manager.get_all_clients()

        # Aggregate metrics from all active clients
        total_rpm = 0
        latencies = []
        statuses = []

        for client in clients.values():
            if hasattr(client, "_rate_limiter"):
                metrics = client._rate_limiter.get_health_metrics()
                total_rpm = max(total_rpm, metrics.get("effective_rpm", 0))  # Use max to show busiest
                latencies.append(metrics.get("ema_response_time_ms", 0))
                statuses.append(metrics.get("status", "unknown"))

        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        overall_status = "normal"
        if "throttled" in statuses:
            overall_status = "throttled"
        elif "degraded" in statuses:
            overall_status = "degraded"

        result["llm_health"] = {
            "rate_limiter": {"effective_rpm": total_rpm, "status": overall_status},
            "latency": {"avg_ms": round(avg_latency, 1), "status": "high" if avg_latency > 5000 else "normal"},
        }

    except Exception as e:
        logger.warning(f"Failed to gather LLM health metrics: {e}")

    return jsonify(result)
