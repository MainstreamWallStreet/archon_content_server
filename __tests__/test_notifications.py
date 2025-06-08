from unittest.mock import MagicMock, patch

import pytest

from src.notifications import send_email, send_alert


def test_send_email_success():
    fake_client = MagicMock()
    fake_client.send.return_value.status_code = 202
    with patch("src.notifications.SendGridAPIClient", return_value=fake_client), patch(
        "src.notifications.get_setting", side_effect=lambda k: "x"
    ):
        send_email("user@example.com", "subj", "body")
        fake_client.send.assert_called()


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

    with patch("src.notifications.send_email") as send_mock, patch(
        "src.notifications.get_setting", side_effect=_settings
    ):
        send_alert("subj", "body")
        send_mock.assert_any_call("a@example.com", "subj", "body")
        send_mock.assert_any_call("b@example.com", "subj", "body")
        assert send_mock.call_count == 2
