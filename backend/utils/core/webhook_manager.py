"""
Webhook Manager - Send notifications to external services (Slack, Discord, Teams).

Extends NotificationManager with webhook-based communication for:
- Slack channels
- Discord servers
- Microsoft Teams channels
- Custom webhooks
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class WebhookType(Enum):
    """Supported webhook platforms."""

    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    CUSTOM = "custom"


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint."""

    name: str
    webhook_type: WebhookType
    webhook_url: str
    enabled: bool = True
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    timeout_seconds: int = 10
    headers: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


class WebhookManager:
    """
    Manages notifications sent to external webhook services.

    Features:
    - Multi-platform support (Slack, Discord, Teams)
    - Automatic retry with exponential backoff
    - Rich message formatting
    - Async request handling
    - Failed delivery logging
    """

    def __init__(self):
        """Initialize the webhook manager."""
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.failed_deliveries: List[Dict[str, Any]] = []
        self.max_failed_deliveries_log = 100  # Keep last 100 failures
        self._load_webhooks_from_env()
        logger.info("WebhookManager initialized")

    def _load_webhooks_from_env(self) -> None:
        """Load webhook configurations from environment variables."""
        try:
            # Check for webhook URLs in environment
            if slack_url := os.environ.get("WEBHOOK_SLACK_URL"):
                self.register_webhook(
                    name="default_slack",
                    webhook_type=WebhookType.SLACK,
                    webhook_url=slack_url,
                )

            if discord_url := os.environ.get("WEBHOOK_DISCORD_URL"):
                self.register_webhook(
                    name="default_discord",
                    webhook_type=WebhookType.DISCORD,
                    webhook_url=discord_url,
                )

            if teams_url := os.environ.get("WEBHOOK_TEAMS_URL"):
                self.register_webhook(
                    name="default_teams",
                    webhook_type=WebhookType.TEAMS,
                    webhook_url=teams_url,
                )

            logger.info(f"Loaded {len(self.webhooks)} webhooks from environment")

        except Exception as e:
            logger.warning(f"Failed to load webhooks from env: {e}")

    def register_webhook(
        self,
        name: str,
        webhook_type: WebhookType,
        webhook_url: str,
        retry_attempts: int = 3,
        retry_delay_seconds: int = 5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Register a new webhook endpoint.

        Args:
            name: Unique name for this webhook
            webhook_type: Type of webhook (Slack, Discord, etc.)
            webhook_url: Full URL of the webhook endpoint
            retry_attempts: Number of retry attempts on failure
            retry_delay_seconds: Initial delay between retries
            metadata: Optional metadata for the webhook

        Returns:
            bool: True if registered successfully
        """
        try:
            if not webhook_url.startswith(("http://", "https://")):
                logger.error(f"Invalid webhook URL for {name}: {webhook_url}")
                return False

            config = WebhookConfig(
                name=name,
                webhook_type=webhook_type,
                webhook_url=webhook_url,
                retry_attempts=retry_attempts,
                retry_delay_seconds=retry_delay_seconds,
                metadata=metadata or {},
            )

            self.webhooks[name] = config
            logger.info(f"Webhook registered: {name} ({webhook_type.value})")
            return True

        except Exception as e:
            logger.error(f"Failed to register webhook {name}: {e}")
            return False

    def unregister_webhook(self, name: str) -> bool:
        """Unregister a webhook."""
        if name in self.webhooks:
            del self.webhooks[name]
            logger.info(f"Webhook unregistered: {name}")
            return True
        return False

    async def send_to_webhook(
        self,
        webhook_name: str,
        message: str,
        title: Optional[str] = None,
        priority: MessagePriority = MessagePriority.MEDIUM,
        color: Optional[str] = None,
        fields: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Send a message to a registered webhook.

        Args:
            webhook_name: Name of the registered webhook
            message: Main message content
            title: Optional title
            priority: Message priority level
            color: Optional color for formatted messages
            fields: Optional additional fields to include

        Returns:
            bool: True if sent successfully
        """
        if webhook_name not in self.webhooks:
            logger.error(f"Webhook not found: {webhook_name}")
            return False

        webhook = self.webhooks[webhook_name]
        if not webhook.enabled:
            logger.warning(f"Webhook is disabled: {webhook_name}")
            return False

        payload = self._build_payload(
            webhook.webhook_type,
            message=message,
            title=title,
            priority=priority,
            color=color,
            fields=fields,
        )

        return await self._send_with_retry(webhook, payload)

    async def send_to_all_webhooks(
        self,
        message: str,
        title: Optional[str] = None,
        priority: MessagePriority = MessagePriority.MEDIUM,
        webhook_types: Optional[List[WebhookType]] = None,
    ) -> Dict[str, bool]:
        """
        Send a message to all or specific webhook types.

        Args:
            message: Message content
            title: Optional title
            priority: Message priority
            webhook_types: If specified, only send to these types

        Returns:
            Dict: Mapping of webhook names to success status
        """
        results = {}
        tasks = []

        for name, webhook in self.webhooks.items():
            # Skip if webhook_types specified and this webhook type not included
            if webhook_types and webhook.webhook_type not in webhook_types:
                continue

            if not webhook.enabled:
                results[name] = False
                continue

            payload = self._build_payload(webhook.webhook_type, message=message, title=title, priority=priority)

            tasks.append(
                self._send_with_retry(webhook, payload).then(lambda success, n=name: results.update({n: success}))
            )

        # Execute all sends concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return results if results else {name: False for name in self.webhooks.keys()}

    def send_to_webhook_sync(
        self,
        webhook_name: str,
        message: str,
        title: Optional[str] = None,
        priority: MessagePriority = MessagePriority.MEDIUM,
        color: Optional[str] = None,
        fields: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Synchronous version of send_to_webhook (convenience wrapper).

        Args:
            webhook_name: Name of the registered webhook
            message: Main message content
            title: Optional title
            priority: Message priority level
            color: Optional color for formatted messages
            fields: Optional additional fields

        Returns:
            bool: True if sent successfully
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, use sync send
                return self._send_webhook_sync_internal(webhook_name, message, title, priority, color, fields)
            else:
                return loop.run_until_complete(
                    self.send_to_webhook(webhook_name, message, title, priority, color, fields)
                )
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.send_to_webhook(webhook_name, message, title, priority, color, fields))

    def _send_webhook_sync_internal(
        self,
        webhook_name: str,
        message: str,
        title: Optional[str] = None,
        priority: MessagePriority = MessagePriority.MEDIUM,
        color: Optional[str] = None,
        fields: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Internal synchronous send using requests library."""
        try:
            import requests

            if webhook_name not in self.webhooks:
                return False

            webhook = self.webhooks[webhook_name]
            payload = self._build_payload(
                webhook.webhook_type,
                message=message,
                title=title,
                priority=priority,
                color=color,
                fields=fields,
            )

            response = requests.post(
                webhook.webhook_url,
                json=payload,
                timeout=webhook.timeout_seconds,
                headers=webhook.headers or {},
            )

            if response.status_code in (200, 201, 204):
                logger.info(f"Message sent to {webhook_name}")
                return True
            else:
                self._log_failed_delivery(webhook_name, response.status_code, response.text)
                return False

        except Exception as e:
            logger.error(f"Failed to send to {webhook_name}: {e}")
            self._log_failed_delivery(webhook_name, "exception", str(e))
            return False

    async def _send_with_retry(self, webhook: WebhookConfig, payload: Dict[str, Any]) -> bool:
        """Send message to webhook with retry logic."""
        last_error = None

        for attempt in range(webhook.retry_attempts):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        webhook.webhook_url,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(seconds=webhook.timeout_seconds),
                        headers=webhook.headers or {"Content-Type": "application/json"},
                    ) as response:
                        if response.status in (200, 201, 204):
                            logger.info(f"Message sent to {webhook.name} (attempt {attempt + 1})")
                            return True
                        else:
                            text = await response.text()
                            self._log_failed_delivery(webhook.name, response.status, text)
                            last_error = f"HTTP {response.status}"

            except asyncio.TimeoutError:
                last_error = "Request timeout"
            except Exception as e:
                last_error = str(e)

            # Wait before retry (exponential backoff)
            if attempt < webhook.retry_attempts - 1:
                wait_time = webhook.retry_delay_seconds * (2**attempt)
                logger.warning(f"Retry {attempt + 1}/{webhook.retry_attempts} for {webhook.name} in {wait_time}s")
                await asyncio.sleep(wait_time)

        logger.error(f"Failed to send to {webhook.name} after {webhook.retry_attempts} attempts: {last_error}")
        return False

    # ==================== Message Format Builders ====================

    def _build_payload(
        self,
        webhook_type: WebhookType,
        message: str,
        title: Optional[str] = None,
        priority: MessagePriority = MessagePriority.MEDIUM,
        color: Optional[str] = None,
        fields: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Build payload for the specific webhook format."""

        color = color or self._get_color_for_priority(priority)

        if webhook_type == WebhookType.SLACK:
            return self._build_slack_payload(message, title, color, fields)
        elif webhook_type == WebhookType.DISCORD:
            return self._build_discord_payload(message, title, color, fields)
        elif webhook_type == WebhookType.TEAMS:
            return self._build_teams_payload(message, title, color, fields)
        else:
            return {
                "message": message,
                "title": title,
                "color": color,
                "fields": fields,
            }

    def _build_slack_payload(
        self,
        message: str,
        title: Optional[str] = None,
        color: str = "#808080",
        fields: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Build Slack message format (Block Kit)."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*\n{message}" if title else message,
                },
            }
        ]

        if fields:
            field_blocks = [{"type": "mrkdwn", "text": f"*{k}*\n{v}"} for k, v in fields.items()]
            if field_blocks:
                blocks.append({"type": "section", "fields": field_blocks})

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_Ollash Agent | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
                    }
                ],
            }
        )

        return {"blocks": blocks}

    def _build_discord_payload(
        self,
        message: str,
        title: Optional[str] = None,
        color: str = "#808080",
        fields: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Build Discord embed format."""

        # Convert hex color to decimal for Discord
        color_int = int(color.lstrip("#"), 16)

        embed = {
            "title": title or "Ollash Notification",
            "description": message,
            "color": color_int,
            "timestamp": datetime.now().isoformat(),
        }

        if fields:
            embed["fields"] = [{"name": k, "value": v, "inline": len(str(v)) < 50} for k, v in fields.items()]

        embed["footer"] = {"text": "Ollash Agent"}

        return {"embeds": [embed]}

    def _build_teams_payload(
        self,
        message: str,
        title: Optional[str] = None,
        color: str = "#808080",
        fields: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Build Microsoft Teams Adaptive Card format."""

        body = [
            {
                "type": "TextBlock",
                "text": title or "Ollash Notification",
                "weight": "bolder",
                "size": "large",
            },
            {"type": "TextBlock", "text": message, "wrap": True},
        ]

        if fields:
            facts = [{"name": k, "value": v} for k, v in fields.items()]
            body.append({"type": "FactSet", "facts": facts})

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": body,
            "msTeams": {"width": "Full"},
        }

    @staticmethod
    def _get_color_for_priority(priority: MessagePriority) -> str:
        """Get hex color for priority level."""
        colors = {
            MessagePriority.LOW: "#3b82f6",  # Blue
            MessagePriority.MEDIUM: "#f59e0b",  # Amber
            MessagePriority.HIGH: "#ef5350",  # Red
            MessagePriority.CRITICAL: "#8b0000",  # Dark Red
        }
        return colors.get(priority, "#808080")

    # ==================== Logging & Diagnostics ====================

    def _log_failed_delivery(self, webhook_name: str, error_code: Any, error_details: str) -> None:
        """Log a failed delivery attempt."""
        failure = {
            "webhook": webhook_name,
            "timestamp": datetime.now().isoformat(),
            "error_code": str(error_code),
            "error_details": error_details[:200],  # Truncate for storage
        }

        self.failed_deliveries.append(failure)

        # Keep only the last N failures
        if len(self.failed_deliveries) > self.max_failed_deliveries_log:
            self.failed_deliveries = self.failed_deliveries[-self.max_failed_deliveries_log :]

        logger.warning(f"Failed delivery to {webhook_name}: {error_code}")

    def get_failed_deliveries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get the most recent failed deliveries."""
        return self.failed_deliveries[-limit:]

    def get_webhook_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered webhooks."""
        return {
            name: {
                "enabled": webhook.enabled,
                "type": webhook.webhook_type.value,
                "last_attempt": None,  # Would be tracked in production
                "success_count": 0,  # Would be tracked in production
            }
            for name, webhook in self.webhooks.items()
        }


# Global instance
_webhook_manager = None


def get_webhook_manager() -> WebhookManager:
    """Get or create the global webhook manager instance."""
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager
