"""
Integration guide for Phase 6 REST API with Flask application
Shows how to enable Phase 6 endpoints in the web module
"""

# FILE: src/web/__init__.py or src/web/app.py
# Add this import and registration to your existing Flask app initialization:

"""
from flask import Flask
from src.web.blueprints.phase6_bp import phase6_bp

def create_app(config=None):
    app = Flask(__name__)
    
    if config:
        app.config.update(config)
    
    # ... existing blueprint registrations ...
    
    # Register Phase 6 blueprint
    app.register_blueprint(phase6_bp)
    
    return app


# In your main web entry point (e.g., run_web.py):
from src.web import create_app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)

# Phase 6 endpoints will now be available at:
# http://localhost:5000/api/v1/...
"""


# ==================== INTEGRATION CHECKLIST ====================

INTEGRATION_CHECKLIST = {
    "Flask Setup": [
        "✓ Import phase6_bp from src/web/blueprints/phase6_bp.py",
        "✓ Register blueprint with app: app.register_blueprint(phase6_bp)",
        "✓ Ensure Flask app is running with '/api/v1' prefix"
    ],
    "Environment Configuration": [
        "✓ Set WEBHOOK_SLACK_URL in .env",
        "✓ Set WEBHOOK_DISCORD_URL in .env",
        "✓ Set WEBHOOK_TEAMS_URL in .env",
        "✓ Ensure Ollama server is accessible"
    ],
    "Database/File Storage": [
        "✓ Ensure project root is writable (for decision_memory, feedback storage)",
        "✓ Create logs directory if not exists",
        "✓ Initialize database connections if using persistent storage"
    ],
    "Testing": [
        "✓ Run unit tests: pytest tests/unit/test_phase6_*.py -v",
        "✓ Run integration tests: pytest tests/integration/test_phase6_integration.py -v",
        "✓ Test endpoints: curl http://localhost:5000/api/v1/health"
    ],
    "Frontend": [
        "✓ Integrate voice widget JavaScript",
        "✓ Setup artifact injection script",
        "✓ Add feedback submission form"
    ]
}


# ==================== QUICK START ====================

def example_flask_integration():
    """
    Example of integrating Phase 6 into existing Flask app
    """
    
    from flask import Flask
    from src.web.blueprints.phase6_bp import phase6_bp
    
    # Create Flask app
    app = Flask(__name__)
    
    # Register Phase 6 blueprint
    app.register_blueprint(phase6_bp)
    
    # Test connectivity
    with app.test_client() as client:
        response = client.get('/api/v1/health')
        assert response.status_code == 200
        print("✓ Phase 6 API is ready!")
    
    return app


# ==================== ENDPOINT SUMMARY ====================

ENDPOINTS = {
    "Notification UI": {
        "GET /api/v1/notifications/artifacts": "List all active artifacts",
        "POST /api/v1/notifications/artifacts": "Create new notification artifact",
        "POST /api/v1/notifications/clear": "Clear old artifacts"
    },
    "Webhooks": {
        "GET /api/v1/webhooks": "List registered webhooks and status",
        "POST /api/v1/webhooks": "Register new webhook",
        "POST /api/v1/webhooks/<name>/send": "Send message via webhook",
        "GET /api/v1/webhooks/<name>/health": "Check webhook health"
    },
    "Reports": {
        "GET /api/v1/reports/daily": "Get today's activity report",
        "GET /api/v1/reports/trends": "Get performance trend report",
        "GET /api/v1/reports/anomalies": "Get anomaly detection report"
    },
    "Voice Commands": {
        "POST /api/v1/voice/process": "Process voice transcription",
        "GET /api/v1/voice/commands": "Get voice command history",
        "GET /api/v1/voice/stats": "Get voice command statistics"
    },
    "Decision Memory": {
        "GET /api/v1/decisions": "Get decision analytics",
        "POST /api/v1/decisions": "Record new decision",
        "POST /api/v1/decisions/<id>/outcome": "Record decision outcome",
        "POST /api/v1/decisions/suggestions": "Get decision suggestions"
    },
    "Feedback": {
        "POST /api/v1/feedback": "Submit feedback",
        "GET /api/v1/feedback/profile": "Get learned style profile",
        "GET /api/v1/feedback/trends": "Get feedback trends"
    },
    "Advanced Triggers": {
        "GET /api/v1/triggers": "List all triggers",
        "POST /api/v1/triggers": "Register new trigger",
        "POST /api/v1/triggers/<id>/evaluate": "Evaluate trigger",
        "POST /api/v1/triggers/<id>/fire": "Fire trigger manually",
        "GET /api/v1/triggers/conflicts": "Detect conflicts"
    },
    "Utilities": {
        "GET /api/v1/health": "Health check",
        "POST /api/v1/batch": "Execute batch operations",
        "GET /api/v1/export/decisions": "Export decisions",
        "GET /api/v1/export/feedback": "Export feedback"
    }
}


# ==================== EXAMPLE REQUESTS ====================

EXAMPLE_REQUESTS = {
    "Send Notification": {
        "method": "POST",
        "url": "/api/v1/notifications/artifacts",
        "body": {
            "type": "system_status",
            "metrics": {"cpu": 85, "memory": 72},
            "thresholds": {"cpu": 80, "memory": 70}
        }
    },
    
    "Register Slack Webhook": {
        "method": "POST",
        "url": "/api/v1/webhooks",
        "body": {
            "name": "prod_alerts",
            "type": "SLACK",
            "url": "https://hooks.slack.com/services/YOUR/HOOK/URL"
        }
    },
    
    "Send Webhook Message": {
        "method": "POST",
        "url": "/api/v1/webhooks/prod_alerts/send",
        "body": {
            "title": "High CPU Alert",
            "message": "CPU usage exceeded threshold",
            "priority": "HIGH",
            "fields": {"cpu": "92%", "timestamp": "2024-01-01T12:00:00"}
        }
    },
    
    "Process Voice Command": {
        "method": "POST",
        "url": "/api/v1/voice/process",
        "body": {
            "text": "create task for user onboarding",
            "confidence": 92.5,
            "language": "en"
        }
    },
    
    "Record Decision": {
        "method": "POST",
        "url": "/api/v1/decisions",
        "body": {
            "id": "dec_001",
            "domain": "ARCHITECTURE",
            "text": "Use microservices architecture",
            "reasoning": "Better scalability",
            "option": "microservices",
            "alternatives": ["monolith", "serverless"]
        }
    },
    
    "Submit Feedback": {
        "method": "POST",
        "url": "/api/v1/feedback",
        "body": {
            "content_id": "content_001",
            "excerpt": "Long detailed explanation...",
            "type": "TOO_VERBOSE",
            "feedback": "Be more concise",
            "severity": "moderate"
        }
    },
    
    "Register Composite Trigger": {
        "method": "POST",
        "url": "/api/v1/triggers",
        "body": {
            "id": "trigger_high_cpu",
            "name": "High CPU Alert",
            "operator": "AND",
            "conditions": [
                {"metric": "cpu", "operator": ">", "value": 85},
                {"metric": "memory", "operator": ">", "value": 80}
            ],
            "cooldown": 60
        }
    },
    
    "Evaluate Trigger": {
        "method": "POST",
        "url": "/api/v1/triggers/trigger_high_cpu/evaluate",
        "body": {
            "context": {
                "cpu": 92,
                "memory": 88
            }
        }
    }
}


# ==================== PYTHON CLIENT EXAMPLES ====================

def python_client_examples():
    """
    Examples of using Phase 6 API from Python
    """
    
    import requests
    import json
    
    BASE_URL = "http://localhost:5000/api/v1"
    
    # Example 1: Health check
    response = requests.get(f"{BASE_URL}/health")
    print(f"Health: {response.json()}")
    
    # Example 2: Register webhook
    response = requests.post(f"{BASE_URL}/webhooks", json={
        "name": "my_slack",
        "type": "SLACK",
        "url": "https://hooks.slack.com/..."
    })
    print(f"Webhook registered: {response.json()}")
    
    # Example 3: Send message
    response = requests.post(f"{BASE_URL}/webhooks/my_slack/send", json={
        "title": "Alert",
        "message": "System status update",
        "priority": "MEDIUM"
    })
    print(f"Message sent: {response.json()}")
    
    # Example 4: Process voice command
    response = requests.post(f"{BASE_URL}/voice/process", json={
        "text": "create task for testing",
        "confidence": 95.0
    })
    print(f"Voice command result: {response.json()}")
    
    # Example 5: Submit feedback
    response = requests.post(f"{BASE_URL}/feedback", json={
        "content_id": "content_1",
        "excerpt": "Sample content",
        "type": "TOO_VERBOSE",
        "feedback": "Be more concise",
        "severity": "minor"
    })
    print(f"Feedback submitted: {response.json()}")
    
    # Example 6: Get style profile
    response = requests.get(f"{BASE_URL}/feedback/profile")
    print(f"Style profile: {response.json()}")
    
    # Example 7: Batch operations
    response = requests.post(f"{BASE_URL}/batch", json={
        "operations": [
            {
                "type": "send_notification",
                "data": {
                    "webhook": "my_slack",
                    "message": "Batch message 1"
                }
            },
            {
                "type": "record_feedback",
                "data": {
                    "content_id": "batch_content",
                    "excerpt": "Content",
                    "type": "TOO_TECHNICAL",
                    "text": "Simplify this"
                }
            }
        ]
    })
    print(f"Batch result: {response.json()}")


# ==================== CURL EXAMPLES ====================

CURL_EXAMPLES = """
# Health check
curl http://localhost:5000/api/v1/health

# List webhooks
curl http://localhost:5000/api/v1/webhooks

# Register webhook
curl -X POST http://localhost:5000/api/v1/webhooks \\
  -H "Content-Type: application/json" \\
  -d '{"name":"slack","type":"SLACK","url":"https://..."}'

# Get daily report (as JSON)
curl "http://localhost:5000/api/v1/reports/daily?format=json"

# Get daily report (as Markdown)
curl "http://localhost:5000/api/v1/reports/daily?format=markdown"

# Process voice command
curl -X POST http://localhost:5000/api/v1/voice/process \\
  -H "Content-Type: application/json" \\
  -d '{"text":"create task","confidence":90.0}'

# Get voice history
curl "http://localhost:5000/api/v1/voice/commands?limit=10"

# Record decision
curl -X POST http://localhost:5000/api/v1/decisions \\
  -H "Content-Type: application/json" \\
  -d '{
    "id":"dec_001",
    "domain":"ARCHITECTURE",
    "text":"Use caching",
    "reasoning":"Performance",
    "option":"redis"
  }'

# Get decision analytics
curl http://localhost:5000/api/v1/decisions

# Submit feedback
curl -X POST http://localhost:5000/api/v1/feedback \\
  -H "Content-Type: application/json" \\
  -d '{
    "content_id":"content_1",
    "excerpt":"Sample",
    "type":"TOO_VERBOSE",
    "feedback":"Be concise"
  }'

# Get style profile
curl http://localhost:5000/api/v1/feedback/profile

# Register trigger
curl -X POST http://localhost:5000/api/v1/triggers \\
  -H "Content-Type: application/json" \\
  -d '{
    "id":"cpu_alert",
    "name":"High CPU",
    "operator":"AND",
    "conditions":[{"metric":"cpu","operator":">","value":85}]
  }'

# Evaluate trigger
curl -X POST http://localhost:5000/api/v1/triggers/cpu_alert/evaluate \\
  -H "Content-Type: application/json" \\
  -d '{"context":{"cpu":92}}'

# Export decisions
curl http://localhost:5000/api/v1/export/decisions > decisions.json

# Export feedback
curl http://localhost:5000/api/v1/export/feedback > feedback.json
"""


if __name__ == "__main__":
    print("Phase 6 Integration Guide")
    print("=" * 80)
    print("\nIntegration Checklist:")
    for section, items in INTEGRATION_CHECKLIST.items():
        print(f"\n{section}:")
        for item in items:
            print(f"  {item}")
    
    print("\n\nEndpoints Summary:")
    for category, endpoints in ENDPOINTS.items():
        print(f"\n{category}:")
        for endpoint, description in endpoints.items():
            print(f"  {endpoint}: {description}")
