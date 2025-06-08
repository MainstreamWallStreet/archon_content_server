import json
from unittest.mock import Mock, patch

import pytest

from src.banshee_watchlist import BansheeStore


@pytest.fixture
def mock_storage_client():
    with patch("google.cloud.storage.Client") as mock_client:
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_bucket.exists.return_value = True
        yield mock_client


@pytest.fixture
def store(mock_storage_client):
    return BansheeStore("test-bucket")


def test_add_ticker_saves_json(store):
    store.add_ticker("AAPL", "griffin")
    store._bucket.blob.assert_called_with("watchlist/AAPL.json")
    assert store._bucket.blob.return_value.upload_from_string.called
    payload = store._bucket.blob.return_value.upload_from_string.call_args[0][0]
    data = json.loads(payload)
    assert data["name"] == "AAPL"
    assert data["created_by_user"] == "griffin"


def test_list_tickers_returns_names(store):
    mock_blob1 = Mock()
    mock_blob1.name = "watchlist/AAPL.json"
    mock_blob2 = Mock()
    mock_blob2.name = "watchlist/MSFT.json"
    store._client.list_blobs.return_value = [mock_blob1, mock_blob2]
    tickers = store.list_tickers()
    assert tickers == ["AAPL", "MSFT"]


def test_schedule_and_update_call(store):
    call = {
        "ticker": "AAPL",
        "call_date": "2025-07-30",
        "call_time": "2025-07-30T14:00:00Z",
        "status": "scheduled",
    }
    store.schedule_call(call)
    store._bucket.blob.assert_called_with("earnings_queue/AAPL/2025-07-30.json")
    store._bucket.blob.return_value.download_as_text.return_value = json.dumps(call)
    store.update_call_status("AAPL", "2025-07-30", "sent_to_raven")
    uploaded = store._bucket.blob.return_value.upload_from_string.call_args_list[-1][0][
        0
    ]
    assert json.loads(uploaded)["status"] == "sent_to_raven"
