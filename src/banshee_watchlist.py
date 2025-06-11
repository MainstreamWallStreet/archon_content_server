from __future__ import annotations

import json
import os
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
        client_opts = None
        if os.getenv("STORAGE_EMULATOR_HOST"):
            client_opts = {"api_endpoint": os.environ["STORAGE_EMULATOR_HOST"]}
        try:
            self._client = storage.Client(client_options=client_opts)
            self._bucket = self._client.bucket(bucket)
            if not self._bucket.exists():
                raise ValueError(f"GCS bucket {bucket} does not exist")
        except GoogleCloudError as exc:  # pragma: no cover - network errors
            raise RuntimeError(f"Failed to initialise GCS client: {exc}") from exc

    # ────────────────────────── watchlist helpers ──────────────────────────
    def list_tickers(self) -> List[str]:
        """Return all tickers in the watchlist."""
        try:
            blobs = self._client.list_blobs(self._bucket.name, prefix="watchlist/")
            return [b.name.split("/")[-1].split(".")[0] for b in blobs]
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to list tickers: {exc}") from exc

    def add_ticker(self, ticker: str, user: str) -> None:
        """Create a watchlist object for ``ticker``."""
        blob = self._bucket.blob(f"watchlist/{ticker.upper()}.json")
        # Fail fast if the ticker already exists
        if blob.exists() is True:
            raise ValueError(f"Ticker {ticker.upper()} already exists in watchlist")
        obj = {
            "name": ticker.upper(),
            "created_by_user": user,
            "created_at": date.today().isoformat(),
        }
        try:
            blob.upload_from_string(json.dumps(obj), if_generation_match=0)
            utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            send_alert(
                f"Ticker {ticker.upper()} Added to Watchlist",
                f"Ticker {ticker.upper()} was added to the watchlist by {user} at {utc_time}.",
            )
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to add ticker {ticker}: {exc}") from exc

    def remove_ticker(self, ticker: str) -> None:
        """Delete ``ticker`` from the watchlist."""
        blob = self._bucket.blob(f"watchlist/{ticker.upper()}.json")
        try:
            blob.delete()
            utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            send_alert(
                f"Ticker {ticker.upper()} Removed from Watchlist",
                f"Ticker {ticker.upper()} was removed from the watchlist at {utc_time}.",
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
