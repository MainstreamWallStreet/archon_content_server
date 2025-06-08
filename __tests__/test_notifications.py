from unittest.mock import MagicMock, patch

import pytest

from src.notifications import send_email, send_alert


def test_send_email_success():
    fake_client = MagicMock()
    fake_client.send.return_value.status_code = 202
    log = MagicMock()
    with patch("src.notifications.SendGridAPIClient", return_value=fake_client), patch(
        "src.notifications.get_setting", side_effect=lambda k: "x"
    ), patch("src.notifications.logger", log):
        send_email("user@example.com", "subj", "body")
        fake_client.send.assert_called()
        log.info.assert_called_with("sent email to %s", "user@example.com")


def test_send_email_failure():
    fake_client = MagicMock()
    fake_client.send.return_value.status_code = 500
    with patch("src.notifications.SendGridAPIClient", return_value=fake_client), patch(
        "src.notifications.get_setting", side_effect=lambda k: "x"
    ):
        with pytest.raises(RuntimeError):
            send_email("user@example.com", "subj", "body")


def test_send_alert_all_recipients():
    def _settings(name: str, *_, **__):
        if name == "ALERT_RECIPIENTS":
            return '["a@example.com","b@example.com"]'
        return "x"

    fake_client = MagicMock()
    fake_client.send.return_value.status_code = 202
    log = MagicMock()
    with patch("src.notifications.SendGridAPIClient", return_value=fake_client), patch(
        "src.notifications.get_setting", side_effect=_settings
    ), patch("src.notifications.logger", log):
        send_alert("subj", "body")
        assert fake_client.send.call_count == 2
        log.info.assert_any_call("sent email to %s", "a@example.com")
        log.info.assert_any_call("sent email to %s", "b@example.com")
