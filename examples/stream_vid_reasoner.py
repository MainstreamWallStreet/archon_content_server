#!/usr/bin/env python3
"""
stream_vid_reasoner.py
======================

Call the `/vid-reasoner` endpoint with `stream=True` to receive a streaming
response from the server and print chunks as they arrive.

Usage
-----
$ python examples/stream_vid_reasoner.py "hello world!" \
    --server http://localhost:8080

Environment
-----------
The script loads variables from a `.env` file (via `python-dotenv`).
It requires `ARCHON_API_KEY` to be set in the environment or in `.env`.

Example .env snippet::
    ARCHON_API_KEY=your-archon-api-key

"""
from __future__ import annotations

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

# ────────────────────────────────
# 🔧  CLI
# ────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream response from vid-reasoner endpoint"
    )
    parser.add_argument("message", help="Input message to send to vid-reasoner")
    parser.add_argument(
        "--server",
        default="http://localhost:8080",
        help="Base URL of Archon Content Server (default: http://localhost:8080)",
    )
    return parser.parse_args()


# ────────────────────────────────
# 🚀  Main logic
# ────────────────────────────────


def main() -> None:
    args = parse_args()

    # Load .env (if present) – this is a no-op if the file doesn't exist.
    load_dotenv()

    api_key = os.getenv("ARCHON_API_KEY")
    if not api_key:
        sys.exit("❌ ARCHON_API_KEY not found in environment or .env file.")

    url = f"{args.server.rstrip('/')}/vid-reasoner"

    payload = {
        "input_value": args.message,
        "output_type": "text",
        "input_type": "text",
        "stream": True,
    }

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
    }

    print(f"📡 Requesting streaming response from {url}\n")

    try:
        with requests.post(
            url, json=payload, headers=headers, stream=True, timeout=60
        ) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=None):
                if chunk:
                    # Stream arrives as bytes – decode and print without newline
                    try:
                        text = chunk.decode("utf-8", errors="ignore")
                    except Exception:
                        text = str(chunk)
                    print(text, end="", flush=True)
    except KeyboardInterrupt:
        print("\n⏹️  Interrupted by user")
    except requests.RequestException as exc:
        sys.exit(f"❌ Request failed: {exc}")


if __name__ == "__main__":
    main()
