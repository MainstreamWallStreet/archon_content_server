# Banshee Server

Banshee is a FastAPI-based backend for managing stock watchlists, earnings alerts, and notifications. It integrates with Google Cloud Storage, SendGrid, and external APIs to provide robust alerting and data synchronization for financial events.

## Features

- **Watchlist Management**: Add, remove, and list stock tickers.
- **Earnings Alerts**: Track upcoming earnings calls and send notifications.
- **Global and User Alerts**: Send system-wide or user-specific email notifications.
- **Google Cloud Integration**: Uses GCS for persistent storage of watchlists and call queues.
- **SendGrid Integration**: Email notifications for alerts and system events.
- **API Key and Basic Auth Security**: Protects endpoints with API keys and/or basic authentication.
- **Automated Data Sync**: Scheduled tasks for syncing earnings data and sending queued emails.
- **Self-Contained Background Scheduler**: All periodic jobs run inside the server—no external cron or cloud scheduler needed.
- **Comprehensive Test Suite**: Includes robust async and endpoint tests.

## Background Scheduler: How Banshee Automates Everything

Banshee includes a built-in, self-contained background scheduler that automates all periodic operations. This means you do **not** need to set up any external cron jobs, Google Cloud Scheduler, or other automation tools. If the server is running, your jobs are running.

### What the Scheduler Does

- **Daily Sync (00:00 UTC / 19:00 EST)**
  - Refreshes upcoming earnings calls for all tickers
  - Queues reminder emails (1 week, 1 day, and 1 hour before each call)
  - Cleans up old/past data
- **Hourly Email Dispatch**
  - Scans the email queue for any emails due in the next hour
  - Sends those emails and removes them from the queue
- **Manual Triggers**
  - You can still trigger these operations manually via `/tasks/daily-sync`, `/tasks/upcoming-sync`, and `/tasks/send-queued-emails` endpoints

### How It Works

- The scheduler is started automatically when the FastAPI app starts, and stopped when the app shuts down.
- Uses Python's `asyncio` for non-blocking background tasks.
- All logic is covered by tests, and you can manually trigger syncs via API endpoints.
- No external dependencies: works the same in local dev, staging, or production.

### Why This Design?

- **Self-contained**: No ops or cloud setup required.
- **Portable**: Works anywhere you run the server.
- **Reliable**: If the server is running, your periodic jobs are running.

## Requirements

- Python 3.11+
- Google Cloud credentials (for GCS)
- SendGrid account (for email notifications)

## Installation

1. **Clone the repository:**
   ```sh
   git clone https://github.com/MainstreamWallStreet/banshee-server-rebuild.git
   cd banshee-server-rebuild
   ```

2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   - Copy `sample.env` to `.env` and fill in your secrets and configuration.
   - Required variables include:
     - `GOOGLE_CLOUD_PROJECT`
     - `GOOGLE_SA_VALUE`
     - `API_NINJAS_KEY`
     - `RAVEN_API_KEY`
     - `BANSHEE_API_KEY`
     - `BANSHEE_DATA_BUCKET`
     - `EARNINGS_BUCKET`
     - `EMAIL_QUEUE_BUCKET`
     - `BANSHEE_WEB_PASSWORD`
     - `SENDGRID_API_KEY`
     - `ALERT_FROM_EMAIL`
     - `ALERT_RECIPIENTS`
     - `ENV`

## Running the Server

For local development, use the provided entrypoint:

```sh
python run_banshee.py
```

This will start the FastAPI server on `http://0.0.0.0:8080` with hot reload and detailed logging.

## API Overview

### Authentication

- Most endpoints require an `X-API-Key` header with the value set to your `BANSHEE_API_KEY`.
- The `/web` UI endpoint uses HTTP Basic Auth with the password from `BANSHEE_WEB_PASSWORD`.

### Endpoints

- `GET /`  
  Health check. Returns API status.

- `GET /watchlist`  
  List all tickers in the watchlist.

- `POST /watchlist`  
  Add a ticker to the watchlist.  
  **Body:** `{ "ticker": "AAPL", "user": "alice" }`

- `DELETE /watchlist/{ticker}`  
  Remove a ticker from the watchlist and clean up related data.

- `GET /earnings/upcoming`  
  List upcoming earnings calls.

- `GET /earnings/{ticker}`  
  Get earnings data for a specific ticker.

- `POST /send-global-alert`  
  Send a global alert email to all configured recipients.  
  **Body:** `{ "subject": "Alert", "message": "Something happened" }`

- `POST /tasks/daily-sync`  
  Trigger a daily sync of earnings and watchlist data.

- `POST /tasks/upcoming-sync`  
  Trigger a sync of upcoming earnings calls.

- `POST /tasks/send-queued-emails`  
  Send all queued emails.

- `POST /test-email`  
  Send a test email to the configured address.

- `GET /web`  
  Access the web UI (requires HTTP Basic Auth).

## Email & Alerting

- Uses SendGrid for all email notifications.
- Alerts can be sent to all admins or individual users.
- Recipients and sender are configured via environment variables.

## Testing

- Tests are located in the `__tests__` directory.
- To run all tests:
  ```sh
  pytest __tests__/
  ```
- Tests cover:
  - Watchlist API
  - Notification and alerting logic
  - Earnings alerts and data sync
  - GCS job queue logic

## Deployment

- See `deploy.md` for details on deploying to Google Cloud Run using Cloud Build and Cloud Deploy.
- All secrets and environment variables should be managed securely (e.g., via Google Secret Manager).

## Contributing

Pull requests and issues are welcome! Please ensure all tests pass before submitting changes.

---

**Main Authors:**  
- Griffin Clark  
- Mainstream Wall Street Team 