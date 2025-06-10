from unittest.mock import MagicMock, patch

import pytest

from src.notifications import send_email, send_alert


def test_send_email_success():
    fake_client = MagicMock()
    fake_client.send.return_value.status_code = 202
    log = MagicMock()
    with patch("src.notifications.SendGridAPIClient", return_value=fake_client), patch(
        "src.notifications.get_setting", side_effect=lambda k, **kwargs: "x"
    ), patch("src.notifications.logger", log):
        send_email("user@example.com", "subj", "body")
        fake_client.send.assert_called()
        log.info.assert_any_call("Attempting to send email to %s with subject: %s", "user@example.com", "subj")
        log.info.assert_any_call("✅ Successfully sent email to %s (status: %s)", "user@example.com", 202)


def test_send_email_failure():
    fake_client = MagicMock()
    fake_client.send.return_value.status_code = 500
    fake_client.send.return_value.body = "Internal Server Error"
    with patch("src.notifications.SendGridAPIClient", return_value=fake_client), patch(
        "src.notifications.get_setting", side_effect=lambda k, **kwargs: "x"
    ):
        with pytest.raises(RuntimeError):
            send_email("user@example.com", "subj", "body")


def test_send_alert_all_recipients():
    def _settings(name: str, *_, **kwargs):
        if name == "ALERT_RECIPIENTS":
            return '["a@example.com","b@example.com"]'
        if name == "ALERT_FROM_EMAIL":
            return "alerts@example.com"
        return "x"

    fake_client = MagicMock()
    fake_client.send.return_value.status_code = 202
    log = MagicMock()
    with patch("src.notifications.SendGridAPIClient", return_value=fake_client), patch(
        "src.notifications.get_setting", side_effect=_settings
    ), patch("src.notifications.logger", log):
        send_alert("subj", "body")
        assert fake_client.send.call_count == 2
        log.info.assert_any_call("🚨 Starting alert distribution: '%s'", "subj")
        log.info.assert_any_call("📧 Found %d recipient(s) for alert distribution: %s", 2, ["a@example.com","b@example.com"])
        log.info.assert_any_call("📤 Sending alert to: %s", "a@example.com")
        log.info.assert_any_call("📤 Sending alert to: %s", "b@example.com")
        log.info.assert_any_call("✅ Alert distribution complete: %d successful, %d failed out of %d total recipients", 2, 0, 2)


def test_send_alert_no_recipients():
    def _settings(name: str, *_, **kwargs):
        if name == "ALERT_RECIPIENTS":
            return '[]'
        return "x"

    log = MagicMock()
    with patch("src.notifications.get_setting", side_effect=_settings), patch("src.notifications.logger", log):
        send_alert("subj", "body")
        log.warning.assert_any_call("⚠️  No recipients configured in ALERT_RECIPIENTS - alert will not be sent")


def test_send_alert_invalid_json():
    def _settings(name: str, *_, **kwargs):
        if name == "ALERT_RECIPIENTS":
            return 'invalid json'
        return "x"

    with patch("src.notifications.get_setting", side_effect=_settings):
        with pytest.raises(RuntimeError, match="Invalid ALERT_RECIPIENTS"):
            send_alert("subj", "body")


def test_send_alert_partial_failure():
    def _settings(name: str, *_, **kwargs):
        if name == "ALERT_RECIPIENTS":
            return '["good@example.com","bad@example.com"]'
        if name == "ALERT_FROM_EMAIL":
            return "alerts@example.com"
        return "x"

    fake_client = MagicMock()
    # First call succeeds, second call fails
    fake_client.send.side_effect = [
        MagicMock(status_code=202),  # Success for first email
        Exception("SendGrid error")  # Failure for second email
    ]
    
    log = MagicMock()
    with patch("src.notifications.SendGridAPIClient", return_value=fake_client), patch(
        "src.notifications.get_setting", side_effect=_settings
    ), patch("src.notifications.logger", log):
        send_alert("subj", "body")
        log.info.assert_any_call("✅ Alert distribution complete: %d successful, %d failed out of %d total recipients", 1, 1, 2)
        log.warning.assert_any_call("⚠️  %d email(s) failed to send - check logs above for details", 1)
