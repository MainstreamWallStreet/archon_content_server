#!/usr/bin/env python3
"""Demo script for watchlist API."""

import os
import requests
import sys
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BANSHEE_API_KEY")
if not API_KEY:
    print("Error: BANSHEE_API_KEY not found in .env file.", file=sys.stderr)
    sys.exit(1)

BASE_URL = "http://localhost:8080"
TIMEOUT = 10  # seconds

def log_request_info(endpoint):
    print(f"Hitting URL: {endpoint}")
    print(f"Using API key (first 10 chars): {API_KEY[:10]}")

def delete_ticker(ticker):
    """Delete a ticker from the watchlist."""
    endpoint = f"{BASE_URL}/watchlist/tickers/{ticker}"
    log_request_info(endpoint)
    print(f"Deleting {ticker} from watchlist...")
    try:
        resp = requests.delete(endpoint, headers={"X-API-Key": API_KEY}, timeout=TIMEOUT)
        if resp.status_code == 404:
            print(f"{ticker} not found in watchlist.")
        else:
            resp.raise_for_status()
            print(f"Successfully deleted {ticker}.")
    except requests.Timeout:
        print(f"Error: DELETE request timed out after {TIMEOUT} seconds.", file=sys.stderr)
        sys.exit(1)

def add_ticker(ticker):
    """Add a ticker to the watchlist."""
    endpoint = f"{BASE_URL}/watchlist/tickers"
    log_request_info(endpoint)
    print(f"Adding {ticker} to watchlist...")
    try:
        resp = requests.post(endpoint, json={"ticker": ticker}, headers={"X-API-Key": API_KEY}, timeout=TIMEOUT)
        resp.raise_for_status()
        print(f"Successfully added {ticker}.")
    except requests.Timeout:
        print(f"Error: POST request timed out after {TIMEOUT} seconds.", file=sys.stderr)
        sys.exit(1)

def main():
    ticker = "AAPL"
    try:
        # First, delete the ticker if it exists
        delete_ticker(ticker)
        # Then add it
        add_ticker(ticker)
        # Finally, delete it again
        delete_ticker(ticker)
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
