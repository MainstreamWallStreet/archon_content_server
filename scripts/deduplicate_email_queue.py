#!/usr/bin/env python3
"""
Deduplicate the email queue in the GCS bucket, removing all but the most recent email for each (ticker, call_time, kind).

Usage:
  python scripts/deduplicate_email_queue.py

Requires:
  - EMAIL_QUEUE_BUCKET environment variable set
  - GCS credentials available (e.g., GOOGLE_APPLICATION_CREDENTIALS)
"""
import os
import logging
from src.earnings_alerts import GcsBucket, cleanup_all_duplicate_emails

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    bucket_name = os.environ.get("EMAIL_QUEUE_BUCKET")
    if not bucket_name:
        print("EMAIL_QUEUE_BUCKET environment variable is not set.")
        exit(1)
    
    logger.info(f"Connecting to GCS bucket: {bucket_name}")
    bucket = GcsBucket(bucket_name)
    removed = cleanup_all_duplicate_emails(bucket)
    logger.info(f"Deduplication complete. Removed {removed} duplicate emails.")
    print(f"Deduplication complete. Removed {removed} duplicate emails.")

if __name__ == "__main__":
    main() 