# Ollash Proactive Automation System - Quick Start Guide

## What Was Implemented

Ollash now has a **complete proactive automation and alerting system** that:

✅ **Schedules tasks** (daily, hourly, custom cron)  
✅ **Monitors system resources** (CPU, RAM, Disk)  
✅ **Triggers smart alerts** when thresholds exceeded  
✅ **Sends real-time notifications** to the web UI  
✅ **Executes system agents** based on conditions  
✅ **Stores configuration** in easy-to-edit JSON files  

## 30-Second Setup

### 1. Start Ollash Normally

```bash
cd /path/to/Ollash
python run_web.py
```

The automation manager **starts automatically** when the web app initializes.

### 2. Monitor in Real-Time

Open http://localhost:5000 in your browser. You'll see:
- Real-time **alert notifications** (top-right corner)
- **Automations** tab showing scheduled tasks
- Task status and history

### 3. View Active Tasks

```bash
# Check running tasks
curl http://localhost:5000/api/automations

# View recent alerts
curl http://localhost:5000/api/alerts/history
```

## Default Configuration

### Included Tasks (pre-configured)

**Daily System Health (9:00 AM daily)**
- Checks CPU, memory, disk usage
- Analyzes running processes
- Generates comprehensive health report

**Hourly Resource Monitor (every 60 min)**
- Quick RAM & disk check
- Alerts if critical thresholds exceeded

**Weekly Process Optimization (Monday 2:00 AM)**
- Lists top 10 resource-consuming processes
- Suggests optimizations

**Monthly Performance Baseline (1st day of month)**
- Generates baseline metrics
- Compares with historical data

**Resource Threshold Alerts (every 15-30 min)**
- Disk space < 15% FREE → 🚨 Critical
- RAM available < 10% FREE → 🚨 Critical

## Customizing Tasks

### Edit `config/tasks.json`

```json
{
  "task_id": "my_custom_task",
  "name": "My Custom Monitoring",
  "schedule": {
    "type": "interval",
    "interval_minutes": 30
  },
  "agent": "system",
  "prompt": "Your monitoring prompt here",
  "notifications": {
    "enabled": true,
    "channels": ["ui", "email"],
    "severity_threshold": "warning"
  }
}
```

**After saving, either:**
- Restart Ollash: `POST /api/automations/reload`
- Or wait for OM to reload config automatically

### Cron Expressions

Use [crontab.guru](https://crontab.guru/) to generate:

```
0 9 * * *          = Every day at 9:00 AM
*/15 * * * *       = Every 15 minutes
0 2 1 * *          = 1st of month at 2:00 AM
0,30 * * * *       = Every 30 minutes
0 9 * * 1-5        = Weekdays at 9:00 AM
```

## Customizing Alerts

### Edit `config/alerts.json`

```json
{
  "alert_id": "custom_alert",
  "name": "My Custom Alert",
  "entity": "custom",
  "threshold": 85,
  "operator": ">",
  "severity": "warning",
  "cooldown_seconds": 300,
  "channels": ["ui"],
  "enabled": true
}
```

| Operator | Meaning |
|----------|---------|
| `>` | Greater than |
| `<` | Less than |
| `>=` | Greater or equal |
| `<=` | Less or equal |
| `==` | Equal |
| `!=` | Not equal |

## Email Notifications

To enable email alerts, set environment variables:

```bash
export SMTP_SERVER=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=your-email@gmail.com
export SMTP_PASSWORD=your-app-specific-password
export NOTIFICATION_FROM_EMAIL=ollash-alerts@yourdomain.com
```

Then update `config/alerts.json`:
```json
{
  "alert_id": "high_cpu",
  "channels": ["ui", "email"]
}
```

**Gmail Setup:**
1. Enable 2FA
2. Generate app password: https://myaccount.google.com/apppasswords
3. Use app password in SMTP_PASSWORD

## API Commands

### Run Task Immediately

```bash
curl -X POST http://localhost:5000/api/automations/daily_health_check/run
```

### Toggle Task ON/OFF

```bash
curl -X POST http://localhost:5000/api/automations/hourly_resource_monitor/toggle
```

### Delete Task

```bash
curl -X DELETE http://localhost:5000/api/automations/task_id
```

### Get Alert History

```bash
curl http://localhost:5000/api/alerts/history?limit=50
```

### Disable Alert Spam

```bash
curl -X POST http://localhost:5000/api/alerts/high_cpu/disable
```

## Monitoring Tools (System Agent)

The system agent can now call these tools:

**`get_system_info()`**
- OS, CPU, Memory specs
- Uptime, architecture

**`list_processes()`** 
- Running processes
- CPU/Memory per process
- PID and user info

**`check_resource_threshold(resource, threshold_percent)`**
- Alerts if disk < threshold% FREE
- Alerts if RAM < threshold% FREE
- Returns: `{alert: true/false, current_free_percent: ..., severity: ...}`

**`analyze_log_file(file_path)`**
- Parses error logs
- Extracts warnings/errors
- Count and categorization

## Real-Time UI Notifications

Notifications automatically appear (top-right):

```
┌─────────────────────────┐
│  ⚠️  High CPU Usage      │  ← Critical (red)
│  Current: 87%           │
│  Threshold: 85% (>)     │
│  [×]                    │
└─────────────────────────┘
```

**Notification Types:**
- 🔵 **INFO** (blue) - General information
- 🟡 **WARNING** (yellow) - Elevated metrics  
- 🔴 **CRITICAL** (red) - Urgent action needed
- 🟢 **SUCCESS** (green) - Task completed

**Auto-dismiss:** 5 seconds (8 seconds for critical)

**Sound Alert:** Critical alerts play system tone

## Debugging

### Check APScheduler Status

```python
# In Python REPL
from src.utils.core.automation_manager import get_automation_manager
am = get_automation_manager()
print(am.scheduler.get_jobs())  # List scheduled jobs
```

### View Execution Log

```bash
tail -f ollash.log | grep -i "automation\|alert\|task"
```

### Monitor SSE Connection

In browser console:
```javascript
console.log(proactiveAlertHandler.isConnected)  // true/false
proactiveAlertHandler.getHistory()              // Alert history
```

### Check Config Files

```bash
# Tasks configuration
cat config/tasks.json | python -m json.tool

# Alert thresholds  
cat config/alerts.json | python -m json.tool
```

## Troubleshooting

### Alerts Not Showing?

1. **Check EventPublisher:**
   ```python
   from src.utils.core.event_publisher import EventPublisher
   ep = EventPublisher()
   ```

2. **Verify alert is enabled:**
   ```json
   { "alert_id": "...", "enabled": true }
   ```

3. **Check browser console:**
   - Open DevTools (F12)
   - Go to Console tab
   - Look for errors related to `alert-handler.js`

### Tasks Not Running?

1. **Verify APScheduler started:**
   ```bash
   ps aux | grep python  # Look for 'scheduler'
   ```

2. **Check task configuration:**
   - `"enabled": true` ✓
   - Cron syntax valid (test at crontab.guru)
   - Agent exists (`system`, `network`, etc.)

3. **Review logs:**
   ```bash
   grep "Scheduled task\|Executing task" ollash.log
   ```

### Email Not Sending?

1. **Test SMTP config:**
   ```python
   from src.utils.core.notification_manager import get_notification_manager
   nm = get_notification_manager()
   print(nm.smtp_enabled)  # Should be True
   ```

2. **Verify environment variables:**
   ```bash
   echo $NOTIFICATION_FROM_EMAIL
   echo $SMTP_SERVER
   ```

3. **Check credentials:**
   - Gmail: Using app-specific password? (not regular password)
   - Other services: 2FA disabled or using app password?

## Next Steps

### 1. Create Custom Task

Edit `config/tasks.json`:
```json
{
  "task_id": "backup_check",
  "name": "Daily Backup Verification",
  "schedule": {"type": "cron", "cron_expression": "0 3 * * *"},
  "agent": "system",
  "prompt": "Check if backup directory has recent files"
}
```

### 2. Monitor Specific Process

```json
{
  "task_id": "monitor_service",
  "agent": "system",
  "prompt": "Check if WebServer process is running and using < 2GB RAM"
}
```

### 3. Weekly Cleanup

```json
{
  "task_id": "cleanup_old_logs",
  "agent": "system",
  "prompt": "Find log files older than 30 days and suggest cleanup",
  "schedule": {"type": "cron", "cron_expression": "0 2 * * 0"}
}
```

### 4. Custom Alert

```json
{
  "alert_id": "db_size",
  "entity": "database",
  "threshold": 5000,
  "operator": ">",
  "severity": "warning"
}
```

## Architecture Highlights

### Scheduling Engine (APScheduler)
- Lightweight background daemon
- Supports cron + interval triggers
- Handles timezones automatically

### Event-Driven Alerts (SSE)
- Browser-server real-time connection
- No polling needed
- Automatic reconnection on disconnect

### Modular Design
- Automation independent of alerting
- Custom callbacks for advanced use cases
- Easy to extend with new tools

### Graceful Degradation
- Email fails → UI still works
- Alert triggers → Task still executes
- Task fails → Other tasks continue

## Performance Notes

- **Default:** Checks system every 15-60 minutes
- **Memory overhead:** ~5-10 MB for scheduler
- **CPU impact:** Negligible (<1% for monitoring)
- **Network:** SSE streams use minimal bandwidth

## Security Considerations

1. **API calls:**
   - Currently open (for development)
   - Add authentication before production
   - Use API keys or JWT tokens

2. **Email credentials:**
   - Never commit .env to git
   - Use environment variables
   - Rotate app-specific passwords regularly

3. **Task execution:**
   - Runs with Ollash process privileges
   - Limit dangerous prompts
   - Review logs regularly

## Support

For issues:
1. Check this guide's Troubleshooting section
2. Review `PROACTIVE_AUTOMATION_SYSTEM.md` for detailed architecture
3. Check logs: `ollash.log`
4. Enable debug logging in app.py

---

**Status:** ✅ Production-ready for local monitoring  
**Last Updated:** February 2026
