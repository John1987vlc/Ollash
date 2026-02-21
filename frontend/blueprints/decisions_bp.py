from flask import Blueprint, jsonify, request
from backend.core.containers import main_container
from backend.utils.core.episodic_memory import DecisionRecord

decisions_bp = Blueprint("decisions", __name__)

@decisions_bp.route("/api/decisions", methods=["GET"])
def get_decisions():
    """Returns the latest logical decisions made by agents."""
    limit = request.args.get("limit", 20, type=int)
    root = main_container.core.ollash_root_dir()
    from backend.utils.core.episodic_memory import EpisodicMemory
    from backend.utils.core.agent_logger import AgentLogger
    from backend.utils.core.structured_logger import StructuredLogger
    
    sl = StructuredLogger(root / "logs" / "decisions.log")
    memory = EpisodicMemory(root / ".ollash", AgentLogger(sl, "decisions_api"))
    
    decisions = memory.recall_decisions(max_results=limit)
    return jsonify({"decisions": [d.to_dict() for d in decisions]})

@decisions_bp.route("/api/decisions/session/<session_id>", methods=["GET"])
def get_session_decisions(session_id):
    """Returns decisions for a specific chat session."""
    root = main_container.core.ollash_root_dir()
    from backend.utils.core.episodic_memory import EpisodicMemory
    from backend.utils.core.agent_logger import AgentLogger
    from backend.utils.core.structured_logger import StructuredLogger
    
    sl = StructuredLogger(root / "logs" / "decisions.log")
    memory = EpisodicMemory(root / ".ollash", AgentLogger(sl, "decisions_api"))
    
    # Simple query for session
    import sqlite3
    with sqlite3.connect(str(memory._db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM decisions WHERE session_id = ? ORDER BY timestamp ASC", (session_id,)).fetchall()
        
    return jsonify({"decisions": [dict(r) for r in rows]})
