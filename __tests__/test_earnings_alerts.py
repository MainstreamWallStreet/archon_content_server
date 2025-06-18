import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.earnings_alerts import (
    GcsBucket,
    refresh_upcoming_calls,
    cleanup_email_queue,
    cleanup_calls_queue,
    cleanup_past_data,
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
    assert email_bucket.blob.call_count == 3  # one_week, tomorrow, and one_hour reminders


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
        removed_count = cleanup_email_queue(bucket, {"AAPL"})
        delete.assert_called_once_with("queue/MSFT/x.json")
        assert removed_count == 1


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
        removed_count = cleanup_calls_queue(bucket, {"AAPL"})
        delete.assert_called_once_with("calls/MSFT/2025-08-01.json")
        assert removed_count == 1


def test_cleanup_past_data_removes_old_items(buckets):
    _, _ = buckets
    call_bucket = GcsBucket("calls-b")
    email_bucket = GcsBucket("email-b")
    
    # Set up a test time
    now = datetime(2025, 7, 30, 15, 0, tzinfo=timezone.utc)
    past_call_time = (now - timedelta(days=2)).isoformat()  # 2 days ago
    old_email_time = (now - timedelta(hours=2)).isoformat()  # 2 hours ago
    
    with patch.object(
        call_bucket,
        "list_json",
        return_value=[
            ("calls/AAPL/old.json", {"ticker": "AAPL", "call_time": past_call_time}),
            ("calls/MSFT/current.json", {"ticker": "MSFT", "call_time": (now + timedelta(days=1)).isoformat()}),
        ],
    ), patch.object(call_bucket, "delete") as call_delete, patch.object(
        email_bucket,
        "list_json",
        return_value=[
            ("queue/AAPL/old.json", {"ticker": "AAPL", "send_time": old_email_time}),
            ("queue/MSFT/current.json", {"ticker": "MSFT", "send_time": (now + timedelta(minutes=30)).isoformat()}),
        ],
    ), patch.object(email_bucket, "delete") as email_delete:
        
        calls_removed, emails_removed = cleanup_past_data(call_bucket, email_bucket, now=now)
        
        call_delete.assert_called_once_with("calls/AAPL/old.json")
        email_delete.assert_called_once_with("queue/AAPL/old.json")
        assert calls_removed == 1
        assert emails_removed == 1


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


def test_cleanup_duplicate_emails_removes_duplicates(buckets):
    _, _ = buckets
    bucket = GcsBucket("email-b")
    
    # Create test data with duplicates
    test_emails = [
        ("queue/AAPL/old1.json", {"ticker": "AAPL", "call_time": "2025-08-01T13:00:00+00:00", "kind": "one_week"}),
        ("queue/AAPL/old2.json", {"ticker": "AAPL", "call_time": "2025-08-01T13:00:00+00:00", "kind": "one_week"}),
        ("queue/AAPL/new.json", {"ticker": "AAPL", "call_time": "2025-08-01T13:00:00+00:00", "kind": "one_week"}),
        ("queue/AAPL/different.json", {"ticker": "AAPL", "call_time": "2025-08-02T13:00:00+00:00", "kind": "one_week"}),
    ]
    
    with patch.object(bucket, "list_json", return_value=test_emails), \
         patch.object(bucket, "delete") as delete:
        
        from src.earnings_alerts import cleanup_duplicate_emails
        removed_count = cleanup_duplicate_emails(bucket, "AAPL", "2025-08-01T13:00:00+00:00", "one_week")
        
        # Should remove 3 emails (old1, old2, new) for the specific call_time/kind combination
        assert removed_count == 3
        assert delete.call_count == 3


def test_cleanup_ticker_emails_removes_all_for_ticker(buckets):
    _, _ = buckets
    bucket = GcsBucket("email-b")
    
    # Create test data
    all_emails = [
        ("queue/AAPL/email1.json", {"ticker": "AAPL", "call_time": "2025-08-01T13:00:00+00:00", "kind": "one_week"}),
        ("queue/AAPL/email2.json", {"ticker": "AAPL", "call_time": "2025-08-01T13:00:00+00:00", "kind": "tomorrow"}),
        ("queue/MSFT/email3.json", {"ticker": "MSFT", "call_time": "2025-08-01T13:00:00+00:00", "kind": "one_week"}),
    ]
    
    def mock_list_json(prefix):
        if prefix == "queue/AAPL/":
            return [email for email in all_emails if email[0].startswith("queue/AAPL/")]
        elif prefix == "queue/":
            return all_emails
        else:
            return []
    
    with patch.object(bucket, "list_json", side_effect=mock_list_json), \
         patch.object(bucket, "delete") as delete:
        
        from src.earnings_alerts import cleanup_ticker_emails
        removed_count = cleanup_ticker_emails(bucket, "AAPL")
        
        # Should remove 2 emails for AAPL, keep MSFT
        assert removed_count == 2
        assert delete.call_count == 2


def test_cleanup_all_duplicate_emails_removes_system_duplicates(buckets):
    _, _ = buckets
    bucket = GcsBucket("email-b")
    
    # Create test data with duplicates across different tickers
    test_emails = [
        ("queue/AAPL/old1.json", {"ticker": "AAPL", "call_time": "2025-08-01T13:00:00+00:00", "kind": "one_week"}),
        ("queue/AAPL/new1.json", {"ticker": "AAPL", "call_time": "2025-08-01T13:00:00+00:00", "kind": "one_week"}),
        ("queue/MSFT/old2.json", {"ticker": "MSFT", "call_time": "2025-08-01T13:00:00+00:00", "kind": "one_week"}),
        ("queue/MSFT/new2.json", {"ticker": "MSFT", "call_time": "2025-08-01T13:00:00+00:00", "kind": "one_week"}),
        ("queue/AAPL/unique.json", {"ticker": "AAPL", "call_time": "2025-08-02T13:00:00+00:00", "kind": "one_week"}),
    ]
    
    with patch.object(bucket, "list_json", return_value=test_emails), \
         patch.object(bucket, "delete") as delete:
        
        from src.earnings_alerts import cleanup_all_duplicate_emails
        removed_count = cleanup_all_duplicate_emails(bucket)
        
        # Should remove 2 duplicates (old1 and old2), keep new1, new2, and unique
        assert removed_count == 2
        assert delete.call_count == 2
