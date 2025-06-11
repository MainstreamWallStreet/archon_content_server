"""SendGrid notification helper."""

from __future__ import annotations

import json
import logging
import os

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from src.config import get_setting

logger = logging.getLogger(__name__)


class NotificationAgent:
    """Minimal email notification service."""

    def __init__(self, *, client: SendGridAPIClient, recipient: str) -> None:
        self.client = client
        self.recipient = recipient
        self.from_email = get_setting("ALERT_FROM_EMAIL", default="banshee@example.com")

    def send(self, subject: str, body: str) -> None:
        logger.info(
            "Attempting to send email to %s with subject: %s", self.recipient, subject
        )

        message = Mail(
            from_email=self.from_email,
            to_emails=self.recipient,
            subject=subject,
            plain_text_content=body,
        )

        try:
            resp = self.client.send(message)
            if resp.status_code >= 400:
                logger.error(
                    "SendGrid error %s for recipient %s: %s",
                    resp.status_code,
                    self.recipient,
                    resp.body,
                )
                raise RuntimeError(f"SendGrid error {resp.status_code}: {resp.body}")
            logger.info(
                "✅ Successfully sent email to %s (status: %s)",
                self.recipient,
                resp.status_code,
            )
        except Exception as e:
            logger.error("❌ Failed to send email to %s: %s", self.recipient, str(e))
            raise


def send_email(to_email: str, subject: str, message: str) -> None:
    """Send a notification email using SendGrid.

    NOTE: For sending alerts to multiple recipients, use send_alert() instead.
    This function is for single-recipient emails only.

    Parameters
    ----------
    to_email : str
        Recipient address.
    subject : str
        Email subject line.
    message : str
        Plain text body.

    Raises
    ------
    RuntimeError
        If the SendGrid API returns an error.
    """
    logger.info("🚨 Sending single email alert: '%s'", subject)
    logger.info("📤 Sending email to: %s", to_email)

    api_key = get_setting("SENDGRID_API_KEY")
    if not api_key:
        logger.error("❌ SENDGRID_API_KEY not configured - cannot send email")
        raise RuntimeError("SENDGRID_API_KEY not configured")

    client = SendGridAPIClient(api_key)
    agent = NotificationAgent(client=client, recipient=to_email)
    agent.send(subject, message)

    logger.info("✅ Single email sent successfully")


def send_alert(subject: str, message: str) -> None:
    """Send an alert email to all configured recipients.

    This is the preferred method for system alerts and notifications that should
    go to all administrators/stakeholders.

    Parameters
    ----------
    subject : str
        Subject line for the message.
    message : str
        Body text.
    """

    logger.info("🚨 Starting alert distribution: '%s'", subject)

    # Try to get recipients from environment variable
    recipients_json = get_setting("ALERT_RECIPIENTS", default="[]")
    logger.debug("Raw ALERT_RECIPIENTS value: %s", recipients_json)

    try:
        recipients = json.loads(recipients_json)
        if not isinstance(recipients, list):
            logger.error(
                "ALERT_RECIPIENTS must be a JSON array, got: %s",
                type(recipients).__name__,
            )
            raise RuntimeError(
                f"ALERT_RECIPIENTS must be a JSON array, got: {type(recipients).__name__}"
            )

        logger.info(
            "📧 Found %d recipient(s) for alert distribution: %s",
            len(recipients),
            recipients,
        )

        if not recipients:
            logger.warning(
                "⚠️  No recipients configured in ALERT_RECIPIENTS - alert will not be sent"
            )
            return

    except json.JSONDecodeError as exc:
        logger.error("❌ Invalid ALERT_RECIPIENTS JSON format: %s", exc)
        raise RuntimeError(f"Invalid ALERT_RECIPIENTS: {exc}") from exc

    api_key = get_setting("SENDGRID_API_KEY")
    if not api_key:
        logger.error("❌ SENDGRID_API_KEY not configured - cannot send alerts")
        raise RuntimeError("SENDGRID_API_KEY not configured")

    client = SendGridAPIClient(api_key)

    successful_sends = 0
    failed_sends = 0

    for addr in recipients:
        try:
            logger.info("📤 Sending alert to: %s", addr)
            agent = NotificationAgent(client=client, recipient=addr)
            agent.send(subject, message)
            successful_sends += 1
        except Exception as e:
            logger.error("❌ Failed to send alert to %s: %s", addr, str(e))
            failed_sends += 1
            # Continue trying to send to other recipients even if one fails

    logger.info(
        "✅ Alert distribution complete: %d successful, %d failed out of %d total recipients",
        successful_sends,
        failed_sends,
        len(recipients),
    )

    if failed_sends > 0:
        logger.warning(
            "⚠️  %d email(s) failed to send - check logs above for details", failed_sends
        )

    if successful_sends == 0:
        raise RuntimeError(f"All {len(recipients)} alert emails failed to send")


# Backward compatibility aliases - these will be deprecated in future versions
def send_notification_email(to_email: str, subject: str, message: str) -> None:
    """DEPRECATED: Use send_email() instead. This alias will be removed in a future version."""
    logger.warning("send_notification_email() is deprecated - use send_email() instead")
    send_email(to_email, subject, message)


def broadcast_alert(subject: str, message: str) -> None:
    """DEPRECATED: Use send_alert() instead. This alias will be removed in a future version."""
    logger.warning("broadcast_alert() is deprecated - use send_alert() instead")
    send_alert(subject, message)
