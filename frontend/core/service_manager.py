"""Module for initializing and managing core application services."""

import logging
from pathlib import Path
from backend.utils.core.system.alert_manager import get_alert_manager
from backend.utils.core.system.automation_manager import get_automation_manager
from backend.utils.core.system.notification_manager import get_notification_manager


def init_app_services(app, ollash_root_dir: Path, event_publisher):
    """Initializes managers and core services, attaching them to app config."""
    logger = app.config.get("logger") or logging.getLogger(__name__)

    try:
        automation_manager = get_automation_manager(ollash_root_dir, event_publisher)
        notification_manager = get_notification_manager()
        alert_manager = get_alert_manager(notification_manager, event_publisher)

        # Store in app config for blueprints to access
        app.config["automation_manager"] = automation_manager
        app.config["notification_manager"] = notification_manager
        app.config["alert_manager"] = alert_manager
        app.config["event_publisher"] = event_publisher

        # Start the automation manager
        automation_manager.start()
        logger.info("✅ Automation Manager and core services started successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize core services: {e}", exc_info=True)
        # We continue to allow the UI to start even if some background services fail

    return app
