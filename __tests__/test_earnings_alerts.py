import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.earnings_alerts import (
    GcsBucket,
    refresh_upcoming_calls,
    cleanup_email_queue,
    cleanup_calls_queue,
    send_due_emails,
)


@pytest.fixture
def buckets():
    with patch("src.earnings_alerts.storage.Client") as client:
        call_bucket = MagicMock()
        email_bucket = MagicMock()
        client.return_value.bucket.side_effect = [call_bucket, email_bucket]
        call_bucket.exists.return_value = True
        email_bucket.exists.return_value = True
        yield call_bucket, email_bucket


def _fake_fetch(ticker: str):
    return [{"earnings_date": "2025-07-30T15:00:00Z"}]


@pytest.mark.asyncio
async def test_refresh_upcoming_calls_creates_objects(buckets):
    call_bucket, email_bucket = buckets
    store = MagicMock()
    store.list_tickers.return_value = ["AAPL"]
    fetcher = AsyncMock(side_effect=_fake_fetch)
    await refresh_upcoming_calls(
        store,
        GcsBucket("calls-b"),
        GcsBucket("email-b"),
        fetcher=fetcher,
    )
    call_bucket.blob.assert_called_with("calls/AAPL/2025-07-30.json")
    assert email_bucket.blob.call_count == 2  # one_week and tomorrow reminders


def test_cleanup_email_queue_removes_unknown(buckets):
    _, _ = buckets
    bucket = GcsBucket("email-b")
    with patch.object(
        bucket,
        "list_json",
        return_value=[
            ("queue/MSFT/x.json", {"ticker": "MSFT"}),
            ("queue/AAPL/y.json", {"ticker": "AAPL"}),
        ],
    ), patch.object(bucket, "delete") as delete:
        cleanup_email_queue(bucket, {"AAPL"})
        delete.assert_called_once_with("queue/MSFT/x.json")


def test_cleanup_calls_queue_removes_unknown(buckets):
    _, _ = buckets
    bucket = GcsBucket("calls-b")
    with patch.object(
        bucket,
        "list_json",
        return_value=[
            ("calls/MSFT/2025-08-01.json", {"ticker": "MSFT"}),
            ("calls/AAPL/2025-08-02.json", {"ticker": "AAPL"}),
        ],
    ), patch.object(bucket, "delete") as delete:
        cleanup_calls_queue(bucket, {"AAPL"})
        delete.assert_called_once_with("calls/MSFT/2025-08-01.json")


def test_send_due_emails_dispatches(buckets):
    _, _ = buckets
    now = datetime(2025, 7, 29, 15, 0, tzinfo=timezone.utc)
    bucket = GcsBucket("email-b")
    with patch.object(
        bucket,
        "list_json",
        return_value=[
            (
                "queue/AAPL/x.json",
                {
                    "ticker": "AAPL",
                    "call_time": "2025-07-30T15:00:00+00:00",
                    "send_time": "2025-07-29T15:30:00+00:00",
                    "kind": "tomorrow",
                },
            )
        ],
    ), patch.object(bucket, "delete") as delete, patch(
        "src.earnings_alerts.send_alert"
    ) as send_alert:
        send_due_emails(bucket, now=now)
        send_alert.assert_called_once()
        delete.assert_called_once()
