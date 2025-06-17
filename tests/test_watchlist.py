import json
import pytest


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


def test_add_ticker_writes_array(client, patch_store):
    resp = client.post(
        "/watchlist", json={"ticker": "AAPL"}, headers={"X-API-Key": "secret"}
    )
    assert resp.status_code == 200
    assert patch_store.file == json.dumps(["AAPL"])


def test_add_duplicate_returns_409(client, patch_store):
    client.post("/watchlist", json={"ticker": "AAPL"}, headers={"X-API-Key": "secret"})
    resp = client.post(
        "/watchlist", json={"ticker": "AAPL"}, headers={"X-API-Key": "secret"}
    )
    assert resp.status_code == 409


def test_delete_ticker_updates_file(client, patch_store):
    client.post("/watchlist", json={"ticker": "AAPL"}, headers={"X-API-Key": "secret"})
    resp = client.delete("/watchlist/AAPL", headers={"X-API-Key": "secret"})
    assert resp.status_code == 200
    assert patch_store.file == "[]"
