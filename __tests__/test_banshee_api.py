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


def test_get_email_queue_endpoint():
    """Test the email queue endpoint returns data correctly."""
    with patch("src.banshee_api.email_bucket") as email_bucket, patch(
        "src.banshee_api.get_setting", side_effect=get_setting_side_effect
    ):
        # Mock the email bucket to return some test data
        email_bucket.list_json.return_value = [
            ("queue/AAPL/email1.json", {"ticker": "AAPL", "send_time": "2025-01-20T10:00:00Z"}),
            ("queue/MSFT/email2.json", {"ticker": "MSFT", "send_time": "2025-01-21T14:00:00Z"}),
        ]
        
        client = TestClient(app)
        resp = client.get("/email-queue", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert data["items"][0][0] == "queue/AAPL/email1.json"
        assert data["items"][0][1]["ticker"] == "AAPL"
        assert data["items"][1][0] == "queue/MSFT/email2.json"
        assert data["items"][1][1]["ticker"] == "MSFT"
        
        # Verify the correct prefix was used
        email_bucket.list_json.assert_called_once_with("queue/")


def test_get_earnings_endpoint():
    """Test the earnings endpoint returns data correctly."""
    with patch("src.banshee_api.calls_bucket") as calls_bucket, patch(
        "src.banshee_api.get_setting", side_effect=get_setting_side_effect
    ):
        # Mock the calls bucket to return some test data
        calls_bucket.list_json.return_value = [
            ("calls/AAPL/2025-01-20.json", {"ticker": "AAPL", "call_date": "2025-01-20"}),
            ("calls/MSFT/2025-01-21.json", {"ticker": "MSFT", "call_date": "2025-01-21"}),
        ]
        
        client = TestClient(app)
        resp = client.get("/earnings", headers=HEADERS)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert data["items"][0][0] == "calls/AAPL/2025-01-20.json"
        assert data["items"][0][1]["ticker"] == "AAPL"
        assert data["items"][1][0] == "calls/MSFT/2025-01-21.json"
        assert data["items"][1][1]["ticker"] == "MSFT"
        
        # Verify the correct prefix was used
        calls_bucket.list_json.assert_called_once_with("calls/")


def test_get_email_queue_endpoint_error_handling():
    """Test the email queue endpoint handles errors gracefully."""
    with patch("src.banshee_api.email_bucket") as email_bucket, patch(
        "src.banshee_api.get_setting", side_effect=get_setting_side_effect
    ):
        # Mock the email bucket to raise an exception
        email_bucket.list_json.side_effect = RuntimeError("GCS connection failed")
        
        client = TestClient(app)
        resp = client.get("/email-queue", headers=HEADERS)
        
        assert resp.status_code == 500
        data = resp.json()
        assert "detail" in data
        assert "GCS connection failed" in data["detail"]


def test_get_earnings_endpoint_error_handling():
    """Test the earnings endpoint handles errors gracefully."""
    with patch("src.banshee_api.calls_bucket") as calls_bucket, patch(
        "src.banshee_api.get_setting", side_effect=get_setting_side_effect
    ):
        # Mock the calls bucket to raise an exception
        calls_bucket.list_json.side_effect = RuntimeError("GCS connection failed")
        
        client = TestClient(app)
        resp = client.get("/earnings", headers=HEADERS)
        
        assert resp.status_code == 500
        data = resp.json()
        assert "detail" in data
        assert "GCS connection failed" in data["detail"]
