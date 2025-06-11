from fastapi.testclient import TestClient
from unittest.mock import patch

from src.banshee_api import app

API_KEY = "test"
HEADERS = {"X-API-Key": API_KEY}


def test_get_watchlist_endpoint():
    with patch("src.banshee_api.store") as store:
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
    ) as clean_calls:
        client = TestClient(app)
        resp = client.post(
            "/watchlist",
            headers=HEADERS,
            json={"ticker": "MSFT", "user": "griffin"},
        )
        assert resp.status_code == 200
        store.add_ticker.assert_called_with("MSFT", "griffin")
        assert refresh.called
        assert clean_email.called
        assert clean_calls.called


def test_send_global_alert_endpoint():
    with patch("src.banshee_api.send_alert") as send_alert:
        client = TestClient(app)
        payload = {"subject": "Hello", "message": "World"}
        resp = client.post("/send-global-alert", headers=HEADERS, json=payload)
        assert resp.status_code == 200
        send_alert.assert_called_with("Hello", "World")


def test_send_global_alert_requires_auth():
    client = TestClient(app)
    resp = client.post("/send-global-alert", json={"subject": "sub", "message": "body"})
    assert resp.status_code == 403


def test_delete_watchlist_endpoint():
    with patch("src.banshee_api.store") as store, patch(
        "src.banshee_api.calls_bucket"
    ) as calls_bucket, patch(
        "src.banshee_api.email_bucket"
    ) as email_bucket, patch(
        "src.banshee_api.cleanup_email_queue"
    ) as clean_email, patch(
        "src.banshee_api.cleanup_calls_queue"
    ) as clean_calls:
        store.list_tickers.return_value = ["AAPL", "MSFT"]
        calls_bucket.list_json.return_value = []
        email_bucket.list_json.return_value = []
        
        client = TestClient(app)
        resp = client.delete("/watchlist/AAPL", headers=HEADERS)
        assert resp.status_code == 200
        store.remove_ticker.assert_called_with("AAPL")
        assert clean_email.called
        assert clean_calls.called
        assert "AAPL removed from watchlist" in resp.json()["message"]
