#!/usr/bin/env python3
"""Demonstrate adding and removing a watchlist item via the API."""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv
from google.cloud import storage


def _client() -> storage.Client:
    opts = None
    if os.getenv("STORAGE_EMULATOR_HOST"):
        opts = {"api_endpoint": os.environ["STORAGE_EMULATOR_HOST"]}
    return storage.Client(client_options=opts)


def _check_exists(bucket: storage.Bucket, path: str) -> bool:
    return bucket.blob(path).exists()


def main() -> None:
    load_dotenv()
    api_key = os.environ["BANSHEE_API_KEY"]
    bucket_name = os.environ["BANSHEE_DATA_BUCKET"]
    host = os.environ.get("BANSHEE_HOST", "http://localhost:8080")
    ticker = os.environ.get("DEMO_TICKER", "AAPL").upper()
    gcs = _client()
    bucket = gcs.bucket(bucket_name)

    headers = {"X-API-Key": api_key}

    print(f"Adding {ticker} to watchlist…")
    resp = requests.post(
        f"{host}/watchlist", json={"ticker": ticker, "user": "demo"}, headers=headers
    )
    resp.raise_for_status()
    path = f"watchlist/{ticker}.json"
    print("Exists after add:", _check_exists(bucket, path))

    print(f"Removing {ticker} from watchlist…")
    resp = requests.delete(f"{host}/watchlist/{ticker}", headers=headers)
    resp.raise_for_status()
    print("Exists after delete:", _check_exists(bucket, path))


if __name__ == "__main__":
    main()
