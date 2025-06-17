import json
import pytest
from unittest.mock import patch, AsyncMock
import httpx
from datetime import datetime


class InMemoryStore:
    def __init__(self):
        self.file = "[]"

    def list_tickers(self):
        return json.loads(self.file)

    def add_ticker(self, ticker: str, user: str | None = None):
        tickers = json.loads(self.file)
        t = ticker.upper()
        if t in tickers:
            raise ValueError("duplicate")
        tickers.append(t)
        self.file = json.dumps(tickers)

    def remove_ticker(self, ticker: str):
        tickers = json.loads(self.file)
        t = ticker.upper()
        if t not in tickers:
            raise ValueError("missing")
        tickers.remove(t)
        self.file = json.dumps(tickers)


@pytest.fixture(autouse=True)
def patch_store(monkeypatch):
    store = InMemoryStore()
    monkeypatch.setattr("src.banshee_api.store", store)
    return store


@pytest.fixture(autouse=True)
def patch_raven_url(monkeypatch):
    monkeypatch.setenv("RAVEN_URL", "http://test-raven")


def test_add_ticker_writes_array(client, patch_store):
    with patch("src.banshee_api._notify_raven", new_callable=AsyncMock):
        resp = client.post(
            "/watchlist", json={"ticker": "AAPL"}, headers={"X-API-Key": "secret"}
        )
        assert resp.status_code == 200
        assert patch_store.file == json.dumps(["AAPL"])


def test_add_duplicate_returns_409(client, patch_store):
    with patch("src.banshee_api._notify_raven", new_callable=AsyncMock):
        client.post("/watchlist", json={"ticker": "AAPL"}, headers={"X-API-Key": "secret"})
        resp = client.post(
            "/watchlist", json={"ticker": "AAPL"}, headers={"X-API-Key": "secret"}
        )
        assert resp.status_code == 409


def test_delete_ticker_updates_file(client, patch_store):
    with patch("src.banshee_api._notify_raven", new_callable=AsyncMock):
        client.post("/watchlist", json={"ticker": "AAPL"}, headers={"X-API-Key": "secret"})
        resp = client.delete("/watchlist/AAPL", headers={"X-API-Key": "secret"})
        assert resp.status_code == 200
        assert patch_store.file == "[]"


@pytest.mark.asyncio
async def test_notify_raven_success():
    """Test successful notification to Raven API."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    
    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        from src.banshee_api import _notify_raven
        await _notify_raven("AAPL", year=2024)
        
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://test-raven/process"
        assert call_args[1]["json"] == {
            "ticker": "AAPL",
            "year": 2024,
            "point_of_origin": "banshee",
            "include_transcript": True
        }


@pytest.mark.asyncio
async def test_notify_raven_http_error():
    """Test handling of HTTP errors from Raven API."""
    class MockResponse:
        async def raise_for_status(self):
            raise httpx.HTTPError("Test error")
    async def mock_post(*args, **kwargs):
        return MockResponse()
    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value = mock_client
    
    with patch("httpx.AsyncClient", return_value=mock_async_client):
        from src.banshee_api import _notify_raven
        with pytest.raises(RuntimeError, match="Failed to notify Raven for AAPL"):
            await _notify_raven("AAPL")


@pytest.mark.asyncio
async def test_notify_raven_unexpected_error():
    """Test handling of unexpected errors."""
    with patch("httpx.AsyncClient.post", side_effect=Exception("Unexpected error")):
        from src.banshee_api import _notify_raven
        with pytest.raises(RuntimeError, match="Unexpected error notifying Raven for AAPL"):
            await _notify_raven("AAPL")


@pytest.mark.asyncio
async def test_notify_raven_missing_url():
    """Test handling of missing RAVEN_URL environment variable."""
    with patch("src.banshee_api.get_setting", return_value=None):
        from src.banshee_api import _notify_raven
        with pytest.raises(RuntimeError, match="RAVEN_URL environment variable is not set"):
            await _notify_raven("AAPL")


@pytest.mark.asyncio
async def test_notify_raven_with_quarter():
    """Test notification with quarter parameter."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    
    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        from src.banshee_api import _notify_raven
        await _notify_raven("AAPL", year=2024, quarter=2)
        
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"] == {
            "ticker": "AAPL",
            "year": 2024,
            "point_of_origin": "banshee",
            "include_transcript": True,
            "quarter": 2
        }
