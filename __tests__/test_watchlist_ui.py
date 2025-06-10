from fastapi.testclient import TestClient
from src.banshee_api import app


def test_watchlist_ui_requires_auth(monkeypatch):
    client = TestClient(app)
    resp = client.get("/web")
    assert resp.status_code == 401


def test_watchlist_ui_ok(monkeypatch):
    monkeypatch.setenv("BANSHEE_WEB_PASSWORD", "testpass")
    monkeypatch.setenv("BANSHEE_API_KEY", "key")
    client = TestClient(app)
    resp = client.get("/web", auth=("user", "testpass"))
    assert resp.status_code == 200
