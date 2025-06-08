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
    with patch("src.banshee_api.store") as store:
        client = TestClient(app)
        resp = client.post(
            "/watchlist",
            headers=HEADERS,
            json={"ticker": "MSFT", "user": "griffin"},
        )
        assert resp.status_code == 200
        store.add_ticker.assert_called_with("MSFT", "griffin")
