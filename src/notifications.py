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
        self.from_email = os.getenv("ALERT_FROM_EMAIL", "banshee@example.com")

    def send(self, subject: str, body: str) -> None:
        message = Mail(
            from_email=self.from_email,
            to_emails=self.recipient,
            subject=subject,
            plain_text_content=body,
        )
        resp = self.client.send(message)
        if resp.status_code >= 400:
            raise RuntimeError(f"SendGrid error {resp.status_code}: {resp.body}")
        logger.info("sent email to %s", self.recipient)


def send_email(to_email: str, subject: str, message: str) -> None:
    """Send a notification email using SendGrid.

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

    api_key = get_setting("SENDGRID_API_KEY")
    client = SendGridAPIClient(api_key)
    agent = NotificationAgent(client=client, recipient=to_email)
    agent.send(subject, message)


def send_alert(subject: str, message: str) -> None:
    """Send an alert email to all configured recipients.

    Parameters
    ----------
    subject : str
        Subject line for the message.
    message : str
        Body text.
    """

    recipients_json = get_setting("ALERT_RECIPIENTS", default="[]")
    try:
        recipients = json.loads(recipients_json)
    except json.JSONDecodeError as exc:  # pragma: no cover - misconfig
        raise RuntimeError(f"Invalid ALERT_RECIPIENTS: {exc}") from exc
    api_key = get_setting("SENDGRID_API_KEY")
    client = SendGridAPIClient(api_key)
    for addr in recipients:
        NotificationAgent(client=client, recipient=addr).send(subject, message)
