import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
from datetime import datetime
from fastapi.testclient import TestClient
from src.banshee_api import app, store, calls_bucket, email_bucket
import os
from dotenv import load_dotenv
from src.banshee_api import _notify_raven
import time

load_dotenv()

API_KEY = os.getenv("BANSHEE_API_KEY")
if not API_KEY:
    raise RuntimeError("BANSHEE_API_KEY not found in .env file.")

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


@pytest.mark.asyncio
async def test_notify_raven_success():
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json.return_value = {"status": "success"}
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_async_client):
        await _notify_raven("AAPL")
        assert mock_response.raise_for_status.await_count == 1


@pytest.mark.asyncio
async def test_notify_raven_http_error():
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock(side_effect=httpx.HTTPError("Test error"))
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_async_client):
        with pytest.raises(RuntimeError, match="Failed to notify Raven for AAPL"):
            await _notify_raven("AAPL")


@pytest.mark.asyncio
async def test_notify_raven_unexpected_error():
    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("Unexpected error")
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_async_client):
        with pytest.raises(RuntimeError, match="Unexpected error notifying Raven for AAPL"):
            await _notify_raven("AAPL")


@pytest.mark.asyncio
async def test_notify_raven_missing_url():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(RuntimeError, match="Unexpected error notifying Raven for AAPL: Missing required setting: RAVEN_API_KEY"):
            await _notify_raven("AAPL")


@pytest.mark.asyncio
async def test_notify_raven_with_quarter():
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json.return_value = {"status": "success"}
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_async_client):
        await _notify_raven("AAPL", quarter="Q1")
        assert mock_response.raise_for_status.await_count == 1


@pytest.mark.asyncio
async def test_notify_raven_sends_api_key():
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json.return_value = {"status": "success"}
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__.return_value = mock_client
    with patch("httpx.AsyncClient", return_value=mock_async_client):
        await _notify_raven("AAPL")
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args[1]
        assert "headers" in call_kwargs
        assert "X-API-Key" in call_kwargs["headers"]


client = TestClient(app)

@pytest.fixture
def mock_store():
    with patch("src.banshee_api.store") as mock:
        mock.list_tickers.return_value = []  # Start with empty list
        mock.add_ticker = MagicMock()
        mock.remove_ticker = MagicMock()
        yield mock

@pytest.fixture
def mock_cleanup():
    with patch("src.banshee_api.cleanup_calls_queue", return_value=0) as mock_calls, \
         patch("src.banshee_api.cleanup_email_queue", return_value=0) as mock_email:
        yield mock_calls, mock_email

@pytest.fixture
def mock_raven():
    with patch("src.banshee_api._notify_raven") as mock:
        yield mock

def test_create_ticker_success(mock_store, mock_cleanup, mock_raven):
    """Test successful creation of a ticker."""
    start_time = time.time()
    response = client.post(
        "/watchlist/tickers",
        json={"ticker": "AAPL"},
        headers={"X-API-Key": API_KEY}
    )
    end_time = time.time()
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully added AAPL to watchlist"}
    mock_store.add_ticker.assert_called_once_with("AAPL")
    mock_raven.assert_called_once()
    assert end_time - start_time < 1.0

def test_create_ticker_duplicate(mock_store):
    """Test creating a duplicate ticker returns 409."""
    mock_store.list_tickers.return_value = ["AAPL"]
    response = client.post(
        "/watchlist/tickers",
        json={"ticker": "AAPL"},
        headers={"X-API-Key": API_KEY}
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]

def test_create_ticker_raven_failure(mock_store, mock_cleanup, mock_raven):
    """Test that ticker is still created even if Raven notification fails."""
    mock_raven.side_effect = Exception("Raven notification failed")
    response = client.post(
        "/watchlist/tickers",
        json={"ticker": "AAPL"},
        headers={"X-API-Key": API_KEY}
    )
    assert response.status_code == 200
    mock_store.add_ticker.assert_called_once_with("AAPL")

def test_delete_ticker_success(mock_store, mock_cleanup):
    """Test successful deletion of a ticker."""
    mock_store.list_tickers.return_value = ["AAPL"]
    start_time = time.time()
    response = client.delete(
        "/watchlist/tickers/AAPL",
        headers={"X-API-Key": API_KEY}
    )
    end_time = time.time()
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully deleted AAPL from watchlist"}
    mock_store.remove_ticker.assert_called_once_with("AAPL")
    mock_cleanup[0].assert_called_once()
    mock_cleanup[1].assert_called_once()
    assert end_time - start_time < 1.0

def test_delete_ticker_not_found(mock_store):
    """Test deleting a non-existent ticker returns 404."""
    mock_store.list_tickers.return_value = []
    response = client.delete(
        "/watchlist/tickers/AAPL",
        headers={"X-API-Key": API_KEY}
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

def test_list_tickers_success(mock_store):
    """Test successful listing of tickers."""
    mock_store.list_tickers.return_value = ["AAPL", "MSFT"]
    start_time = time.time()
    response = client.get(
        "/watchlist/tickers",
        headers={"X-API-Key": API_KEY}
    )
    end_time = time.time()
    assert response.status_code == 200
    assert response.json() == {"tickers": ["AAPL", "MSFT"]}
    assert end_time - start_time < 1.0

def test_endpoints_require_auth():
    """Test that all endpoints require authentication."""
    endpoints = [
        ("POST", "/watchlist/tickers", {"ticker": "AAPL"}),
        ("DELETE", "/watchlist/tickers/AAPL", None),
        ("GET", "/watchlist/tickers", None)
    ]
    for method, endpoint, json_data in endpoints:
        response = client.request(
            method,
            endpoint,
            json=json_data if json_data else None
        )
        assert response.status_code == 403
        assert "Not authenticated" in response.json()["detail"]

def test_endpoints_invalid_auth():
    """Test that invalid API key is rejected."""
    endpoints = [
        ("POST", "/watchlist/tickers", {"ticker": "AAPL"}),
        ("DELETE", "/watchlist/tickers/AAPL", None),
        ("GET", "/watchlist/tickers", None)
    ]
    for method, endpoint, json_data in endpoints:
        response = client.request(
            method,
            endpoint,
            json=json_data if json_data else None,
            headers={"X-API-Key": "invalid-key"}
        )
        assert response.status_code == 403
        assert "Invalid API key" in response.json()["detail"]
