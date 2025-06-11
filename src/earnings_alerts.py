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
            blob = self._bucket.blob(path)
            blob.upload_from_string(json.dumps(data))
            logger.info("Saved gs://%s/%s", self.name, path)
        except GoogleCloudError as exc:  # pragma: no cover - network errors
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

    if fetcher is None:
        from src.banshee_api import _fetch_api_ninjas_upcoming as fetcher

    now = datetime.now(timezone.utc)
    tickers = store.list_tickers()

    for ticker in tickers:
        data = await fetcher(ticker)
        for item in data:
            if "earnings_date" not in item:
                continue
            call_time = datetime.fromisoformat(
                item["earnings_date"].replace("Z", "+00:00")
            )
            call_date = call_time.date().isoformat()
            call_obj = {
                "ticker": ticker,
                "call_date": call_date,
                "call_time": call_time.isoformat(),
            }
            path = f"calls/{ticker}/{call_date}.json"
            calls_bucket.write_json(path, call_obj)

            # schedule emails
            for offset, label in [
                (timedelta(days=7), "one_week"),
                (timedelta(days=1), "tomorrow"),
                (timedelta(hours=1), "one_hour"),
            ]:
                send_time = call_time - offset
                if send_time <= now:
                    continue
                email_obj = {
                    "ticker": ticker,
                    "call_time": call_time.isoformat(),
                    "send_time": send_time.isoformat(),
                    "kind": label,
                }
                epath = f"queue/{ticker}/{uuid.uuid4()}.json"
                email_bucket.write_json(epath, email_obj)

    logger.info("Completed upcoming call refresh for %d tickers", len(tickers))


def cleanup_email_queue(email_bucket: GcsBucket, tickers: set[str]) -> None:
    """Remove queued emails for tickers no longer tracked."""
    for path, data in email_bucket.list_json("queue/"):
        if data.get("ticker") not in tickers:
            email_bucket.delete(path)


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
    return (
        f"{ticker} earnings call in 1 hour",
        f"The {ticker} earnings call is at {dt_str}.",
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
