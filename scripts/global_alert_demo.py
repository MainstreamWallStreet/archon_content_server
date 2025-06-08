#!/usr/bin/env python3
"""Send a global alert via the Banshee API."""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    api_key = os.environ["BANSHEE_API_KEY"]
    host = os.environ.get("BANSHEE_HOST", "http://localhost:8080")
    subject = os.environ.get("ALERT_SUBJECT", "Banshee Test Alert")
    body = os.environ.get("ALERT_BODY", "This is a test message.")

    resp = requests.post(
        f"{host}/send-global-alert",
        headers={"X-API-Key": api_key},
        json={"subject": subject, "message": body},
    )
    resp.raise_for_status()
    print(resp.json())


if __name__ == "__main__":
    main()
