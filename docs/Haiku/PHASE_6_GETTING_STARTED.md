# PHASE 6: DEVELOPER GETTING STARTED GUIDE

Welcome! This guide will get you up and running with Phase 6 in 15 minutes.

---

## ⚡ 15-MINUTE QUICKSTART

### Step 1: Verify Installation (2 min)
```bash
# Check all Phase 6 files exist
ls -la src/utils/core/adaptive_notification_ui.py        # 580 lines
ls -la src/utils/core/webhook_manager.py                 # 620 lines
ls -la src/utils/core/activity_report_generator.py       # 850 lines
ls -la src/utils/core/voice_command_processor.py         # 740 lines
ls -la src/utils/core/memory_of_decisions.py             # 760 lines
ls -la src/utils/core/feedback_cycle_manager.py          # 790 lines
ls -la src/utils/core/advanced_trigger_manager.py        # 620 lines

# All 7 should exist ✓
```

### Step 2: Configure Environment (3 min)
```bash
# Edit .env file
nano .env

# Add webhook URLs:
WEBHOOK_SLACK_URL=https://hooks.slack.com/services/YOUR/HOOK/URL
WEBHOOK_DISCORD_URL=https://discord.com/api/webhooks/YOUR/ID/TOKEN
WEBHOOK_TEAMS_URL=https://outlook.webhook.office.com/webhookb2/YOUR/ID
```

### Step 3: Test Imports (2 min)
```python
# python test_imports.py
from src.utils.core.adaptive_notification_ui import get_adaptive_notification_ui
from src.utils.core.webhook_manager import get_webhook_manager
from src.utils.core.activity_report_generator import get_activity_report_generator
from src.utils.core.voice_command_processor import get_voice_command_processor
from src.utils.core.memory_of_decisions import MemoryOfDecisions
from src.utils.core.feedback_cycle_manager import get_feedback_cycle_manager
from src.utils.core.advanced_trigger_manager import get_advanced_trigger_manager

print("✓ All imports successful!")
```

### Step 4: Run Unit Tests (5 min)
```bash
# Run all Phase 6 unit tests
pytest tests/unit/test_adaptive_notification_ui.py -v
pytest tests/unit/test_webhook_manager.py -v
pytest tests/unit/test_activity_report_generator.py -v
pytest tests/unit/test_voice_command_processor.py -v
pytest tests/unit/test_memory_of_decisions.py -v
pytest tests/unit/test_feedback_cycle_manager.py -v
pytest tests/unit/test_advanced_trigger_manager.py -v

# Or run all at once
pytest tests/unit/test_*.py -v  # 69 tests should pass ✓
```

### Step 5: Start Using Phase 6 (3 min)
```python
# examples.py
from src.utils.core.webhook_manager import get_webhook_manager, WebhookType, MessagePriority
from src.utils.core.voice_command_processor import get_voice_command_processor

# 1. Send notification via Slack
webhooks = get_webhook_manager()
webhooks.register_webhook("slack", WebhookType.SLACK, "https://...")
webhooks.send_to_webhook_sync(
    webhook_name="slack",
    message="Hello from Phase 6!",
    title="Test Message",
    priority=MessagePriority.MEDIUM
)

# 2. Process voice command
voice = get_voice_command_processor()
command = voice.process_voice_input("create task for testing")
print(f"Command: {command.command_type}, Confidence: {command.confidence}")
```

**You're done! Phase 6 is ready to use.** ✓

---

## 🎓 LEARNING PATH

### Beginner (Understand what Phase 6 does)
1. Read: `PHASE_6_COMPLETION_SUMMARY.md` (5 min)
2. Skim: `PHASE_6_QUICK_INTEGRATION.md` (10 min)
3. Browse: Core component docstrings (15 min)

**Outcome**: Understand 3 pillars, 9 managers, basic usage

### Intermediate (Use Phase 6 in your code)
1. Review: Component-specific section below (20 min)
2. Copy: Example code snippets (10 min)
3. Run: Unit tests for that component (10 min)
4. Modify: Example to fit your use case (20 min)

**Outcome**: Able to use 2-3 Phase 6 components in production

### Advanced (Extend Phase 6)
1. Study: E2E test workflows (30 min)
2. Read: Component source code (60 min)
3. Plan: Your new feature (30 min)
4. Implement: New functionality (as needed)
5. Test: With unit + E2E tests (as needed)

**Outcome**: Can add new features to Phase 6

---

## 🔥 CORE COMPONENTS OVERVIEW

### 1️⃣ AdaptiveNotificationUI - Send Beautiful Notifications
**What it does**: Creates interactive visual artifacts instead of simple messages

```python
from src.utils.core.adaptive_notification_ui import get_adaptive_notification_ui

ui = get_adaptive_notification_ui()

# Create network diagram notification
ui.notify_network_error(
    service_name="API",
    failed_nodes=["node2", "node4"],
    error_message="Connection timeout"
)

# Create status dashboard
ui.notify_system_status(
    metrics={"cpu": 85, "memory": 72},
    thresholds={"cpu": 80, "memory": 70}
)

# Create decision tree for troubleshooting
ui.notify_decision_point(
    problem="High latency",
    options={
        "scale": "Add more servers",
        "optimize": "Optimize code"
    }
)
```

**Tests**: `tests/unit/test_adaptive_notification_ui.py` (9 tests)

---

### 2️⃣ WebhookManager - Send to Slack, Discord, Teams
**What it does**: Send notifications to external services with rich formatting

```python
from src.utils.core.webhook_manager import (
    get_webhook_manager, WebhookType, MessagePriority
)

webhooks = get_webhook_manager()

# Register Slack webhook
webhooks.register_webhook(
    name="prod_alerts",
    webhook_type=WebhookType.SLACK,
    webhook_url="https://hooks.slack.com/services/..."
)

# Send message
webhooks.send_to_webhook_sync(
    webhook_name="prod_alerts",
    message="CPU usage at 85%",
    title="⚠️ Performance Alert",
    priority=MessagePriority.HIGH,
    fields={
        "Service": "API Server",
        "Duration": "3 minutes",
        "Action": "Investigating..."
    }
)

# Check status
status = webhooks.get_webhook_status()
failures = webhooks.get_failed_deliveries()
```

**Tests**: `tests/unit/test_webhook_manager.py` (10 tests)

---

### 3️⃣ ActivityReportGenerator - Generate Smart Reports
**What it does**: Create daily/trend/anomaly reports with analytics

```python
from src.utils.core.activity_report_generator import get_activity_report_generator

gen = get_activity_report_generator()

# Daily summary
daily = gen.generate_daily_summary()
print(f"Performance Score: {daily.performance_score:.0f}/100")
print(f"Metrics: {daily.metrics}")

# Performance trends
trends = gen.generate_performance_trend_report()

# Anomalies
anomalies = gen.generate_anomaly_report()

# Export formats
markdown = gen.format_report_as_markdown(daily)
html = gen.format_report_as_html(daily)
```

**Tests**: `tests/unit/test_activity_report_generator.py` (10 tests)

---

### 4️⃣ VoiceCommandProcessor - Voice to Action
**What it does**: Convert voice transcriptions to executable commands

```python
from src.utils.core.voice_command_processor import get_voice_command_processor

voice = get_voice_command_processor()

# Process voice input
command = voice.process_voice_input(
    transcribed_text="create high priority task for tomorrow",
    confidence=92.5,
    language="en"
)

# Check confidence
if command.confidence >= 70:
    # Execute command
    result = voice.execute_voice_command(command)
    print(f"✓ Executed: {command.command_type}")
else:
    print(f"✗ Low confidence ({command.confidence:.0f}%)")

# Get history
history = voice.command_history
stats = voice.get_command_statistics()
```

**Tests**: `tests/unit/test_voice_command_processor.py` (10 tests)

---

### 5️⃣ MemoryOfDecisions - Learn from Decisions
**What it does**: Track decisions, record outcomes, suggest similar approaches

```python
from src.utils.core.memory_of_decisions import (
    MemoryOfDecisions, DecisionDomain
)
from pathlib import Path

memory = MemoryOfDecisions(Path.cwd())

# Record a decision
memory.record_decision(
    decision_id="cache_001",
    domain=DecisionDomain.OPTIMIZATION,
    decision_text="Implement Redis caching",
    reasoning="Reduce database load",
    context={"service": "user_api"},
    chosen_option="redis_cache",
    alternatives=["memcached", "in_memory"]
)

# Later: Record outcome
memory.record_decision_outcome(
    decision_id="cache_001",
    satisfaction_score=95.0,
    actual_outcome="60% response time improvement",
    lessons_learned="Redis very effective"
)

# Get suggestions for similar problem
suggestions = memory.get_decision_suggestions(
    current_context={"service": "product_api", "issue": "slow_queries"},
    limit=5
)

# Analytics
analytics = memory.get_decision_analytics()
```

**Tests**: `tests/unit/test_memory_of_decisions.py` (10 tests)

---

### 6️⃣ FeedbackCycleManager - Learn User Preferences
**What it does**: Extract preferences from feedback and apply them to future output

```python
from src.utils.core.feedback_cycle_manager import (
    get_feedback_cycle_manager, FeedbackType
)
from pathlib import Path

feedback_mgr = get_feedback_cycle_manager(Path.cwd())

# Submit feedback
feedback_mgr.submit_feedback(
    content_id="report_001",
    content_excerpt="Long detailed explanation...",
    feedback_type=FeedbackType.TOO_VERBOSE,
    feedback_text="This is too long, be more concise",
    severity="moderate"
)

# Get learned style profile
profile = feedback_mgr.get_style_profile()
# Returns: {"verbosity": 30, "technical_level": 60, "tone": 70}

# Apply learned style to new content
styled_text = feedback_mgr.apply_style_preferences(
    original_text="Very long detailed description..."
)

# Get trends
trends = feedback_mgr.get_feedback_trends(days=7)
summary = feedback_mgr.get_feedback_summary()
```

**Tests**: `tests/unit/test_feedback_cycle_manager.py` (10 tests)

---

### 7️⃣ AdvancedTriggerManager - Complex Automation
**What it does**: Create complex automation rules with AND/OR/NOT logic

```python
from src.utils.core.advanced_trigger_manager import (
    get_advanced_trigger_manager, LogicOperator, CompositeTriggerCondition
)

triggers = get_advanced_trigger_manager()

# Register composite trigger (AND condition)
condition = CompositeTriggerCondition(
    id="high_system_stress",
    operator=LogicOperator.AND,
    sub_conditions=[
        {"metric": "cpu", "operator": ">", "value": 85},
        {"metric": "memory", "operator": ">", "value": 80}
    ]
)

triggers.register_composite_trigger(
    trigger_id="stress_alert",
    name="System Stress Detection",
    composite_condition=condition,
    action_callback=lambda ctx: print(f"Alert! Context: {ctx}"),
    cooldown_seconds=60
)

# Evaluate trigger
context = {"cpu": 92, "memory": 88}
should_fire = triggers.evaluate_trigger("stress_alert", context)

# Fire manually
triggers.fire_trigger("stress_alert", context)

# Detect conflicts
conflicts = triggers.detect_conflicts()
```

**Tests**: `tests/unit/test_advanced_trigger_manager.py` (10 tests)

---

## 🌐 REST API QUICK REFERENCE

### Health Check
```bash
curl http://localhost:5000/api/v1/health
```

### Send via Webhook
```bash
curl -X POST http://localhost:5000/api/v1/webhooks/my_slack/send \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Alert",
    "message": "System status update",
    "priority": "MEDIUM"
  }'
```

### Process Voice Command
```bash
curl -X POST http://localhost:5000/api/v1/voice/process \
  -H "Content-Type: application/json" \
  -d '{
    "text": "create task for testing",
    "confidence": 95.0
  }'
```

### Submit Feedback
```bash
curl -X POST http://localhost:5000/api/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "content_1",
    "excerpt": "Sample content",
    "type": "TOO_VERBOSE",
    "feedback": "Be more concise"
  }'
```

### More endpoints in `PHASE_6_API_INTEGRATION.md`

---

## 🧪 TESTING YOUR CHANGES

### Run Tests for Specific Component
```bash
# Test webhook manager
pytest tests/unit/test_webhook_manager.py -v

# Test with specific function
pytest tests/unit/test_webhook_manager.py::TestWebhookFormatting -v

# Run with output
pytest tests/unit/test_webhook_manager.py -v -s
```

### Create Your Own Test
```python
# tests/unit/test_my_feature.py
import pytest
from src.utils.core.voice_command_processor import get_voice_command_processor

def test_my_feature():
    """Test my new feature"""
    processor = get_voice_command_processor()
    
    # Your test here
    assert processor is not None
```

### Run All Phase 6 Tests
```bash
pytest tests/ -k "phase6 or adaptive or webhook or voice or memory or feedback or trigger" -v
```

---

## 📈 COMMON USE CASES

### Use Case 1: Monitor System and Alert
```python
from src.utils.core.advanced_trigger_manager import get_advanced_trigger_manager
from src.utils.core.webhook_manager import get_webhook_manager

triggers = get_advanced_trigger_manager()
webhooks = get_webhook_manager()

# Create trigger
# ... (register composite trigger for high CPU AND memory)

# In your monitoring loop
context = get_current_metrics()  # Your metrics function
if triggers.evaluate_trigger("high_stress", context):
    webhooks.send_to_webhook_sync(
        webhook_name="slack",
        message="System under stress!",
        title="⚠️ Alert"
    )
```

### Use Case 2: Voice-to-Task Automation
```python
from src.utils.core.voice_command_processor import get_voice_command_processor
from src.utils.core.memory_of_decisions import MemoryOfDecisions

voice = get_voice_command_processor()
memory = MemoryOfDecisions(Path.cwd())

# User speaks
command = voice.process_voice_input(audio_transcription)

if command.confidence >= 70:
    # Execute
    result = voice.execute_voice_command(command)
    
    # Remember decision
    memory.record_decision(
        decision_id=f"voice_{datetime.now().timestamp()}",
        domain=DecisionDomain.AUTOMATION,
        decision_text=command.original_text,
        reasoning="Voice command",
        chosen_option=command.command_type.value
    )
```

### Use Case 3: Daily Reports with Learning
```python
from src.utils.core.activity_report_generator import get_activity_report_generator
from src.utils.core.feedback_cycle_manager import get_feedback_cycle_manager

report_gen = get_activity_report_generator()
feedback_mgr = get_feedback_cycle_manager(Path.cwd())

# Generate report
report = report_gen.generate_daily_summary()

# Get learned style preferences
style = feedback_mgr.get_style_profile()

# Format with learned style
if style and style.get("verbosity", 50) < 40:
    # User prefers concise
    formatted = report_gen.format_report_as_markdown(report)
else:
    # User wants details
    formatted = report_gen.format_report_as_html(report)

# Send with learned preferences applied
```

---

## 🐛 COMMON ISSUES & SOLUTIONS

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Ensure `src/` directory is in PYTHONPATH |
| `JSONDecodeError` in webhook | Check webhook URL format in `.env` |
| Voice confidence too low | Lower `VOICE_MIN_CONFIDENCE` threshold |
| Tests fail with `FileNotFoundError` | Run tests from project root directory |
| Decisions not persisting | Check write permissions on project root |
| Feedback not learned | Submit multiple feedback items (5+) |

---

## 📚 DOCUMENTATION MAP

| Document | Purpose | Read Time |
|----------|---------|-----------|
| This file (getting_started.md) | Quick reference | 15 min |
| PHASE_6_COMPLETION_SUMMARY.md | Full overview | 30 min |
| PHASE_6_QUICK_INTEGRATION.md | Copy-paste examples | 20 min |
| PHASE_6_API_INTEGRATION.md | API endpoints | 25 min |
| Individual `test_*.py` files | Usage examples | 10 min each |

---

## ✅ NEXT STEPS

### Immediate (Today)
- [ ] Run the 15-minute quickstart
- [ ] Run unit tests
- [ ] Read PHASE_6_COMPLETION_SUMMARY.md
- [ ] Test one component with curl

### Short Term (This week)
- [ ] Integrate 2-3 Phase 6 components into your code
- [ ] Write tests for your usage
- [ ] Configure webhooks
- [ ] Deploy to development

### Medium Term (This month)
- [ ] Integrate all Phase 6 components
- [ ] Create custom triggers
- [ ] Build frontend voice widget
- [ ] Deploy to production

---

## 🚀 YOU'RE READY!

Phase 6 is built for developers like you. Start small, test often, and extend as needed.

**Questions?** Check the documentation files listed above.  
**Issues?** Review the test files for usage patterns.  
**Extending?** Follow the existing component patterns.

Happy coding! 🎉

---

**Phase 6 Documentation Index:**
- Getting Started (you are here)
- PHASE_6_COMPLETION_SUMMARY.md (full overview)
- PHASE_6_QUICK_INTEGRATION.md (integration guide)
- PHASE_6_API_INTEGRATION.md (API reference)
- FILE_STRUCTURE_PHASE6.md (file map)
