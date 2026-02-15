"""Notification Manager - Handles multi-channel notifications (Email, UI, etc.)"""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manages notifications across multiple channels."""

    def __init__(self):
        """Initialize notification manager with SMTP config from env."""
        self.smtp_server = os.environ.get("SMTP_SERVER")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USER")
        self.smtp_password = os.environ.get("SMTP_PASSWORD")
        self.from_email = os.environ.get("NOTIFICATION_FROM_EMAIL")
        self.from_name = os.environ.get("NOTIFICATION_FROM_NAME", "Ollash Agent")

        # Email channels to be stored (for future persistence)
        self.subscribed_emails = set()

        self._validate_smtp_config()

    def _validate_smtp_config(self):
        """Check if SMTP configuration is valid."""
        self.smtp_enabled = all(
            [self.smtp_server, self.smtp_user, self.smtp_password, self.from_email]
        )

        if not self.smtp_enabled:
            logger.warning(
                "SMTP not fully configured. Email notifications will be disabled. "
                "Set SMTP_SERVER, SMTP_USER, SMTP_PASSWORD, NOTIFICATION_FROM_EMAIL in .env"
            )
        else:
            logger.info(
                f"Email notifications enabled (SMTP: {self.smtp_server}:{self.smtp_port})"
            )

    def subscribe_email(self, email: str) -> bool:
        """
        Subscribe an email address to notifications.

        Args:
            email: Email address to subscribe

        Returns:
            bool: True if valid email, False otherwise
        """
        if self._is_valid_email(email):
            self.subscribed_emails.add(email)
            logger.info(f"Email subscribed: {email}")
            return True
        return False

    def unsubscribe_email(self, email: str) -> bool:
        """Unsubscribe an email address."""
        if email in self.subscribed_emails:
            self.subscribed_emails.discard(email)
            logger.info(f"Email unsubscribed: {email}")
            return True
        return False

    def send_task_completion(
        self,
        task_name: str,
        agent_type: str,
        result: str,
        recipient_emails: Optional[List[str]] = None,
        success: bool = True,
    ) -> bool:
        """
        Send notification about a completed task.

        Args:
            task_name: Name of the completed task
            agent_type: Type of agent that ran the task
            result: Result/output from the task
            recipient_emails: List of email addresses (uses subscribed if None)
            success: Whether task completed successfully

        Returns:
            bool: True if sent successfully
        """
        if not recipient_emails:
            recipient_emails = list(self.subscribed_emails)

        if not recipient_emails:
            logger.debug("No recipients for task completion notification")
            return False

        subject = f"{'✓' if success else '✗'} Task Completed: {task_name}"

        html_body = self._build_html_email(
            title=f"Task {'Completed' if success else 'Failed'}: {task_name}",
            content=f"""
                <p><strong>Agent:</strong> {agent_type}</p>
                <p><strong>Status:</strong> {'Success' if success else 'Failed'}</p>
                <p><strong>Completed At:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin-top: 15px;">
                    <p><strong>Result:</strong></p>
                    <pre style="overflow-x: auto; max-height: 300px;">{result}</pre>
                </div>
            """,
            status="success" if success else "error",
        )

        return self._send_email(
            subject=subject, html_body=html_body, recipient_emails=recipient_emails
        )

    def send_threshold_alert(
        self,
        task_name: str,
        metric_name: str,
        metric_value: float,
        threshold: float,
        unit: str = "%",
        recipient_emails: Optional[List[str]] = None,
    ) -> bool:
        """
        Send alert when a metric crosses a threshold.

        Args:
            task_name: Name of the monitoring task
            metric_name: Name of the metric (e.g., 'Disk Usage')
            metric_value: Current metric value
            threshold: Threshold value that was crossed
            unit: Unit of measurement
            recipient_emails: Optional list of recipients

        Returns:
            bool: True if sent successfully
        """
        if not recipient_emails:
            recipient_emails = list(self.subscribed_emails)

        if not recipient_emails:
            return False

        subject = f"⚠️ Alert: {metric_name} threshold exceeded - {metric_value}{unit}"

        html_body = self._build_html_email(
            title=f"Threshold Alert: {metric_name}",
            content=f"""
                <p><strong>Monitoring Task:</strong> {task_name}</p>
                <p><strong>Metric:</strong> {metric_name}</p>
                <p><strong>Current Value:</strong> <span style="color: #ef4444; font-weight: bold;">{metric_value}{unit}</span></p>
                <p><strong>Threshold:</strong> {threshold}{unit}</p>
                <p><strong>Alert Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            """,
            status="warning",
        )

        return self._send_email(
            subject=subject, html_body=html_body, recipient_emails=recipient_emails
        )

    def send_error_notification(
        self,
        task_name: str,
        error_message: str,
        error_type: str = "General Error",
        recipient_emails: Optional[List[str]] = None,
    ) -> bool:
        """
        Send error notification.

        Args:
            task_name: Task that failed
            error_message: Error message/details
            error_type: Type of error
            recipient_emails: Optional list of recipients

        Returns:
            bool: True if sent successfully
        """
        if not recipient_emails:
            recipient_emails = list(self.subscribed_emails)

        if not recipient_emails:
            return False

        subject = f"❌ Error in Task: {task_name}"

        html_body = self._build_html_email(
            title=f"Task Error: {task_name}",
            content=f"""
                <p><strong>Error Type:</strong> {error_type}</p>
                <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <div style="background: #fef2f2; padding: 15px; border-left: 4px solid #ef4444; border-radius: 5px; margin-top: 15px;">
                    <p><strong>Details:</strong></p>
                    <pre style="overflow-x: auto; max-height: 300px; color: #991b1b;">{error_message}</pre>
                </div>
            """,
            status="error",
        )

        return self._send_email(
            subject=subject, html_body=html_body, recipient_emails=recipient_emails
        )

    def send_custom_notification(
        self, subject: str, html_body: str, recipient_emails: Optional[List[str]] = None
    ) -> bool:
        """
        Send a custom notification.

        Args:
            subject: Email subject
            html_body: HTML body content
            recipient_emails: Optional list of recipients

        Returns:
            bool: True if sent successfully
        """
        if not recipient_emails:
            recipient_emails = list(self.subscribed_emails)

        return self._send_email(
            subject=subject, html_body=html_body, recipient_emails=recipient_emails
        )

    # ==================== Private Methods ====================

    def _send_email(
        self, subject: str, html_body: str, recipient_emails: List[str]
    ) -> bool:
        """
        Send email via SMTP.

        Args:
            subject: Email subject
            html_body: HTML body
            recipient_emails: List of recipient emails

        Returns:
            bool: True if sent successfully
        """
        if not self.smtp_enabled:
            logger.warning("SMTP not configured. Email notification skipped.")
            return False

        if not recipient_emails:
            logger.warning("No recipient emails provided")
            return False

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = ", ".join(recipient_emails)

            # Add HTML body
            html_part = MIMEText(html_body, "html")
            msg.attach(html_part)

            # Send via SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(
                f"Email sent successfully to {len(recipient_emails)} recipient(s)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _build_html_email(self, title: str, content: str, status: str = "info") -> str:
        """
        Build a formatted HTML email.

        Args:
            title: Email title
            content: HTML content
            status: Status type ('info', 'success', 'warning', 'error')

        Returns:
            str: Complete HTML email
        """
        status_colors = {
            "info": "#6366f1",
            "success": "#10b981",
            "warning": "#f59e0b",
            "error": "#ef4444",
        }

        status_color = status_colors.get(status, status_colors["info"])

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f9fafb;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, {status_color} 0%, rgba({int(status_color[1:3], 16)}, {int(status_color[3:5], 16)}, {int(status_color[5:7], 16)}, 0.8) 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
        }}
        .body {{
            padding: 30px;
        }}
        .footer {{
            background-color: #f3f4f6;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #6b7280;
            border-top: 1px solid #e5e7eb;
        }}
        pre {{
            background-color: #f3f4f6;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 12px;
        }}
        strong {{
            color: #1f2937;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
        </div>
        <div class="body">
            {content}
        </div>
        <div class="footer">
            <p>This is an automated notification from Ollash Agent</p>
            <p style="margin: 5px 0 0 0;">Do not reply to this email</p>
        </div>
    </div>
</body>
</html>
        """

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Simple email validation."""
        return "@" in email and "." in email.split("@")[1]

    def send_ui_notification(
        self,
        message: str,
        notification_type: str = "info",
        title: str = None,
        data: dict = None,
    ) -> bool:
        """
        Send a real-time notification to the UI via EventPublisher.

        Args:
            message: Notification message
            notification_type: Type of notification (info, warning, critical, success)
            title: Optional notification title
            data: Optional additional data to include

        Returns:
            True if notification was queued for sending
        """
        try:
            from backend.utils.core.event_publisher import EventPublisher

            publisher = EventPublisher()

            notification_data = {
                "message": message,
                "type": notification_type,
                "title": title or notification_type.upper(),
                "timestamp": datetime.now().isoformat(),
            }

            if data:
                notification_data.update(data)

            # Publish to UI alert channel
            publisher.publish("ui_alert", notification_data)
            logger.info(f"📢 UI notification sent: {title or message}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send UI notification: {e}")
            return False


# Global notification manager instance
_notification_manager = None


def get_notification_manager() -> NotificationManager:
    """Get or create the global notification manager instance."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
