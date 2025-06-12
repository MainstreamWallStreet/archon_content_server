from __future__ import annotations

import aiohttp
from typing import List
from datetime import datetime, timezone
import logging
import json

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from src.notifications import send_alert, send_email

from src.config import get_setting
from src.banshee_watchlist import BansheeStore
from src.earnings_alerts import (
    GcsBucket,
    refresh_upcoming_calls,
    cleanup_email_queue,
    cleanup_calls_queue,
    cleanup_past_data,
    send_due_emails,
)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key")


def validate_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    expected = get_setting("BANSHEE_API_KEY")
    if api_key != expected:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


store = BansheeStore(get_setting("BANSHEE_DATA_BUCKET"))
calls_bucket = GcsBucket(get_setting("EARNINGS_BUCKET"))
email_bucket = GcsBucket(get_setting("EMAIL_QUEUE_BUCKET"))
app = FastAPI(title="Banshee API", version="1.0")


class TickerPayload(BaseModel):
    ticker: str
    user: str


class AlertPayload(BaseModel):
    """Data required for sending a global alert."""

    subject: str
    message: str


class EarningsCall(BaseModel):
    """Data model for an earnings call event."""

    ticker: str
    call_date: str  # YYYY-MM-DD format
    call_time: str  # ISO 8601 datetime string
    status: str
    actual_eps: float | None = None
    estimated_eps: float | None = None
    actual_revenue: int | None = None
    estimated_revenue: int | None = None


class UpcomingCallsResponse(BaseModel):
    """Response model for upcoming earnings calls."""

    calls: List[EarningsCall]
    total_count: int
    next_call: EarningsCall | None = None


@app.get("/")
def root():
    """API root endpoint."""
    return {"status": "ok", "message": "Banshee API is running"}


@app.get("/watchlist")
def read_watchlist(_: str = Depends(validate_key)) -> dict[str, List[str]]:
    return {"tickers": store.list_tickers()}


@app.post("/watchlist")
async def create_watchlist(
    payload: TickerPayload, _: str = Depends(validate_key)
) -> dict[str, str]:
    try:
        store.add_ticker(payload.ticker, payload.user)

        # Immediately refresh upcoming calls to ensure the new ticker has an earnings entry
        await refresh_upcoming_calls(store, calls_bucket, email_bucket)

        # Cleanup stale artefacts now that the watchlist has changed – this prevents ghost
        # emails and calls from hanging around when users add/remove tickers frequently.
        remaining_tickers = set(store.list_tickers())
        cleanup_email_queue(email_bucket, remaining_tickers)
        cleanup_calls_queue(calls_bucket, remaining_tickers)

    except ValueError as err:
        # Duplicate ticker or validation issue – return a 400 so clients can handle gracefully
        raise HTTPException(status_code=400, detail=str(err))
    except RuntimeError as err:
        # Underlying storage error – surface the message but keep a 500 status
        raise HTTPException(status_code=500, detail=str(err))

    return {"message": "added"}


@app.delete("/watchlist/{ticker}")
async def delete_watchlist(
    ticker: str, _: str = Depends(validate_key)
) -> dict[str, str]:
    """Remove ticker from watchlist and cleanup all related calls and emails."""
    logger = logging.getLogger(__name__)
    ticker_upper = ticker.upper()

    try:
        logger.info("Starting deletion process for ticker: %s", ticker_upper)

        # Check if ticker exists in watchlist before attempting deletion
        current_tickers = store.list_tickers()
        if ticker_upper not in current_tickers:
            logger.warning("Ticker %s not found in watchlist", ticker_upper)
            raise HTTPException(
                status_code=404, detail=f"Ticker {ticker_upper} not found in watchlist"
            )

        # Count items before cleanup for reporting
        logger.info(
            "Counting existing calls and emails for %s before cleanup", ticker_upper
        )
        calls_before = []
        emails_before = []

        try:
            # Count calls for this ticker
            for path, data in calls_bucket.list_json("calls/"):
                if data.get("ticker") == ticker_upper:
                    calls_before.append(path)

            # Count emails for this ticker
            for path, data in email_bucket.list_json("queue/"):
                if data.get("ticker") == ticker_upper:
                    emails_before.append(path)

            logger.info(
                "Found %d calls and %d emails for %s",
                len(calls_before),
                len(emails_before),
                ticker_upper,
            )
        except Exception as e:
            logger.warning("Error counting existing items: %s", str(e))
            # Continue with deletion even if counting fails

        # Remove ticker from watchlist
        logger.info("Removing %s from watchlist", ticker_upper)
        store.remove_ticker(ticker_upper)

        # Clean up related calls and emails
        remaining_tickers = set(store.list_tickers())
        logger.info("Cleaning up calls and emails for removed ticker %s", ticker_upper)

        removed_calls = cleanup_calls_queue(calls_bucket, remaining_tickers)
        removed_emails = cleanup_email_queue(email_bucket, remaining_tickers)

        # Clean up past/expired data to keep storage lean
        logger.info("Cleaning up past calls and expired emails")
        past_calls, past_emails = cleanup_past_data(calls_bucket, email_bucket)

        # Create detailed success message
        cleanup_details = []
        total_removed_calls = removed_calls + past_calls
        total_removed_emails = removed_emails + past_emails

        if total_removed_calls > 0:
            if removed_calls > 0 and past_calls > 0:
                cleanup_details.append(
                    f"removed {total_removed_calls} call(s) ({removed_calls} stale, {past_calls} past)"
                )
            elif removed_calls > 0:
                cleanup_details.append(f"removed {removed_calls} stale call(s)")
            else:
                cleanup_details.append(f"removed {past_calls} past call(s)")

        if total_removed_emails > 0:
            if removed_emails > 0 and past_emails > 0:
                cleanup_details.append(
                    f"removed {total_removed_emails} email(s) ({removed_emails} stale, {past_emails} expired)"
                )
            elif removed_emails > 0:
                cleanup_details.append(f"removed {removed_emails} stale email(s)")
            else:
                cleanup_details.append(f"removed {past_emails} expired email(s)")

        if cleanup_details:
            cleanup_msg = f" and {', '.join(cleanup_details)}"
        else:
            cleanup_msg = " (no cleanup needed)"

        success_message = f"{ticker_upper} removed from watchlist{cleanup_msg}"
        logger.info(
            "Successfully completed deletion for %s: %s", ticker_upper, success_message
        )

        return {"message": success_message}

    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error("Error deleting ticker %s: %s", ticker_upper, str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove {ticker_upper} from watchlist: {str(e)}",
        )


@app.get("/earnings/upcoming")
async def get_upcoming_earnings(
    _: str = Depends(validate_key),
) -> UpcomingCallsResponse:
    """Get upcoming earnings calls from GCS storage."""
    logger = logging.getLogger(__name__)
    logger.info("Fetching upcoming earnings from GCS storage")

    calls = []
    now = datetime.now(timezone.utc)

    try:
        # Get all saved calls from GCS
        all_items = calls_bucket.list_json("calls/")
        logger.info("Found %d total items in GCS calls bucket", len(all_items))

        for path, call_data in all_items:
            try:
                logger.info("Processing GCS item: %s -> %s", path, call_data)

                # Parse the call time
                call_time_str = call_data["call_time"]
                call_time = datetime.fromisoformat(call_time_str)

                # Only include future calls
                if call_time <= now:
                    logger.info(
                        "Skipping past call: %s at %s",
                        call_data["ticker"],
                        call_time_str,
                    )
                    continue

                # Create EarningsCall object
                call = EarningsCall(
                    ticker=call_data["ticker"],
                    call_date=call_data["call_date"],
                    call_time=call_time_str,
                    status="scheduled",
                    actual_eps=None,
                    estimated_eps=None,
                    actual_revenue=None,
                    estimated_revenue=None,
                )
                calls.append(call)
                logger.info(
                    "Added upcoming call: %s on %s", call.ticker, call.call_date
                )

            except Exception as e:
                logger.error("Error processing GCS item %s: %s", path, str(e))
                continue

        # Sort by call time
        calls.sort(key=lambda x: x.call_time)

        next_call = calls[0] if calls else None

        logger.info("Returning %d upcoming calls", len(calls))
        return UpcomingCallsResponse(
            calls=calls, total_count=len(calls), next_call=next_call
        )

    except Exception as e:
        logger.error("Error fetching upcoming earnings from GCS: %s", str(e))
        # Return empty response if there's an error
        return UpcomingCallsResponse(calls=[], total_count=0, next_call=None)


@app.get("/earnings/{ticker}")
async def get_ticker_earnings(
    ticker: str, _: str = Depends(validate_key)
) -> List[EarningsCall]:
    """Get earnings calls for a specific ticker."""
    data = await _fetch_api_ninjas_upcoming(ticker)
    calls = []

    for item in data:
        if "earnings_date" in item:
            call = EarningsCall(
                ticker=ticker,
                call_date=item["earnings_date"][:10],
                call_time=item["earnings_date"],
                status="scheduled",
                actual_eps=item.get("actual_eps"),
                estimated_eps=item.get("estimated_eps"),
                actual_revenue=item.get("actual_revenue"),
                estimated_revenue=item.get("estimated_revenue"),
            )
            calls.append(call)

    # Sort by call time
    calls.sort(key=lambda x: x.call_time)
    return calls


@app.post("/send-global-alert")
def send_global_alert(
    payload: AlertPayload, _: str = Depends(validate_key)
) -> dict[str, str]:
    """Send an alert email to all configured recipients."""

    send_alert(payload.subject, payload.message)
    return {"status": "sent"}


async def _fetch_api_ninjas(ticker: str) -> list[dict]:
    url = f"https://api.api-ninjas.com/v1/earningscalendar?ticker={ticker}"
    headers = {"X-Api-Key": get_setting("API_NINJAS_KEY")}
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url, headers=headers) as resp:
            if resp.status != 200:
                raise RuntimeError(f"API Ninjas error {resp.status}")
            return await resp.json()


async def _fetch_api_ninjas_upcoming(ticker: str) -> list[dict]:
    """Fetch upcoming earnings calls from API Ninjas with fallback strategies."""
    logger = logging.getLogger(__name__)

    # Primary approach: use show_upcoming=true as documented
    # Fallback: get historical data and filter for future dates
    api_attempts = [
        {
            # Request a larger window of upcoming results (default is 3). Using 10 gives us
            # at least the next year of quarterly earnings, which captures the *soonest*
            # upcoming call that may otherwise be truncated.
            "url": (
                f"https://api.api-ninjas.com/v1/earningscalendar?"
                f"ticker={ticker}&show_upcoming=true&limit=10"
            ),
            "name": "upcoming_only",
            "expected_field": "date",  # Official API docs show 'date' field
        },
        {
            "url": f"https://api.api-ninjas.com/v1/earningscalendar?ticker={ticker}",
            "name": "historical_data",
            "expected_field": "date",
        },
    ]

    headers = {"X-Api-Key": get_setting("API_NINJAS_KEY")}

    for attempt_num, attempt in enumerate(api_attempts, 1):
        logger.info(
            "API attempt %d/%d for %s using %s",
            attempt_num,
            len(api_attempts),
            ticker,
            attempt["name"],
        )
        logger.info("Request URL: %s", attempt["url"])
        logger.info(
            "Request headers: %s",
            {
                k: v[:10] + "..." if k == "X-Api-Key" and len(v) > 10 else v
                for k, v in headers.items()
            },
        )

        async with aiohttp.ClientSession() as sess:
            try:
                async with sess.get(attempt["url"], headers=headers) as resp:
                    logger.info(
                        "API response status for %s (attempt %d): %d",
                        ticker,
                        attempt_num,
                        resp.status,
                    )

                    if resp.status != 200:
                        logger.error(
                            "API Ninjas error for %s (attempt %d): status %d",
                            ticker,
                            attempt_num,
                            resp.status,
                        )
                        response_text = await resp.text()
                        logger.error(
                            "Error response body for %s (attempt %d): %s",
                            ticker,
                            attempt_num,
                            response_text,
                        )

                        # If this isn't the last attempt, continue to next one
                        if attempt_num < len(api_attempts):
                            logger.info("Trying next API approach for %s", ticker)
                            continue
                        else:
                            raise RuntimeError(f"All API attempts failed for {ticker}")

                    result = await resp.json()
                    logger.info(
                        "API response for %s (attempt %d): %s",
                        ticker,
                        attempt_num,
                        json.dumps(result, indent=2) if result else "[]",
                    )

                    # Check if this result has usable data
                    if result and isinstance(result, list) and len(result) > 0:
                        # Prioritize 'date' field as documented, with fallbacks
                        date_fields = [
                            "date",
                            "earnings_date",
                            "announcement_date",
                            "report_date",
                            "call_date",
                            "earnings_call_date",
                        ]

                        usable_items = 0
                        for item in result:
                            if any(
                                field in item and item[field] for field in date_fields
                            ):
                                usable_items += 1

                        logger.info(
                            "Found %d usable items out of %d total for %s (attempt %d)",
                            usable_items,
                            len(result),
                            ticker,
                            attempt_num,
                        )

                        if usable_items > 0:
                            logger.info(
                                "Successfully retrieved usable data for %s using %s",
                                ticker,
                                attempt["name"],
                            )
                            return result
                        else:
                            logger.warning(
                                "No usable date fields found in response for %s (attempt %d)",
                                ticker,
                                attempt_num,
                            )
                            if attempt_num < len(api_attempts):
                                logger.info("Trying next API approach for %s", ticker)
                                continue
                    else:
                        logger.warning(
                            "Empty or invalid result for %s (attempt %d)",
                            ticker,
                            attempt_num,
                        )
                        if attempt_num < len(api_attempts):
                            logger.info("Trying next API approach for %s", ticker)
                            continue

                    # If we get here and it's the last attempt, return whatever we got
                    if attempt_num == len(api_attempts):
                        logger.warning(
                            "Returning potentially empty result for %s after all attempts",
                            ticker,
                        )
                        return result or []

            except Exception as e:
                logger.error(
                    "Exception during API request for %s (attempt %d): %s",
                    ticker,
                    attempt_num,
                    str(e),
                )
                if attempt_num < len(api_attempts):
                    logger.info(
                        "Trying next API approach for %s due to exception", ticker
                    )
                    continue
                else:
                    logger.error("All API attempts failed for %s", ticker)
                    raise

    # This should never be reached, but just in case
    logger.error("Unexpected end of function for %s", ticker)
    return []


async def sync_watchlist(custom_store: BansheeStore | None = None) -> None:
    target = custom_store or store
    for ticker in target.list_tickers():
        data = await _fetch_api_ninjas(ticker)
        target.record_api_call("earningscalendar", ticker)
        for item in data:
            call_date = item["earnings_date"][:10]
            call_obj = {
                "ticker": ticker,
                "call_date": call_date,
                "call_time": item["earnings_date"],
                "status": "scheduled",
            }
            target.schedule_call(call_obj)


@app.post("/tasks/daily-sync")
async def daily_sync(_: str = Depends(validate_key)) -> dict[str, str]:
    await sync_watchlist()
    return {"status": "ok"}


@app.post("/tasks/upcoming-sync")
async def upcoming_sync(_: str = Depends(validate_key)) -> dict[str, str]:
    """Refresh upcoming earnings calls and clean up stale data."""
    logger = logging.getLogger(__name__)
    logger.info("Starting comprehensive upcoming earnings sync")

    try:
        # Get current ticker count for reference
        current_tickers = set(store.list_tickers())
        ticker_count = len(current_tickers)
        logger.info(
            "Current watchlist contains %d tickers: %s",
            ticker_count,
            list(current_tickers),
        )

        # Refresh upcoming calls (this will fetch new data and create new calls/emails)
        logger.info("Refreshing upcoming earnings calls from API")
        await refresh_upcoming_calls(store, calls_bucket, email_bucket)

        # Clean up stale data that no longer corresponds to watchlist tickers
        logger.info("Cleaning up stale calls and emails")
        removed_calls = cleanup_calls_queue(calls_bucket, current_tickers)
        removed_emails = cleanup_email_queue(email_bucket, current_tickers)

        # Clean up past/expired data to keep storage lean
        logger.info("Cleaning up past calls and expired emails")
        past_calls, past_emails = cleanup_past_data(calls_bucket, email_bucket)

        # Create detailed response message
        cleanup_details = []
        total_removed_calls = removed_calls + past_calls
        total_removed_emails = removed_emails + past_emails

        if total_removed_calls > 0:
            if removed_calls > 0 and past_calls > 0:
                cleanup_details.append(
                    f"removed {total_removed_calls} call(s) ({removed_calls} stale, {past_calls} past)"
                )
            elif removed_calls > 0:
                cleanup_details.append(f"removed {removed_calls} stale call(s)")
            else:
                cleanup_details.append(f"removed {past_calls} past call(s)")

        if total_removed_emails > 0:
            if removed_emails > 0 and past_emails > 0:
                cleanup_details.append(
                    f"removed {total_removed_emails} email(s) ({removed_emails} stale, {past_emails} expired)"
                )
            elif removed_emails > 0:
                cleanup_details.append(f"removed {removed_emails} stale email(s)")
            else:
                cleanup_details.append(f"removed {past_emails} expired email(s)")

        if cleanup_details:
            cleanup_msg = f" and {', '.join(cleanup_details)}"
        else:
            cleanup_msg = " (no cleanup needed)"

        success_message = f"Sync completed for {ticker_count} ticker(s){cleanup_msg}"
        logger.info(
            "Successfully completed upcoming earnings sync: %s", success_message
        )

        return {"status": "ok", "message": success_message}

    except Exception as e:
        logger.error("Error during upcoming earnings sync: %s", str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to sync upcoming earnings: {str(e)}"
        )


@app.post("/tasks/send-queued-emails")
def send_queued_emails(_: str = Depends(validate_key)) -> dict[str, str]:
    send_due_emails(email_bucket)
    return {"status": "sent"}


# ───────────────────────────────
# Debug / test utility endpoints
# ───────────────────────────────


@app.post("/test-email")
def test_send_email(
    to: str = "gclark0812@gmail.com", _: str = Depends(validate_key)
) -> dict[str, str]:
    """Send a one-off test email via SendGrid.

    Pass a different recipient with ?to=someone@example.com if needed.
    The endpoint returns JSON; detailed success/failure is logged to the
    server console so you can inspect the SendGrid response.
    """

    subject = "Banshee test email"
    body = (
        "This is a test email from the /test-email endpoint to confirm "
        "SendGrid credentials and deliverability. If you received this, "
        "email sending is working 👍."
    )

    # Will raise RuntimeError if SendGrid responds with an error.
    send_email(to, subject, body)

    return {"status": "sent", "recipient": to}
