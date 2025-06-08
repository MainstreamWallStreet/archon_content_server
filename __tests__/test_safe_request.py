import types
import time
import pytest
from googleapiclient.errors import HttpError
from src.gdrive.gdrive_helper import _safe_request


class DummyResp:
    def __init__(self, status):
        self.status = status


def make_http_error(status: int) -> HttpError:
    resp = types.SimpleNamespace(status=status, reason="", getheaders=lambda: {})
    return HttpError(resp, b"")


def test_safe_request_retries(monkeypatch):
    calls = []
    monkeypatch.setattr(time, "sleep", lambda s: calls.append(s))
    monkeypatch.setattr("random.random", lambda: 0)

    err = make_http_error(429)
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise err
        return "ok"

    out = _safe_request(fn, label="t", max_retries=5)
    assert out == "ok"
    assert attempts["n"] == 3
    assert calls[:2] == [1, 2]


def test_safe_request_non_retry(monkeypatch):
    err = make_http_error(404)

    def fn():
        raise err

    with pytest.raises(HttpError):
        _safe_request(fn, label="t", max_retries=3)
