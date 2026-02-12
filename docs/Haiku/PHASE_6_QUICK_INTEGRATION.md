# PHASE 6: QUICK INTEGRATION GUIDE

Quick reference for integrating Phase 6 components into existing Ollash

---

## 🚀 GETTING STARTED

### 1. Import Components

```python
from src.utils.core.adaptive_notification_ui import get_adaptive_notification_ui
from src.utils.core.webhook_manager import get_webhook_manager, WebhookType, MessagePriority
from src.utils.core.activity_report_generator import get_activity_report_generator
from src.utils.core.voice_command_processor import get_voice_command_processor, CommandType
from src.utils.core.memory_of_decisions import MemoryOfDecisions, DecisionDomain, DecisionOutcome
from src.utils.core.feedback_cycle_manager import get_feedback_cycle_manager, FeedbackType
from src.utils.core.advanced_trigger_manager import get_advanced_trigger_manager, LogicOperator
```

---

## 📦 COMPONENT INITIALIZATION

```python
# All components use singleton pattern - just call get_* function
notification_ui = get_adaptive_notification_ui()
webhook_mgr = get_webhook_manager()
report_gen = get_activity_report_generator()
voice_proc = get_voice_command_processor()
memory = MemoryOfDecisions(Path.cwd())  # Requires project root
feedback_mgr = get_feedback_cycle_manager(Path.cwd())
trigger_mgr = get_advanced_trigger_manager()
```

---

## 🔌 ENVIRONMENT CONFIGURATION

Add to `.env` file:

```dotenv
# Webhook URLs
WEBHOOK_SLACK_URL=https://hooks.slack.com/services/YOUR/HOOK/URL
WEBHOOK_DISCORD_URL=https://discord.com/api/webhooks/YOUR/WEBHOOK/URL
WEBHOOK_TEAMS_URL=https://outlook.webhook.office.com/webhookb2/YOUR/URL

# Existing SMTP (already in .env)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFICATION_FROM_EMAIL=notifications@ollash.ai
```

---

## 🔗 INTEGRATION POINTS

### A. With DefaultAgent (CLI)

```python
# File: src/agents/default_agent.py

class DefaultAgent:
    def __init__(self):
        # ... existing init code ...
        self.notification_ui = get_adaptive_notification_ui()
        self.webhook_mgr = get_webhook_manager()
        self.memory = MemoryOfDecisions(self.project_root)
    
    def on_task_complete(self, task_name, result):
        """Called when a task completes"""
        # Existing: send email notification
        self.notification_manager.send_task_completion(...)
        
        # NEW: Send to webhooks
        self.webhook_mgr.send_to_webhook_sync(
            webhook_name="default_slack",
            message=f"Task completed: {task_name}",
            title="✅ Task Notification",
            priority=MessagePriority.MEDIUM,
            fields={"Result": result[:100]}
        )
        
        # NEW: Record decision
        self.memory.record_decision(
            decision_id=f"task_{task_name}_{datetime.now().timestamp()}",
            domain=DecisionDomain.TROUBLESHOOTING,
            decision_text=f"Completed task: {task_name}",
            reasoning="User initiated",
            context={"task": task_name},
            chosen_option="execute_task"
        )
```

### B. With AutomationManager

```python
# File: src/core/automation_manager.py

class AutomationManager:
    def __init__(self):
        # ... existing init ...
        self.advanced_triggers = get_advanced_trigger_manager()
        self.notification_ui = get_adaptive_notification_ui()
    
    def load_automations(self):
        """Load automation rules"""
        # ... existing code ...
        
        # NEW: Create advanced triggers from rules
        for rule in self.rules:
            if rule.get("use_advanced_logic"):
                composite_cond = CompositeTriggerCondition(
                    id=f"rule_{rule['id']}",
                    operator=LogicOperator.AND,
                    sub_conditions=self._format_conditions(rule)
                )
                
                self.advanced_triggers.register_composite_trigger(
                    trigger_id=rule['id'],
                    name=rule['name'],
                    composite_condition=composite_cond,
                    action_callback=self._create_action(rule),
                    cooldown_seconds=rule.get('cooldown', 0)
                )
    
    def check_triggers(self, context):
        """Check if any triggers should fire"""
        for trigger_id in self.advanced_triggers.triggers:
            if self.advanced_triggers.evaluate_trigger(trigger_id, context):
                # NEW: Show diagnostic UI
                self.notification_ui.notify_diagnostic(
                    problem=f"Trigger fired: {trigger_id}",
                    findings=[f"Context: {context}"]
                )
                self.advanced_triggers.fire_trigger(trigger_id, context)
```

### C. With TaskScheduler

```python
# File: src/utils/core/task_scheduler.py

class TaskScheduler:
    def add_scheduled_job(self, job_id, schedule_type, task_func):
        """Add a scheduled job"""
        # ... existing code ...
        
        # NEW: At 9:00 AM daily, generate activity report
        if schedule_type == "daily_9am":
            def daily_report_job():
                report_gen = get_activity_report_generator()
                report = report_gen.generate_daily_summary()
                
                # Send via webhooks
                webhook_mgr = get_webhook_manager()
                webhook_mgr.send_to_webhook_sync(
                    webhook_name="default_slack",
                    message=f"Daily Report: Score {report.performance_score:.0f}/100",
                    title="📊 Daily System Summary"
                )
                
                # Send via email
                notification_mgr.send_custom_notification(
                    subject="Daily System Summary",
                    html_body=report_gen.format_report_as_html(report),
                    recipient_emails=self.subscribed_emails
                )
            
            schedule.every().day.at("09:00").do(daily_report_job)
```

### D. With Web Blueprint (REST API)

```python
# File: src/web/routes.py

from flask import Blueprint, request, jsonify
from src.utils.core.voice_command_processor import get_voice_command_processor

rest_bp = Blueprint('rest_api', __name__, url_prefix='/api')

# Voice command endpoint
@rest_bp.route('/voice/process', methods=['POST'])
def process_voice_command():
    """Process voice transcription"""
    data = request.get_json()
    
    processor = get_voice_command_processor()
    command = processor.process_voice_input(
        transcribed_text=data.get('text'),
        confidence=data.get('confidence', 0.0),
        language=data.get('language', 'en')
    )
    
    # Execute if high confidence
    if command.confidence >= 70:
        result = processor.execute_voice_command(command)
        return jsonify({
            "success": result['success'],
            "command_type": command.command_type.value,
            "confidence": command.confidence,
            "parameters": command.parameters,
            "result": result
        })
    else:
        return jsonify({
            "success": False,
            "message": f"Low confidence ({command.confidence:.0f}%). Please repeat.",
            "require_confirmation": True,
            "command": command.to_dict()
        }), 400

# Activity report endpoint
@rest_bp.route('/reports/daily', methods=['GET'])
def get_daily_report():
    """Get today's activity report"""
    gen = get_activity_report_generator()
    report = gen.generate_daily_summary()
    
    format_type = request.args.get('format', 'json')
    
    if format_type == 'markdown':
        return gen.format_report_as_markdown(report), 200, {'Content-Type': 'text/markdown'}
    elif format_type == 'html':
        return gen.format_report_as_html(report), 200, {'Content-Type': 'text/html'}
    else:  # json
        return jsonify(report.to_dict())

# Webhook management endpoint
@rest_bp.route('/webhooks', methods=['GET', 'POST'])
def manage_webhooks():
    """Manage webhook endpoints"""
    webhook_mgr = get_webhook_manager()
    
    if request.method == 'GET':
        return jsonify({
            "webhooks": webhook_mgr.get_webhook_status(),
            "failed_deliveries": webhook_mgr.get_failed_deliveries()
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        success = webhook_mgr.register_webhook(
            name=data['name'],
            webhook_type=WebhookType(data['type']),
            webhook_url=data['url']
        )
        return jsonify({"success": success})

# Decision memory endpoint
@rest_bp.route('/decisions', methods=['GET', 'POST'])
def manage_decisions():
    """Manage decision memory"""
    memory = MemoryOfDecisions(Path.cwd())
    
    if request.method == 'GET':
        return jsonify(memory.get_decision_analytics())
    
    elif request.method == 'POST':
        data = request.get_json()
        success = memory.record_decision(
            decision_id=data['id'],
            domain=DecisionDomain(data['domain']),
            decision_text=data['text'],
            reasoning=data['reasoning'],
            context=data.get('context', {}),
            chosen_option=data['option']
        )
        return jsonify({"success": success})

# Feedback endpoint
@rest_bp.route('/feedback', methods=['POST'])
def submit_feedback():
    """Submit feedback on content"""
    data = request.get_json()
    feedback_mgr = get_feedback_cycle_manager(Path.cwd())
    
    feedback = feedback_mgr.submit_feedback(
        content_id=data['content_id'],
        content_excerpt=data['excerpt'],
        feedback_type=FeedbackType(data['type']),
        feedback_text=data['feedback'],
        severity=data.get('severity', 'moderate'),
        suggested_correction=data.get('correction')
    )
    
    return jsonify(feedback.to_dict())
```

---

## 🎙️ FRONTEND INTEGRATION

### Voice Command Widget

```html
<!-- File: src/web/templates/components/voice-command.html -->

<div id="voice-command-widget" class="widget">
    <button id="start-recording" class="btn btn-primary">
        🎤 Start Recording
    </button>
    <button id="stop-recording" class="btn btn-secondary" disabled>
        Stop
    </button>
    
    <div id="transcription-display" class="transcription">
        <!-- Real-time transcription appears here -->
    </div>
    
    <div id="confidence-display" class="confidence">
        Confidence: <span id="confidence-value">0%</span>
    </div>
</div>

<script>
// Use Web Speech API
const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();

document.getElementById('start-recording').addEventListener('click', () => {
    recognition.start();
});

recognition.onresult = (event) => {
    let transcript = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
    }
    
    const confidence = event.results[event.results.length - 1][0].confidence;
    
    fetch('/api/voice/process', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            text: transcript,
            confidence: confidence * 100
        })
    })
    .then(r => r.json())
    .then(data => {
        document.getElementById('transcription-display').textContent = transcript;
        document.getElementById('confidence-value').textContent = `${(confidence * 100).toFixed(0)}%`;
        
        if (data.success) {
            alert(`✅ ${data.command_type}: ${JSON.stringify(data.parameters)}`);
        }
    });
};
</script>
```

### Artifact Injection

```javascript
// File: src/web/static/js/artifact-handler.js

// Listen for new artifacts from EventPublisher
const eventSource = new EventSource('/events/ui_artifact');

eventSource.onmessage = (event) => {
    const artifact = JSON.parse(event.data);
    
    // Render artifact based on type
    if (artifact.type === 'mermaid_diagram') {
        renderMermaidDiagram(artifact);
    } else if (artifact.type === 'metric_card') {
        renderMetricCard(artifact);
    } else if (artifact.type === 'decision_tree') {
        renderDecisionTree(artifact);
    }
    
    // Inject into sidebar
    const sidebar = document.getElementById('artifacts-sidebar');
    sidebar.appendChild(createArtifactElement(artifact));
};

function renderMermaidDiagram(artifact) {
    const div = document.createElement('div');
    div.className = 'artifact mermaid-diagram';
    div.textContent = artifact.content.diagram;
    mermaid.render('mermaid-' + artifact.id, artifact.content.diagram);
}
```

---

## ⚙️ CONFIGURATION EXAMPLE

Create `config.yaml` for Phase 6:

```yaml
# Phase 6 Configuration

push_notifications:
  enabled: true
  webhooks:
    slack:
      enabled: true
      retry_attempts: 3
      timeout_seconds: 10
    discord:
      enabled: true
    teams:
      enabled: false

voice_commands:
  enabled: true
  min_confidence: 70
  language: en

activity_reports:
  daily_time: "09:00"
  enabled: true
  include_anomalies: true
  include_trends: true

decision_memory:
  enabled: true
  max_history: 1000
  learn_preferences: true

feedback:
  enabled: true
  apply_style_preferences: true
  min_confidence: 60

advanced_triggers:
  enabled: true
  max_fires_per_minute: 10
  detect_conflicts: true
```

---

## 📊 MONITORING

Add monitoring for Phase 6:

```python
def get_phase6_health() -> Dict[str, Any]:
    """Get health status of Phase 6 components"""
    return {
        "notification_ui": {
            "active_artifacts": len(get_adaptive_notification_ui().active_artifacts),
            "status": "healthy"
        },
        "webhooks": {
            "registered": len(get_webhook_manager().webhooks),
            "recent_failures": len(get_webhook_manager().get_failed_deliveries()),
            "status": "healthy"
        },
        "reports": {
            "last_generated": get_activity_report_generator().reports_generated[-1].timestamp if get_activity_report_generator().reports_generated else None,
            "status": "healthy"
        },
        "voice": {
            "commands_processed": len(get_voice_command_processor().command_history),
            "average_confidence": get_voice_command_processor().get_command_statistics().get('average_confidence', 0),
            "status": "healthy"
        },
        "decisions": {
            "total_recorded": len(MemoryOfDecisions(Path.cwd()).decisions),
            "status": "healthy"
        },
        "feedback": {
            "total_feedback": len(get_feedback_cycle_manager(Path.cwd()).feedback_history),
            "profile_confidence": get_feedback_cycle_manager(Path.cwd()).get_feedback_summary().get('profile_confidence', 0),
            "status": "healthy"
        },
        "triggers": {
            "active_triggers": len(get_advanced_trigger_manager().triggers),
            "conflicts_detected": len(get_advanced_trigger_manager().detect_conflicts()),
            "status": "healthy"
        }
    }
```

---

## ✅ VALIDATION CHECKLIST

- [ ] All imports work correctly
- [ ] Environment variables configured
- [ ] Webhook URLs valid and tested
- [ ] Database/file storage paths correct
- [ ] Event publishing working
- [ ] REST endpoints responding
- [ ] Voice recognition working
- [ ] Reports generating successfully
- [ ] Decisions being recorded
- [ ] Feedback being captured
- [ ] Triggers evaluating correctly

---

**Ready to integrate Phase 6 into your Ollash installation!**
