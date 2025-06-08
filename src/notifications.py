"""SendGrid notification helper."""

from __future__ import annotations

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

import json

from src.config import get_setting


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
    from_email = get_setting("ALERT_FROM_EMAIL")
    mail = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        plain_text_content=message,
    )
    try:
        resp = SendGridAPIClient(api_key).send(mail)
    except Exception as exc:  # pragma: no cover - network
        raise RuntimeError(f"SendGrid error: {exc}") from exc
    if resp.status_code >= 400:
        raise RuntimeError(f"SendGrid error {resp.status_code}: {resp.body}")


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
    for addr in recipients:
        send_email(addr, subject, message)
