from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from src.notifications import send_alert


class BansheeStore:
    """Helper for managing watchlist and scheduled calls in GCS."""

    def __init__(self, bucket: str) -> None:
        if not bucket:
            raise ValueError("GCS bucket is required")
        try:
            # Use default GCS client (no emulator override)
            self._client = storage.Client()
            self._bucket = self._client.bucket(bucket)
            if not self._bucket.exists():
                raise ValueError(f"GCS bucket {bucket} does not exist")
        except GoogleCloudError as exc:  # pragma: no cover - network errors
            raise RuntimeError(f"Failed to initialise GCS client: {exc}") from exc

    # ────────────────────────── watchlist helpers ──────────────────────────
    def list_tickers(self) -> List[str]:
        """Return all tickers in the watchlist."""
        blob = self._bucket.blob("watchlist.json")
        try:
            if not blob.exists():
                return []
            data = json.loads(blob.download_as_text())
            return [t.upper() for t in data]
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to list tickers: {exc}") from exc

    def add_ticker(self, ticker: str, user: str | None = None) -> None:
        """Add ``ticker`` to the watchlist."""
        blob = self._bucket.blob("watchlist.json")
        try:
            data: List[str] = []
            if blob.exists():
                data = json.loads(blob.download_as_text())
            t = ticker.upper()
            if t in data:
                raise ValueError(f"Ticker {t} already exists in watchlist")
            data.append(t)
            blob.upload_from_string(json.dumps(data))

            utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            try:
                send_alert(
                    f"Ticker {ticker.upper()} Added to Watchlist",
                    f"Ticker {ticker.upper()} was added to the watchlist by {user} at {utc_time}.",
                )
            except Exception as alert_err:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).warning(
                    "send_alert failed during add_ticker: %s", alert_err
                )
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to add ticker {ticker}: {exc}") from exc

    def remove_ticker(self, ticker: str) -> None:
        """Delete ``ticker`` from the watchlist."""
        blob = self._bucket.blob("watchlist.json")
        try:
            data: List[str] = []
            if blob.exists():
                data = json.loads(blob.download_as_text())
            t = ticker.upper()
            if t not in data:
                raise ValueError(f"Ticker {t} not found in watchlist")
            data.remove(t)
            blob.upload_from_string(json.dumps(data))
            utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            try:
                send_alert(
                    f"Ticker {ticker.upper()} Removed from Watchlist",
                    f"Ticker {ticker.upper()} was removed from the watchlist at {utc_time}.",
                )
            except Exception as alert_err:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).warning(
                    "send_alert failed during remove_ticker: %s", alert_err
                )
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to remove ticker {ticker}: {exc}") from exc

    # ────────────────────────── call queue helpers ──────────────────────────
    def schedule_call(self, call_obj: Dict[str, Any]) -> None:
        """Persist a scheduled earnings call."""
        blob = self._bucket.blob(
            f"earnings_queue/{call_obj['ticker']}/{call_obj['call_date']}.json"
        )
        try:
            blob.upload_from_string(json.dumps(call_obj), if_generation_match=0)
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to schedule call: {exc}") from exc

    def update_call_status(self, ticker: str, date_str: str, new_status: str) -> None:
        """Update status for a scheduled call."""
        blob = self._bucket.blob(f"earnings_queue/{ticker}/{date_str}.json")
        try:
            data = json.loads(blob.download_as_text())
            data["status"] = new_status
            blob.upload_from_string(json.dumps(data))
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to update status: {exc}") from exc

    # ────────────────────────── misc helpers ──────────────────────────
    def record_api_call(self, endpoint: str, ticker: str) -> None:
        """Append a line to the monthly API call log."""
        today = date.today()
        path = f"api_calls/{today.strftime('%Y-%m')}.csv"
        blob = self._bucket.blob(path)
        try:
            existing = ""
            if blob.exists():
                existing = blob.download_as_text()
            line = f"{date.today().isoformat()},{endpoint},{ticker}\n"
            blob.upload_from_string(existing + line)
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to record API call: {exc}") from exc
