# Ollash Proactive Automation System - Technical Documentation

## Overview

This document describes the implementation of a **proactive automation and alerting system** for Ollash that enables scheduled task execution, real-time system monitoring, and intelligent alert routing.

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Web UI (Browser)                          │
│  - Real-time Notifications (SSE)                            │
│  - Alert Handler (ws/alert-handler.js)                      │
│  - Task Management Dashboard                                │
└──────────────────────┬──────────────────────────────────────┘
                       │ SSE & REST APIs
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Flask Web Application (src/web/app.py)          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Blueprints Registration & Initialization            │   │
│  │  - /api/alerts - Alert Stream & Management           │   │
│  │  - /api/automations - Task Management API            │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │ Events & Configuration
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Automation & Alert Orchestration Layer             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ AutomationManager (automation_manager.py)             │ │
│  │  - APScheduler (cron & interval scheduling)           │ │
│  │  - Task execution with callbacks                      │ │
│  │  - Task state persistence (tasks.json)                │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ AlertManager (alert_manager.py)                       │ │
│  │  - Threshold monitoring & evaluation                  │ │
│  │  - Alert history tracking                             │ │
│  │  - Multi-channel notification routing                │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ NotificationManager (notification_manager.py)         │ │
│  │  - Email (SMTP) notifications                         │ │
│  │  - UI alerts (via EventPublisher)                    │ │
│  │  - Logging                                            │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │ Events & Tool Execution
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              System Monitoring Tools Layer                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ SystemTools (system_tools.py) - New Tools:            │ │
│  │  ✓ check_resource_threshold(resource, threshold_%)   │ │
│  │  ✓ get_system_info()                                  │ │
│  │  ✓ list_processes()                                   │ │
│  │  ✓ read_log_file(path, lines)                        │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Agent Execution (Default Agent)                       │ │
│  │  - Executes system agent prompts                      │ │
│  │  - Access to monitoring tools                         │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## File Structure

### New Files Created

```
src/utils/core/
├── automation_manager.py          # Main automation orchestrator
├── alert_manager.py               # Alert evaluation & triggering
└── (notification_manager.py)      # Enhanced with UI notification method

src/web/blueprints/
├── alerts_bp.py                   # Alert API endpoints & SSE stream
└── automations_bp_api.py          # Automation task management API

src/web/static/js/
├── alert-handler.js               # Client-side alert listener & UI

config/
├── tasks.json                      # Scheduled task definitions
└── alerts.json                     # Alert threshold configurations
```

### Modified Files

```
src/web/app.py                     # Added blueprint registration & initialization
src/web/templates/index.html       # Added automations section & script includes
src/utils/domains/system/system_tools.py  # Added check_resource_threshold tool
src/utils/core/notification_manager.py    # Added send_ui_notification method
```

## Configuration Files

### tasks.json - Scheduled Automation Tasks

```json
{
  "tasks": [
    {
      "task_id": "hourly_resource_monitor",
      "name": "Hourly Resource Monitor",
      "schedule": {
        "type": "interval",
        "interval_minutes": 60
      },
      "agent": "system",
      "prompt": "Check current RAM and disk usage...",
      "thresholds": {...},
      "notifications": {...}
    }
  ]
}
```

**Supported Schedule Types:**
- `interval`: Execute every N minutes
- `cron`: Execute at specific time (e.g., `0 9 * * *` = daily at 9 AM)

### alerts.json - Alert Definitions

```json
{
  "alerts": [
    {
      "alert_id": "high_cpu",
      "name": "High CPU Usage",
      "threshold": 85,
      "operator": ">",
      "severity": "critical",
      "cooldown_seconds": 600,
      "channels": ["ui", "email"]
    }
  ]
}
```

**Alert Operators:** `>`, `<`, `>=`, `<=`, `==`, `!=`

**Severity Levels:** `info`, `warning`, `critical`

## API Endpoints

### Alert Endpoints

```
GET  /api/alerts              - List active alerts
GET  /api/alerts/stream       - SSE: Real-time alert stream  
GET  /api/alerts/history      - Alert history
POST /api/alerts/<id>/enable   - Enable alert
POST /api/alerts/<id>/disable  - Disable alert
POST /api/alerts/history/clear - Clear alert history
```

### Automation Endpoints

```
GET  /api/automations            - List all tasks
GET  /api/automations/<id>       - Get task details
PUT  /api/automations/<id>       - Update task
POST /api/automations/<id>/run   - Execute task immediately
POST /api/automations/<id>/toggle - Enable/disable task
DEL  /api/automations/<id>       - Delete task
POST /api/automations/reload     - Reload from config
```

## Monitoring Tools

### New SystemTool: check_resource_threshold

```python
def check_resource_threshold(
    resource: str,      # "disk" or "ram"
    threshold_percent: int  # Alert if free < this %
) -> dict
```

**Response:**
```json
{
  "ok": true,
  "alert": true,
  "resource": "disk",
  "current_free_percent": 12.5,
  "threshold_percent": 15,
  "severity": "critical"
}
```

## Real-Time Alert Flow

### 1. Threshold Check (Every 15-60 minutes)

```
AutomationManager._schedule_task()
  ↓ (APScheduler triggers)
AutomationManager._execute_task_wrapper()
  ↓
SystemAgent executes monitoring prompt
  ↓
check_resource_threshold() evaluates metrics
  ↓
AlertManager.check_alert() determines if threshold exceeded
```

### 2. Alert Triggering

```
AlertManager.trigger_alert()
  ├─→ Log to system logger
  ├─→ Send UI notification (NotificationManager.send_ui_notification)
  ├─→ Send email (if configured)
  ├─→ Execute callback (if registered)
  └─→ Publish event (EventPublisher.publish("alert_triggered", ...))
```

### 3. Client-Side Reception (SSE)

```
Browser connects to /api/alerts/stream
  ↓
EventPublisher routes event to SSE subscriber queue
  ↓
Server sends: event: alert_triggered\ndata: {...}\n\n
  ↓
alert-handler.js receives & processes
  ├─→ Display notification UI
  ├─→ Play alert sound (if critical)
  ├─→ Update alert history
  └─→ Trigger custom callbacks
```

## Execution Flow Example

### Scenario: Daily System Health Check + Resource Alerts

**1. Configuration (tasks.json):**
```json
{
  "task_id": "daily_health_check",
  "schedule": {"type": "cron", "cron_expression": "0 9 * * *"},
  "agent": "system",
  "prompt": "Perform system health check..."
}
```

**2. Startup (app.py):**
```python
automation_manager = get_automation_manager(ollash_root_dir, event_publisher)
automation_manager.start()  # Starts APScheduler daemon
```

**3. Scheduled Time Reached (9:00 AM):**
```
APScheduler fires trigger
  ↓
AutomationManager._execute_task_wrapper("daily_health_check", task)
  ↓
SystemAgent.chat("Perform system health check...")
  ├─→ Calls get_system_info()
  ├─→ Calls list_processes()
  └─→ Calls check_resource_threshold()
  ↓
Agent evaluates results and generates report
  ↓
EventPublisher.publish("task_execution_complete", {...})
  ↓
Browser receives SSE event & displays notification
```

## Event Stream Types

### Server-Sent Events (SSE)

The `/api/alerts/stream` endpoint broadcasts these events:

```javascript
// Threshold-based alert triggered
event: alert_triggered
data: {
  "alert_id": "high_cpu",
  "name": "High CPU Usage",
  "current_value": 87,
  "severity": "critical"
}

// Proactive automation notification
event: task_execution_complete
data: {
  "task_id": "daily_health_check",
  "task_name": "Daily System Health Report",
  "timestamp": "2026-02-11T09:00:00"
}

// System-level UI alert
event: ui_alert
data: {
  "title": "⚠️ Disk Space Low",
  "message": "Available disk space below 20%",
  "type": "warning"
}
```

## Client-Side Integration

### JavaScript Alert Handler (alert-handler.js)

```javascript
// Automatically connects on page load
proactiveAlertHandler = new ProactiveAlertHandler();
proactiveAlertHandler.connect();  // SSE connection

// Listens for events and displays notifications
proactiveAlertHandler.handleAlertTriggered(eventData)
  ├─→ showNotification() - Display UI toast
  ├─→ playAlertSound() - Audio cue for critical
  └─→ addToHistory() - Record for dashboard
```

### Notification Display

```css
.notification {
  position: fixed;
  top: 20px; right: 20px;
  animation: slideIn 0.3s;
  auto-dismiss: 5s (8s for critical)
}

.notification-critical { background: #fee2e2; border-left: 4px solid #ef4444; }
.notification-warning { background: #fef3c7; border-left: 4px solid #f59e0b; }
.notification-info    { background: white;   border-left: 4px solid #3b82f6; }
```

## Configuration Best Practices

### 1. Task Scheduling

**Daily vs. Hourly:**
```json
{
  "type": "cron",
  "cron_expression": "0 9 * * *"  // Daily 9 AM
}
{
  "type": "interval",
  "interval_minutes": 60           // Every hour
}
```

**Cron Expression Guide:**
```
minute    hour    day-of-month    month    day-of-week
(0-59)    (0-23)  (1-31)          (1-12)   (0-6)

0 9 * * *        = Daily at 9:00 AM
*/15 * * * *     = Every 15 minutes
0 */4 * * *      = Every 4 hours
0 2 * * 1        = Monday at 2:00 AM
```

### 2. Alert Thresholds

**Recommended Thresholds:**
```json
{
  "cpu": {"warning": 70, "critical": 90},
  "memory": {"warning": 75, "critical": 90},
  "disk": {"warning": 30, "critical": 15}
}
```

### 3. Notification Channels

**For Production:**
```json
{
  "email": {
    "enabled": true,
    "min_severity": "critical",
    "requires_config": true
  },
  "ui": {
    "enabled": true,
    "auto_dismiss_ms": 5000
  }
}
```

**Environment Variables Required (for email):**
```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
NOTIFICATION_FROM_EMAIL=alerts@ollash.local
```

## Performance Considerations

### APScheduler Configuration

- **Max concurrent jobs:** Configurable in `execution_rules`
- **Daemon threads:** Background execution (non-blocking)
- **Job timeouts:** 300 seconds (configurable)
- **Retry logic:** Up to 2 retries with 60s delay

### EventPublisher Performance

- **Subscriber-based:** Only active connections receive events
- **Queue-based:** Non-blocking event delivery
- **Memory-efficient:** Auto-cleanup of inactive subscribers

### Alert Cooldown

Prevents alert spam with configurable cooldown periods:
```json
{
  "alert_id": "high_cpu",
  "cooldown_seconds": 600  // Min 10 min between alerts
}
```

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# In app.py
logger.setLevel(logging.DEBUG)
```

### Monitor Tasks

```bash
# Check scheduled tasks status
GET /api/automations

# View alert history
GET /api/alerts/history?limit=100

# Check specific task
GET /api/automations/{task_id}
```

### Browser Console

```javascript
// Check alert handler connection
proactiveAlertHandler.isConnected  // true/false

// View alert history
proactiveAlertHandler.getHistory(10)

// Manually test notification
proactiveAlertHandler.showNotification(
  "Test Alert",
  "This is a test",
  "warning"
)
```

## Future Enhancements

1. **Dashboard Metrics:**
   - Real-time CPU/RAM/Disk graphs
   - Task execution history
   - Alert trend analysis

2. **Maintenance Agent:**
   - Identify high-consuming processes
   - Suggest automatic cleanup actions
   - Process termination (with user approval)

3. **Database Persistence:**
   - Replace tasks.json with SQLite
   - Store alert history in DB
   - Query historical metrics

4. **Advanced Automation:**
   - Task dependencies & chaining
   - Conditional task branches
   - Task output caching

5. **Integration:**
   - Slack/Discord webhooks
   - PagerDuty escalation
   - Custom webhook receivers

## Troubleshooting

### Alerts Not Appearing

1. Check `/api/alerts/stream` connection (browser dev tools → Network)
2. Verify `EventPublisher` is initialized: `current_app.config['event_publisher']`
3. Check browser console for JavaScript errors
4. Verify alert is `enabled: true` in alerts.json

### Tasks Not Executing

1. Verify `automation_manager.running == True`
2. Check APScheduler jobs: `automation_manager.scheduler.get_jobs()`
3. Verify task `enabled: true` in tasks.json
4. Check cron expression syntax
5. Review logs: `GET /api/alerts/history`

### Email Not Sending

1. Verify SMTP credentials in .env file
2. Check `notification_manager.smtp_enabled`
3. Verify `alert.channels` includes "email"
4. Test SMTP connection independently

## References

- **APScheduler:** https://apscheduler.readthedocs.io/
- **Server-Sent Events:** https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
- **Cron Expression:** https://crontab.guru/
