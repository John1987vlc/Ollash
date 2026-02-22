from flask import Blueprint, render_template, jsonify, request
import uuid
from datetime import datetime, timedelta

# Mocking backend imports if they don't exist yet for the UI demo
try:
    from backend.utils.core.system.task_scheduler import TaskScheduler
    from backend.utils.core.system.execution_plan import ExecutionPlan
except ImportError:
    class TaskScheduler:
        def get_jobs(self): return []
        def add_job(self, *args): pass
        def remove_job(self, *args): pass
    class ExecutionPlan:
        def generate_preview(self, task): return {}

bp = Blueprint('operations', __name__, url_prefix='/operations')

# In-memory mock storage for demonstration
scheduler_jobs = [
    {"id": "job_1", "name": "Daily System Backup", "cron": "0 0 * * *", "next_run": "2026-02-23T00:00:00", "status": "active"},
    {"id": "job_2", "name": "Weekly Model Retraining", "cron": "0 2 * * 0", "next_run": "2026-03-01T02:00:00", "status": "paused"}
]

@bp.route('/')
def operations_dashboard():
    return render_template('pages/operations.html')

@bp.route('/api/jobs', methods=['GET', 'POST'])
def handle_jobs():
    if request.method == 'POST':
        data = request.json
        new_job = {
            "id": f"job_{uuid.uuid4().hex[:8]}",
            "name": data.get('name', 'Untitled Task'),
            "cron": data.get('cron', '* * * * *'),
            "next_run": (datetime.now() + timedelta(days=1)).isoformat(),
            "status": "active"
        }
        scheduler_jobs.append(new_job)
        return jsonify(new_job)
    return jsonify(scheduler_jobs)

@bp.route('/api/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    global scheduler_jobs
    scheduler_jobs = [job for job in scheduler_jobs if job['id'] != job_id]
    return jsonify({"status": "success"})

@bp.route('/api/dag/preview', methods=['POST'])
def preview_dag():
    """Generates a visual execution plan (DAG) for a complex task."""
    task_description = request.json.get('task')
    
    # Mock DAG generation
    dag = {
        "nodes": [
            {"id": "1", "label": "Analyze Requirements", "type": "thinking"},
            {"id": "2", "label": "Search Codebase", "type": "tool"},
            {"id": "3", "label": "Plan Architecture", "type": "thinking"},
            {"id": "4", "label": "Write Code", "type": "action"},
            {"id": "5", "label": "Run Tests", "type": "validation"}
        ],
        "edges": [
            {"from": "1", "to": "2"},
            {"from": "2", "to": "3"},
            {"from": "3", "to": "4"},
            {"from": "4", "to": "5"}
        ]
    }
    return jsonify(dag)
