from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Awaitable, Dict, List, Tuple

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from src.banshee_watchlist import BansheeStore
from src.notifications import send_alert

logger = logging.getLogger(__name__)


def _client() -> storage.Client:
    opts = None
    if os.getenv("STORAGE_EMULATOR_HOST"):
        opts = {"api_endpoint": os.environ["STORAGE_EMULATOR_HOST"]}
    return storage.Client(client_options=opts)


class GcsBucket:
    """Minimal wrapper for JSON reads/writes in a bucket."""

    def __init__(self, name: str) -> None:
        if not name:
            raise ValueError("Bucket name is required")
        self._client = _client()
        self._bucket = self._client.bucket(name)
        if not self._bucket.exists():
            raise ValueError(f"GCS bucket {name} does not exist")
        self.name = name

    def write_json(self, path: str, data: Dict) -> None:
        try:
            logger.info("Writing JSON data to gs://%s/%s", self.name, path)
            logger.info("Data being written: %s", json.dumps(data, indent=2))
            blob = self._bucket.blob(path)
            blob.upload_from_string(json.dumps(data))
            logger.info("Successfully saved gs://%s/%s", self.name, path)
        except GoogleCloudError as exc:  # pragma: no cover - network errors
            logger.error("Failed to write gs://%s/%s: %s", self.name, path, str(exc))
            raise RuntimeError(f"Failed to write {path}: {exc}") from exc

    def list_json(self, prefix: str) -> List[Tuple[str, Dict]]:
        try:
            items: List[Tuple[str, Dict]] = []
            for blob in self._client.list_blobs(self.name, prefix=prefix):
                data = json.loads(blob.download_as_text())
                items.append((blob.name, data))
            return items
        except GoogleCloudError as exc:  # pragma: no cover - network errors
            raise RuntimeError(f"Failed to list {prefix}: {exc}") from exc

    def delete(self, path: str) -> None:
        try:
            blob = self._bucket.blob(path)
            blob.delete()
            logger.info("Deleted gs://%s/%s", self.name, path)
        except GoogleCloudError as exc:  # pragma: no cover - network errors
            raise RuntimeError(f"Failed to delete {path}: {exc}") from exc


async def refresh_upcoming_calls(
    store: BansheeStore,
    calls_bucket: GcsBucket,
    email_bucket: GcsBucket,
    *,
    fetcher: Callable[[str], Awaitable[List[Dict]]] | None = None,
) -> None:
    """Fetch upcoming earnings and queue reminder emails."""
    logger.info("Starting refresh_upcoming_calls process")

    if fetcher is None:
        from src.banshee_api import _fetch_api_ninjas_upcoming as fetcher
        logger.info("Using default API Ninjas fetcher")

    now = datetime.now(timezone.utc)
    logger.info("Current UTC time: %s", now.isoformat())
    
    tickers = store.list_tickers()
    logger.info("Retrieved %d tickers from watchlist: %s", len(tickers), tickers)
    
    if not tickers:
        logger.warning("No tickers found in watchlist - nothing to refresh")
        return

    total_calls_saved = 0
    total_emails_queued = 0

    for ticker_index, ticker in enumerate(tickers, 1):
        logger.info("[%d/%d] Processing ticker: %s", ticker_index, len(tickers), ticker)
        
        try:
            logger.info("Fetching upcoming earnings data for %s from API Ninjas", ticker)
            data = await fetcher(ticker)
            logger.info("API response for %s: received %d items", ticker, len(data))
            
            if not data:
                logger.info("No earnings data returned for %s", ticker)
                continue
                
            # Log the raw API response for debugging
            logger.info("Raw API data for %s: %s", ticker, json.dumps(data, indent=2))
            
        except Exception as e:
            logger.error("Failed to fetch data for %s: %s", ticker, str(e))
            continue
        
        calls_found = 0
        emails_for_ticker = 0
        
        for item_index, item in enumerate(data):
            logger.info("Processing item %d for %s: %s", item_index + 1, ticker, json.dumps(item, indent=2))
            logger.info("Available fields in item %d for %s: %s", item_index + 1, ticker, list(item.keys()))
            
            # Try multiple possible date field names as fallback
            date_field = None
            possible_date_fields = ['date', 'earnings_date', 'announcement_date', 'report_date', 'call_date', 'earnings_call_date']
            
            for field_name in possible_date_fields:
                if field_name in item and item[field_name]:
                    date_field = field_name
                    logger.info("Found date field '%s' for %s with value: %s", field_name, ticker, item[field_name])
                    break
            
            if not date_field:
                logger.warning("Item %d for %s missing all expected date fields %s, skipping", 
                             item_index + 1, ticker, possible_date_fields)
                logger.warning("Item data for debugging: %s", json.dumps(item, indent=2))
                continue
                
            try:
                earnings_date_raw = item[date_field]
                logger.info("Using date field '%s' for %s: %s", date_field, ticker, earnings_date_raw)
                
                # Handle different date formats
                if len(earnings_date_raw) == 10:  # Date only like "2026-04-13"
                    # Assume before market opens (8 AM EST = 1 PM UTC)
                    call_time = datetime.fromisoformat(f"{earnings_date_raw}T13:00:00+00:00")
                    logger.info("Parsed date-only string for %s: %s -> %s (8 AM EST)", ticker, earnings_date_raw, call_time.isoformat())
                elif earnings_date_raw.endswith('Z'):
                    # ISO format with Z timezone
                    call_time = datetime.fromisoformat(earnings_date_raw.replace("Z", "+00:00"))
                    logger.info("Parsed ISO Z-format for %s: %s -> %s", ticker, earnings_date_raw, call_time.isoformat())
                else:
                    # Try to parse as-is and add timezone if missing
                    try:
                        call_time = datetime.fromisoformat(earnings_date_raw)
                        if call_time.tzinfo is None:
                            # Add UTC timezone if missing
                            call_time = call_time.replace(tzinfo=timezone.utc)
                            logger.info("Added UTC timezone for %s: %s -> %s", ticker, earnings_date_raw, call_time.isoformat())
                        else:
                            logger.info("Parsed datetime with timezone for %s: %s -> %s", ticker, earnings_date_raw, call_time.isoformat())
                    except ValueError as ve:
                        logger.error("Failed to parse date format for %s: %s (error: %s)", ticker, earnings_date_raw, str(ve))
                        continue
                
                logger.info("Final call_time for %s: %s", ticker, call_time.isoformat())
                
                # Check if this is a future call
                if call_time <= now:
                    logger.info("Call time %s for %s is in the past (now: %s), skipping", 
                              call_time.isoformat(), ticker, now.isoformat())
                    continue
                    
                call_date = call_time.date().isoformat()
                logger.info("Call date for %s: %s", ticker, call_date)
                
                call_obj = {
                    "ticker": ticker,
                    "call_date": call_date,
                    "call_time": call_time.isoformat(),
                }
                logger.info("Created call object for %s: %s", ticker, json.dumps(call_obj, indent=2))
                
                path = f"calls/{ticker}/{call_date}.json"
                logger.info("Saving call data to GCS path: gs://%s/%s", calls_bucket.name, path)
                
                calls_bucket.write_json(path, call_obj)
                calls_found += 1
                total_calls_saved += 1
                logger.info("Successfully saved call data for %s to gs://%s/%s", ticker, calls_bucket.name, path)

                # schedule emails
                logger.info("Scheduling reminder emails for %s earnings call at %s", ticker, call_time.isoformat())
                
                for offset, label in [
                    (timedelta(days=7), "one_week"),
                    (timedelta(days=1), "tomorrow"),
                ]:
                    send_time = call_time - offset
                    logger.info("Calculating %s reminder for %s: send_time=%s (call_time=%s - %s)", 
                              label, ticker, send_time.isoformat(), call_time.isoformat(), str(offset))
                    
                    if send_time <= now:
                        logger.info("Send time %s for %s %s reminder is in the past (now: %s), skipping", 
                                  send_time.isoformat(), ticker, label, now.isoformat())
                        continue
                        
                    email_obj = {
                        "ticker": ticker,
                        "call_time": call_time.isoformat(),
                        "send_time": send_time.isoformat(),
                        "kind": label,
                    }
                    logger.info("Created email object for %s %s reminder: %s", 
                              ticker, label, json.dumps(email_obj, indent=2))
                    
                    epath = f"queue/{ticker}/{uuid.uuid4()}.json"
                    logger.info("Saving email to GCS path: gs://%s/%s", email_bucket.name, epath)
                    
                    email_bucket.write_json(epath, email_obj)
                    emails_for_ticker += 1
                    total_emails_queued += 1
                    logger.info("Successfully queued %s reminder email for %s at gs://%s/%s", 
                              label, ticker, email_bucket.name, epath)
                              
            except Exception as e:
                logger.error("Error processing earnings item %d for %s: %s", item_index + 1, ticker, str(e))
                logger.error("Problematic item data: %s", json.dumps(item, indent=2))
                continue
        
        logger.info("Completed processing %s: found %d calls, queued %d emails", 
                  ticker, calls_found, emails_for_ticker)

    logger.info("Completed upcoming call refresh for %d tickers", len(tickers))
    logger.info("SUMMARY: Saved %d calls to gs://%s, queued %d emails to gs://%s", 
              total_calls_saved, calls_bucket.name, total_emails_queued, email_bucket.name)


def cleanup_email_queue(email_bucket: GcsBucket, tickers: set[str]) -> int:
    """Remove queued emails for tickers no longer tracked.
    
    Returns:
        int: Number of emails removed
    """
    removed_count = 0
    for path, data in email_bucket.list_json("queue/"):
        if data.get("ticker") not in tickers:
            email_bucket.delete(path)
            removed_count += 1
            logger.info("Removed stale email for ticker %s: %s", data.get("ticker"), path)
    
    if removed_count > 0:
        logger.info("Cleanup complete: removed %d stale email(s) from queue", removed_count)
    
    return removed_count


def cleanup_calls_queue(calls_bucket: GcsBucket, tickers: set[str]) -> int:
    """Remove scheduled calls for tickers no longer tracked.
    
    Returns:
        int: Number of calls removed
    """
    removed_count = 0
    for path, data in calls_bucket.list_json("calls/"):
        if data.get("ticker") not in tickers:
            calls_bucket.delete(path)
            removed_count += 1
            logger.info("Removed stale call for ticker %s: %s", data.get("ticker"), path)
    
    if removed_count > 0:
        logger.info("Cleanup complete: removed %d stale call(s) from storage", removed_count)
    
    return removed_count


def cleanup_past_data(calls_bucket: GcsBucket, email_bucket: GcsBucket, *, now: datetime | None = None) -> tuple[int, int]:
    """Remove past calls and emails that are no longer relevant.
    
    Args:
        calls_bucket: GCS bucket containing calls
        email_bucket: GCS bucket containing emails
        now: Current time (defaults to now in UTC)
        
    Returns:
        tuple[int, int]: Number of (calls_removed, emails_removed)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    
    calls_removed = 0
    emails_removed = 0
    
    # Clean up past calls (older than 24 hours)
    cutoff_time = now - timedelta(hours=24)
    
    for path, data in calls_bucket.list_json("calls/"):
        try:
            call_time = datetime.fromisoformat(data["call_time"])
            if call_time < cutoff_time:
                calls_bucket.delete(path)
                calls_removed += 1
                logger.info("Removed past call for %s at %s: %s", 
                          data.get("ticker"), call_time.isoformat(), path)
        except (KeyError, ValueError) as e:
            logger.warning("Invalid call data in %s: %s", path, str(e))
            # Remove invalid data as well
            calls_bucket.delete(path)
            calls_removed += 1
    
    # Clean up past emails (send time more than 1 hour ago)
    email_cutoff = now - timedelta(hours=1)
    
    for path, data in email_bucket.list_json("queue/"):
        try:
            send_time = datetime.fromisoformat(data["send_time"])
            if send_time < email_cutoff:
                email_bucket.delete(path)
                emails_removed += 1
                logger.info("Removed past email for %s scheduled at %s: %s", 
                          data.get("ticker"), send_time.isoformat(), path)
        except (KeyError, ValueError) as e:
            logger.warning("Invalid email data in %s: %s", path, str(e))
            # Remove invalid data as well
            email_bucket.delete(path)
            emails_removed += 1
    
    if calls_removed > 0 or emails_removed > 0:
        logger.info("Past data cleanup complete: removed %d call(s) and %d email(s)", 
                   calls_removed, emails_removed)
    
    return calls_removed, emails_removed


def _render(kind: str, ticker: str, call_time: datetime) -> tuple[str, str]:
    dt_str = call_time.strftime("%Y-%m-%d %H:%M UTC")
    if kind == "one_week":
        return (
            f"{ticker} earnings call in 1 week",
            f"{ticker} will hold its earnings call on {dt_str}.",
        )
    if kind == "tomorrow":
        return (
            f"{ticker} earnings call tomorrow",
            f"Reminder: {ticker} announces earnings on {dt_str}.",
        )
    # If we get here, it's an unknown kind - shouldn't happen
    return (
        f"{ticker} earnings call notification",
        f"Reminder: {ticker} announces earnings on {dt_str}.",
    )


def send_due_emails(email_bucket: GcsBucket, *, now: datetime | None = None) -> None:
    """Send any queued emails due within the next hour."""
    now = now or datetime.now(timezone.utc)
    horizon = now + timedelta(hours=1)

    for path, data in email_bucket.list_json("queue/"):
        send_ts = datetime.fromisoformat(data["send_time"])
        if now <= send_ts <= horizon:
            call_dt = datetime.fromisoformat(data["call_time"])
            subj, body = _render(data["kind"], data["ticker"], call_dt)
            send_alert(subj, body)
            email_bucket.delete(path)
            logger.info("Dispatched email %s scheduled for %s", path, send_ts)
