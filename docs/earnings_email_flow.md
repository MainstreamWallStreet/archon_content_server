# Earnings Email Workflow

Banshee periodically checks upcoming earnings dates for all tickers in the watchlist.
The schedule runs nightly at **19:00 EST** and whenever a new ticker is added.
Results are stored in a dedicated GCS bucket so that alerts survive restarts.

## Buckets

| Purpose | Variable | Example |
|---------|----------|---------|
| Upcoming earnings JSON files | `EARNINGS_BUCKET` | `banshee-earnings` |
| Pending email notifications  | `EMAIL_QUEUE_BUCKET` | `banshee-email-queue` |

Both buckets are created by Terraform and made writable by the Cloud Run service account.

## Workflow

1. **Refresh upcoming calls** – `refresh_upcoming_calls()` fetches data from the
   API Ninjas endpoint for each ticker and writes one file per call to
   `gs://$EARNINGS_BUCKET/calls/<ticker>/<date>.json`.
   For every call three reminder emails are queued (one week, one day and one hour before).
2. **Cleanup** – after refresh and whenever a ticker is removed the email queue
   is scanned and any entries for non‑watchlist tickers are deleted.
3. **Email dispatch** – `send_due_emails()` runs hourly and sends any queued
   emails due within the next hour. Files are removed once sent.

Each write or delete logs the `gs://bucket/path` so activity can be audited.

Terraform variables `earnings_bucket` and `email_queue_bucket` map to the above
environment variables. Update `sample.env` accordingly when deploying.
