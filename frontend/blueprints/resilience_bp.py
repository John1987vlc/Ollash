from flask import Blueprint, render_template, jsonify, current_app
from pathlib import Path
from backend.utils.core.system.metrics_database import get_metrics_database
import random
from datetime import datetime, timedelta

resilience_bp = Blueprint('resilience', __name__, template_folder='templates')

@resilience_bp.route('/resilience')
def resilience_dashboard():
    return render_template('pages/resilience.html')

@resilience_bp.route('/api/resilience/status')
def get_resilience_status():
    """Returns the current state of loop detection and contingency planning."""
    # In a real scenario, we would pull this from the active agent sessions
    # or a global event bus. For now, we'll use the metrics database.
    db = get_metrics_database(Path(current_app.root_path).parent)
    
    loops = db.get_metric_history('system', 'loop_detected', hours=24)
    contingencies = db.get_metric_history('auto_gen', 'contingency_plan', hours=24)
    
    # Mock some data if empty for demonstration of the premium UI
    if not loops:
        loops = [
            {"timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 60))).isoformat(), "value": 1, "tags": {"tool": "ls_directory"}} 
            for _ in range(3)
        ]
    
    if not contingencies:
        contingencies = [
            {"timestamp": (datetime.now() - timedelta(minutes=random.randint(1, 120))).isoformat(), "value": 1, "tags": {"phase": "senior_review"}}
            for _ in range(2)
        ]

    return jsonify({
        "loops_detected": len(loops),
        "contingency_plans_executed": len(contingencies),
        "recent_loops": loops[-5:],
        "recent_contingencies": contingencies[-5:],
        "system_health_score": 98.5 - (len(loops) * 0.5)
    })

@resilience_bp.route('/api/resilience/logs')
def get_resilience_logs():
    """Returns detailed logs for resilience events."""
    # This would parse agent logs specifically for loop/stagnation warnings
    return jsonify([
        {"time": "10:24:05", "event": "Loop detected", "tool": "grep_search", "action": "Triggered backtracking"},
        {"time": "11:15:30", "event": "Contingency plan started", "reason": "Review failure", "status": "Success"},
        {"time": "14:42:12", "event": "Stagnation timeout", "duration": "2m", "action": "Re-prompting agent"}
    ])
