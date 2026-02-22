from flask import Blueprint, jsonify
import random
import time

system_health_bp = Blueprint('system_health', __name__, url_prefix='/api/health')

@system_health_bp.route('/')
def get_system_health():
    """Detailed health check including GPU and Model Latency."""
    # Mocking data from backend.utils.core.system.gpu_aware_rate_limiter
    # and backend.utils.core.llm.model_health_monitor
    
    return jsonify({
        "status": "ok",
        "cpu": random.randint(10, 40),
        "ram": random.randint(30, 60),
        "disk": 45,
        "gpu": {
            "load": random.randint(0, 80),
            "memory_used": 4096,
            "memory_total": 8192,
            "temperature": random.randint(40, 75)
        },
        "llm": {
            "current_model": "qwen2.5-coder:14b",
            "latency_ms": random.randint(50, 200),
            "requests_per_minute": random.randint(0, 15),
            "queue_depth": random.randint(0, 2),
            "status": "healthy" if random.random() > 0.1 else "degraded"
        },
        "models": [
            {"name": "qwen2.5-coder:14b", "status": "online", "latency": 120, "fallback": "qwen2.5-coder:7b"},
            {"name": "llama3:8b", "status": "online", "latency": 85, "fallback": None},
            {"name": "mistral:7b", "status": "offline", "latency": 0, "fallback": "llama3:8b"}
        ]
    })

def init_app(app):
    pass
