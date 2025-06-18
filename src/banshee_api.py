from __future__ import annotations

import aiohttp
import httpx
from typing import List
from datetime import datetime, timezone
import logging
import json
import asyncio

from fastapi import Depends, FastAPI, HTTPException, Security, Response
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
import secrets

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
from src.scheduler import BansheeScheduler, get_scheduler, set_scheduler

API_KEY_HEADER = APIKeyHeader(name="X-API-Key")

security = HTTPBasic()

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "user")
    correct_password = secrets.compare_digest(credentials.password, get_setting("BANSHEE_WEB_PASSWORD", default=""))
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def validate_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Validate the API key."""
    expected_key = get_setting("BANSHEE_API_KEY")
    if not secrets.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "APIKey"},
        )
    return api_key


store = BansheeStore(get_setting("BANSHEE_DATA_BUCKET"))
calls_bucket = GcsBucket(get_setting("EARNINGS_BUCKET"))
email_bucket = GcsBucket(get_setting("EMAIL_QUEUE_BUCKET"))
app = FastAPI(title="Banshee API", version="1.0")

# Initialize the scheduler
scheduler = BansheeScheduler(store, calls_bucket, email_bucket)
set_scheduler(scheduler)


class TickerPayload(BaseModel):
    ticker: str
    user: str | None = None


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


@app.post("/watchlist/tickers")
async def create_ticker(ticker: dict, _: str = Depends(validate_key)):
    """Add a ticker to the watchlist."""
    logger = logging.getLogger(__name__)
    ticker_upper = ticker["ticker"].upper()
    logger.info("Received POST request to add ticker: %s", ticker_upper)
    
    # Check if ticker already exists
    current_tickers = store.list_tickers()
    logger.info("Current tickers in watchlist: %s", current_tickers)
    
    if ticker_upper in current_tickers:
        logger.warning("Ticker %s already exists in watchlist", ticker_upper)
        raise HTTPException(
            status_code=409,
            detail=f"Ticker {ticker_upper} already exists in watchlist"
        )
    
    try:
        logger.info("Adding ticker %s to store", ticker_upper)
        store.add_ticker(ticker_upper)
        logger.info("Successfully added ticker %s to store", ticker_upper)
        
        # Notify Raven to process the ticker for all years from 2020 to current year in the background
        logger.info("Notifying Raven to process ticker %s for years 2020 to current year (background)", ticker_upper)
        current_year = datetime.now().year
        for year in range(2020, current_year + 1):
            asyncio.create_task(_notify_raven(ticker_upper, year=year))
        
        # Immediately refresh upcoming calls to ensure the new ticker has an earnings entry
        logger.info("Refreshing upcoming calls for ticker %s", ticker_upper)
        await refresh_upcoming_calls(store, calls_bucket, email_bucket)
        logger.info("Successfully refreshed upcoming calls")
        
        # Cleanup stale artefacts now that the watchlist has changed
        logger.info("Cleaning up stale artefacts")
        remaining_tickers = set(store.list_tickers())
        cleanup_email_queue(email_bucket, remaining_tickers)
        cleanup_calls_queue(calls_bucket, remaining_tickers)
        logger.info("Successfully cleaned up stale artefacts")
        
        return {"message": f"Successfully added {ticker_upper} to watchlist"}
    except Exception as e:
        logger.error("Error adding ticker %s: %s", ticker_upper, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/watchlist/tickers/{ticker}")
async def delete_ticker(ticker: str, _: str = Depends(validate_key)):
    """Delete a ticker from the watchlist."""
    logger = logging.getLogger(__name__)
    logger.info("Received DELETE request for ticker: %s", ticker)
    
    # Check if ticker exists
    tickers = store.list_tickers()
    logger.info("Current tickers in watchlist: %s", tickers)
    
    if ticker not in tickers:
        logger.info("Ticker %s not found in watchlist", ticker)
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found in watchlist")
    
    try:
        logger.info("Removing ticker %s from store", ticker)
        store.remove_ticker(ticker)
        logger.info("Successfully removed ticker %s from store", ticker)
        
        # Clean up related calls and emails
        logger.info("Cleaning up calls queue for ticker %s", ticker)
        cleanup_calls_queue(calls_bucket, set(tickers))
        logger.info("Cleaning up email queue for ticker %s", ticker)
        cleanup_email_queue(email_bucket, set(tickers))
        logger.info("Successfully cleaned up queues for ticker %s", ticker)
        
        return {"message": f"Successfully deleted {ticker} from watchlist"}
    except Exception as e:
        logger.error("Error deleting ticker %s: %s", ticker, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/watchlist/tickers")
async def list_tickers(_: str = Depends(validate_key)):
    """List all tickers in the watchlist."""
    logger = logging.getLogger(__name__)
    logger.info("Received GET request for watchlist tickers")
    
    try:
        tickers = store.list_tickers()
        logger.info("Successfully retrieved %d tickers from watchlist", len(tickers))
        return {"tickers": tickers}
    except Exception as e:
        logger.error("Error retrieving tickers: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


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


@app.get("/email-queue")
async def get_email_queue(_: str = Depends(validate_key)):
    """Return everything currently in banshee-email-queue."""
    logger = logging.getLogger(__name__)
    logger.info("Received GET request for email queue")
    try:
        items = email_bucket.list_json("queue/")
        logger.info("Successfully retrieved %d items from email queue", len(items))
        return {"items": items}
    except Exception as e:
        logger.error("Error retrieving email queue: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/earnings")
async def get_earnings(_: str = Depends(validate_key)):
    """Return everything currently in banshee-earnings."""
    logger = logging.getLogger(__name__)
    logger.info("Received GET request for earnings")
    try:
        items = calls_bucket.list_json("calls/")
        logger.info("Successfully retrieved %d items from earnings", len(items))
        return {"items": items}
    except Exception as e:
        logger.error("Error retrieving earnings: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/daily-sync")
async def daily_sync(_: str = Depends(validate_key)):
    """Trigger daily sync of earnings and watchlist data."""
    logger = logging.getLogger(__name__)
    logger.info("Received POST request for daily sync")
    
    try:
        scheduler_instance = get_scheduler()
        if scheduler_instance:
            await scheduler_instance.trigger_daily_sync()
        else:
            # Fallback to direct calls if scheduler not available
            await refresh_upcoming_calls(store, calls_bucket, email_bucket)
            cleanup_past_data(calls_bucket, email_bucket)
            
        logger.info("Daily sync completed successfully")
        return {"message": "Daily sync completed successfully"}
    except Exception as e:
        logger.error("Error during daily sync: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/upcoming-sync")
async def upcoming_sync(_: str = Depends(validate_key)):
    """Trigger sync of upcoming earnings calls."""
    logger = logging.getLogger(__name__)
    logger.info("Received POST request for upcoming sync")
    
    try:
        await refresh_upcoming_calls(store, calls_bucket, email_bucket)
        logger.info("Upcoming sync completed successfully")
        return {"message": "Upcoming sync completed successfully"}
    except Exception as e:
        logger.error("Error during upcoming sync: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/send-queued-emails")
async def send_queued_emails(_: str = Depends(validate_key)):
    """Send all queued emails that are due."""
    logger = logging.getLogger(__name__)
    logger.info("Received POST request for send queued emails")
    
    try:
        scheduler_instance = get_scheduler()
        if scheduler_instance:
            await scheduler_instance.trigger_email_dispatch()
        else:
            # Fallback to direct call if scheduler not available
            send_due_emails(email_bucket)
            
        logger.info("Queued emails processed successfully")
        return {"message": "Queued emails processed successfully"}
    except Exception as e:
        logger.error("Error processing queued emails: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Start the background scheduler when the application starts."""
    logger = logging.getLogger(__name__)
    logger.info("Starting Banshee API and background scheduler")
    
    try:
        scheduler_instance = get_scheduler()
        if scheduler_instance:
            await scheduler_instance.start()
            logger.info("Background scheduler started successfully")
        else:
            logger.warning("No scheduler instance found - background tasks will not run")
    except Exception as e:
        logger.error("Failed to start background scheduler: %s", str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the background scheduler when the application shuts down."""
    logger = logging.getLogger(__name__)
    logger.info("Shutting down Banshee API and background scheduler")
    
    try:
        scheduler_instance = get_scheduler()
        if scheduler_instance:
            await scheduler_instance.stop()
            logger.info("Background scheduler stopped successfully")
    except Exception as e:
        logger.error("Failed to stop background scheduler: %s", str(e))


async def _notify_raven(
    ticker: str,
    year: int | None = None,
    point_of_origin: str = "banshee",
    include_transcript: bool = True,
    quarter: int | None = None
) -> None:
    """Notify Raven to process filings and/or transcripts for a ticker.
    
    Args:
        ticker: The stock ticker symbol to process
        year: The year to process (defaults to current year)
        point_of_origin: The origin of the request (defaults to "banshee")
        include_transcript: Whether to include transcript processing (defaults to True)
        quarter: The quarter to process (optional)
        
    Raises:
        RuntimeError: If the Raven API request fails after all retries
    """
    logger = logging.getLogger(__name__)
    
    # Get and validate Raven URL
    url = get_setting("RAVEN_URL", default="https://filing-fetcher-api-455624753981.us-central1.run.app")
    if not url:
        logger.error("RAVEN_URL environment variable is not set")
        raise RuntimeError("RAVEN_URL environment variable is not set")
        
    # Ensure URL has proper scheme
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    url = url.rstrip("/") + "/process"
    
    logger.info("Using Raven URL: %s", url)
    
    # Set default year if not provided
    if year is None:
        year = datetime.now().year
        
    # Prepare request payload
    payload = {
        "ticker": ticker.upper(),
        "year": year,
        "point_of_origin": point_of_origin,
        "include_transcript": include_transcript
    }
    if quarter is not None:
        payload["quarter"] = quarter
        
    logger.info("Prepared Raven payload for %s: %s", ticker, payload)
    
    # Get API key
    api_key = get_setting("RAVEN_API_KEY")
    if not api_key:
        logger.error("RAVEN_API_KEY environment variable is not set")
        raise RuntimeError("RAVEN_API_KEY environment variable is not set")
    
    headers = {"X-API-Key": api_key}
    
    # Retry configuration
    max_retries = 3
    retry_delay = 1.0  # seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Notifying Raven to process %s for year %d (attempt %d/%d)", 
                       ticker, year, attempt, max_retries)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                await response.raise_for_status()
                
                logger.info("Successfully notified Raven to process %s (attempt %d)", 
                           ticker, attempt)
                return  # Success, exit the retry loop
                
        except httpx.ConnectError as e:
            error_msg = f"Connection error notifying Raven for {ticker} (attempt {attempt}/{max_retries}): {str(e)}"
            logger.error(error_msg)
            
            if attempt < max_retries:
                logger.info("Retrying in %.1f seconds...", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                logger.error("All connection attempts failed for %s", ticker)
                raise RuntimeError(f"Failed to connect to Raven for {ticker} after {max_retries} attempts: {str(e)}") from e
                
        except httpx.HTTPError as e:
            error_msg = f"HTTP error notifying Raven for {ticker} (attempt {attempt}/{max_retries}): {str(e)}"
            logger.error(error_msg)
            
            if attempt < max_retries:
                logger.info("Retrying in %.1f seconds...", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                logger.error("All HTTP attempts failed for %s", ticker)
                raise RuntimeError(f"Failed to notify Raven for {ticker} after {max_retries} attempts: {str(e)}") from e
                
        except Exception as e:
            error_msg = f"Unexpected error notifying Raven for {ticker} (attempt {attempt}/{max_retries}): {str(e)}"
            logger.error(error_msg)
            
            if attempt < max_retries:
                logger.info("Retrying in %.1f seconds...", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                logger.error("All attempts failed for %s", ticker)
                raise RuntimeError(f"Unexpected error notifying Raven for {ticker} after {max_retries} attempts: {str(e)}") from e
    
    # This should never be reached, but just in case
    logger.error("Unexpected end of retry loop for %s", ticker)
    raise RuntimeError(f"Unexpected end of retry loop for {ticker}")


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


# Add logging to store methods
def log_store_operation(operation: str, ticker: str):
    logger = logging.getLogger(__name__)
    logger.info("Store operation '%s' for ticker %s", operation, ticker)

# Wrap store methods with logging
original_list_tickers = store.list_tickers
def list_tickers_with_logging():
    log_store_operation("list_tickers", "all")
    return original_list_tickers()
store.list_tickers = list_tickers_with_logging

original_add_ticker = store.add_ticker
def add_ticker_with_logging(ticker: str):
    log_store_operation("add_ticker", ticker)
    return original_add_ticker(ticker)
store.add_ticker = add_ticker_with_logging

original_remove_ticker = store.remove_ticker
def remove_ticker_with_logging(ticker: str):
    log_store_operation("remove_ticker", ticker)
    return original_remove_ticker(ticker)
store.remove_ticker = remove_ticker_with_logging
