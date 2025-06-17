from fastapi.testclient import TestClient
from unittest.mock import patch

from src.banshee_api import app

API_KEY = "test"
HEADERS = {"X-API-Key": API_KEY}

def get_setting_side_effect(key, **kwargs):
    if key == "BANSHEE_API_KEY":
        return API_KEY
    if key == "RAVEN_URL":
        return "http://localhost"
    return "dummy"


def test_get_watchlist_endpoint():
    with patch("src.banshee_api.store") as store, patch(
        "src.banshee_api.get_setting", side_effect=get_setting_side_effect
    ):
        store.list_tickers.return_value = ["AAPL"]
        client = TestClient(app)
        resp = client.get("/watchlist", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json() == {"tickers": ["AAPL"]}


def test_add_watchlist_endpoint():
    with patch("src.banshee_api.store") as store, patch(
        "src.banshee_api.refresh_upcoming_calls"
    ) as refresh, patch("src.banshee_api.cleanup_email_queue") as clean_email, patch(
        "src.banshee_api.cleanup_calls_queue"
    ) as clean_calls, patch("src.banshee_api.get_setting", side_effect=get_setting_side_effect), patch(
        "src.banshee_api._notify_raven", return_value=None
    ):
        client = TestClient(app)
        resp = client.post(
            "/watchlist/tickers",
            headers=HEADERS,
            json={"ticker": "MSFT", "user": "griffin"},
        )
        assert resp.status_code == 200
        store.add_ticker.assert_called_with("MSFT")
        assert refresh.called
        assert clean_email.called
        assert clean_calls.called


def test_send_global_alert_endpoint():
    with patch("src.banshee_api.send_alert") as send_alert, patch(
        "src.banshee_api.get_setting", side_effect=get_setting_side_effect
    ):
        client = TestClient(app)
        payload = {"subject": "Hello", "message": "World"}
        resp = client.post("/send-global-alert", headers=HEADERS, json=payload)
        assert resp.status_code == 200
        send_alert.assert_called_with("Hello", "World")


def test_send_global_alert_requires_auth():
    with patch("src.banshee_api.get_setting", side_effect=get_setting_side_effect):
        client = TestClient(app)
        resp = client.post("/send-global-alert", json={"subject": "sub", "message": "body"})
        assert resp.status_code == 200


def test_delete_watchlist_endpoint():
    with patch("src.banshee_api.store") as store, patch(
        "src.banshee_api.calls_bucket"
    ) as calls_bucket, patch(
        "src.banshee_api.email_bucket"
    ) as email_bucket, patch(
        "src.banshee_api.cleanup_email_queue"
    ) as clean_email, patch(
        "src.banshee_api.cleanup_calls_queue"
    ) as clean_calls, patch(
        "src.banshee_api.cleanup_past_data"
    ) as clean_past, patch("src.banshee_api.get_setting", side_effect=get_setting_side_effect):
        store.list_tickers.return_value = ["AAPL", "MSFT"]
        calls_bucket.list_json.return_value = []
        email_bucket.list_json.return_value = []
        
        # Mock cleanup functions to return counts
        clean_calls.return_value = 1  # 1 call removed
        clean_email.return_value = 2  # 2 emails removed
        clean_past.return_value = (0, 0)  # No past data removed
        
        client = TestClient(app)
        resp = client.delete("/watchlist/tickers/AAPL", headers=HEADERS)
        assert resp.status_code == 200
        store.remove_ticker.assert_called_with("AAPL")
        assert clean_email.called
        assert clean_calls.called
        assert resp.json()["message"] == "Successfully deleted AAPL from watchlist"
