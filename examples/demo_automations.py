#!/usr/bin/env python3
"""
Demo script for Ollash Automations System
Shows how to use the automation components programmatically
"""

import asyncio
import sys
import os
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

from src.utils.core.notification_manager import NotificationManager
from src.utils.core.task_scheduler import TaskScheduler
from src.utils.core.event_publisher import EventPublisher


def demo_notification_manager():
    """Demo: NotificationManager usage"""
    print("\n" + "="*60)
    print("🔔 NOTIFICATION MANAGER DEMO")
    print("="*60)
    
    nm = NotificationManager()
    
    # Subscribe emails
    print("\n1️⃣  Subscribing emails...")
    nm.subscribe_email('admin@example.com')
    nm.subscribe_email('user@example.com')
    print(f"   ✓ Subscribed emails: {nm.subscribed_emails}")
    
    # Check SMTP config
    print("\n2️⃣  SMTP Configuration Status:")
    print(f"   Server: {nm.smtp_server}")
    print(f"   Port: {nm.smtp_port}")
    print(f"   Enabled: {nm.smtp_enabled}")
    if not nm.smtp_enabled:
        print("   ⚠️  Email notifications disabled - configure .env to enable")
    
    # Build HTML email
    print("\n3️⃣  Generating notification HTML...")
    html = nm._build_html_email(
        title="System Disk Space Alert",
        content="""
            <p><strong>Disk Usage: 85%</strong></p>
            <p>Threshold: 80%</p>
            <p>Action: Please free up space on /dev/sda1</p>
        """,
        status="warning"
    )
    print(f"   ✓ Generated {len(html)} characters of HTML")
    print("   Sample preview:")
    print("   " + "\n   ".join(html.split('\n')[:5]))
    
    print("\n   💡 In production, this would be sent via SMTP")


def demo_task_scheduler():
    """Demo: TaskScheduler usage"""
    print("\n" + "="*60)
    print("⏰ TASK SCHEDULER DEMO")
    print("="*60)
    
    scheduler = TaskScheduler()
    scheduler.initialize()
    
    print("\n1️⃣  Creating triggers for different schedules...")
    
    schedules = [
        {'name': 'Hourly', 'schedule': 'hourly'},
        {'name': 'Daily (8 AM)', 'schedule': 'daily'},
        {'name': 'Weekly (Monday)', 'schedule': 'weekly'},
        {'name': 'Custom (Every 30 min)', 'schedule': 'custom', 'cron': '*/30 * * * *'},
    ]
    
    for sched in schedules:
        trigger = scheduler._get_trigger(sched)
        print(f"   ✓ {sched['name']}: {trigger}")
    
    print("\n2️⃣  Task Configuration Examples:")
    
    task_configs = [
        {
            'name': 'disk_check',
            'type': 'System Monitoring',
            'config': {
                'schedule': 'hourly',
                'agent': 'system',
                'prompt': 'Check disk space and report usage'
            }
        },
        {
            'name': 'network_health',
            'type': 'Network Health',
            'config': {
                'schedule': 'daily',
                'agent': 'network',
                'prompt': 'Test connectivity and DNS resolution'
            }
        },
        {
            'name': 'security_audit',
            'type': 'Security Audit',
            'config': {
                'schedule': 'weekly',
                'agent': 'cybersecurity',
                'prompt': 'Scan for open ports and vulnerabilities'
            }
        }
    ]
    
    for task in task_configs:
        print(f"\n   📋 {task['type']} - {task['name']}")
        print(f"      Schedule: {task['config']['schedule']}")
        print(f"      Agent: {task['config']['agent']}")
        print(f"      Prompt: {task['config']['prompt'][:50]}...")
    
    print("\n3️⃣  Scheduling example tasks...")
    
    # Note: In real app, these would be persisted and actually scheduled
    print("   ⏳ Would schedule tasks with APScheduler")
    print("   📊 Jobs would appear in scheduler.get_jobs()")


def demo_event_flow():
    """Demo: Event flow in automation system"""
    print("\n" + "="*60)
    print("🔄 EVENT FLOW DEMO")
    print("="*60)
    
    print("\nAutomation Execution Flow:")
    print("""
    1. [APScheduler] Detects task is due (e.g., every hour)
       ↓
    2. [APScheduler] Calls _execute_scheduled_task()
       ↓
    3. [AutomationExecutor] Instantiates appropriate agent
       ↓
    4. [Agent] Executes prompt and returns output
       ↓
    5. [NotificationManager] Sends result via email/UI
       ↓
    6. [EventPublisher] Publishes task:completed event
       ↓
    7. [Web UI] Receives event via SSE and updates display
    """)
    
    print("Events Published:")
    events = [
        ('task:started', 'Task execution begins'),
        ('task:progress', 'Task is running'),
        ('task:completed', 'Task completed successfully'),
        ('task:error', 'Task failed with error'),
        ('threshold:exceeded', 'Metric crossed threshold'),
    ]
    
    for event, desc in events:
        print(f"   📢 {event:20} - {desc}")


def demo_json_format():
    """Demo: Show JSON format of tasks"""
    print("\n" + "="*60)
    print("📋 TASK CONFIGURATION FORMAT")
    print("="*60)
    
    import json
    
    example_task = {
        "task_abc123": {
            "name": "Daily Disk Check",
            "agent": "system",
            "prompt": "Check disk space on all partitions and alert if any exceed 80%",
            "schedule": "daily",
            "cron": None,
            "status": "active",
            "notifyEmail": True,
            "createdAt": "2026-02-11T10:30:00",
            "lastRun": "2026-02-11T08:00:00",
            "nextRun": "2026-02-12T08:00:00"
        },
        "task_def456": {
            "name": "Weekly Security Audit",
            "agent": "cybersecurity",
            "prompt": "Scan open ports and check for common vulnerabilities",
            "schedule": "weekly",
            "cron": None,
            "status": "active",
            "notifyEmail": True,
            "createdAt": "2026-02-10T15:20:00",
            "lastRun": None,
            "nextRun": "2026-02-17T08:00:00"
        }
    }
    
    print("\nFormat stored in 'config/scheduled_tasks.json':")
    print(json.dumps(example_task, indent=2))


def demo_api_endpoints():
    """Demo: Show REST API endpoints"""
    print("\n" + "="*60)
    print("🌐 REST API ENDPOINTS")
    print("="*60)
    
    endpoints = [
        {
            'method': 'GET',
            'path': '/api/automations',
            'desc': 'List all scheduled tasks',
            'example': 'curl http://localhost:5000/api/automations'
        },
        {
            'method': 'POST',
            'path': '/api/automations',
            'desc': 'Create new task',
            'example': 'curl -X POST http://localhost:5000/api/automations -d \'{"name":"Test","agent":"system",...}\''
        },
        {
            'method': 'PUT',
            'path': '/api/automations/<task_id>/toggle',
            'desc': 'Enable/disable task',
            'example': 'curl -X PUT http://localhost:5000/api/automations/task_123/toggle'
        },
        {
            'method': 'POST',
            'path': '/api/automations/<task_id>/run',
            'desc': 'Execute task immediately',
            'example': 'curl -X POST http://localhost:5000/api/automations/task_123/run'
        },
        {
            'method': 'DELETE',
            'path': '/api/automations/<task_id>',
            'desc': 'Delete task',
            'example': 'curl -X DELETE http://localhost:5000/api/automations/task_123'
        }
    ]
    
    for ep in endpoints:
        print(f"\n   {ep['method']:4} {ep['path']:40} - {ep['desc']}")
        print(f"         {ep['example']}")


def main():
    """Run all demos"""
    print("\n")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     🎯 OLLASH AUTOMATIONS SYSTEM - DEMO                 ║")
    print("╚══════════════════════════════════════════════════════════╝")
    
    try:
        demo_notification_manager()
        demo_task_scheduler()
        demo_event_flow()
        demo_json_format()
        demo_api_endpoints()
        
        print("\n" + "="*60)
        print("✅ DEMO COMPLETE")
        print("="*60)
        print("\n📚 For more info, see AUTOMATIONS_SETUP.md")
        print("🚀 Start the app with: python run_web.py")
        print("🌐 Open: http://localhost:5000")
        print("📍 Go to: Automations tab in sidebar\n")
        
    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
