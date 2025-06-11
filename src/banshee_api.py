from __future__ import annotations

import aiohttp
from typing import List
from datetime import datetime, timezone
import logging
import json

from fastapi import Depends, FastAPI, HTTPException, Security, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import secrets
from fastapi.staticfiles import StaticFiles

from src.notifications import send_alert

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

# Serve static files (for logo, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Simple session storage for authenticated users (in production, use proper session management)
authenticated_sessions = set()


def check_web_auth(request: Request):
    """Check if the user is authenticated for web access."""
    session_id = request.cookies.get("banshee_session")
    if session_id not in authenticated_sessions:
        raise HTTPException(status_code=401, detail="Authentication required")
    return True


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
    """Redirect root to the web interface."""
    return RedirectResponse(url="/web")


@app.post("/web-login")
def web_login(password: str = Form(...)):
    """Simple password-based login for web interface."""
    expected_password = get_setting("BANSHEE_WEB_PASSWORD")
    if not secrets.compare_digest(password, expected_password):
        return HTMLResponse(
            content=LOGIN_HTML.replace(
                "{error}",
                "<div class='error'><i class='fas fa-exclamation-triangle'></i>Invalid password. Please try again.</div>",
            ),
            status_code=401,
        )

    # Create a simple session token
    import uuid

    session_id = str(uuid.uuid4())
    authenticated_sessions.add(session_id)

    # Redirect to main page with session cookie
    response = RedirectResponse(url="/web", status_code=302)
    response.set_cookie("banshee_session", session_id, max_age=3600 * 24)  # 24 hours
    return response


@app.get("/watchlist")
def read_watchlist(_: str = Depends(validate_key)) -> dict[str, List[str]]:
    return {"tickers": store.list_tickers()}


@app.get("/public/watchlist")
def read_watchlist_public() -> dict[str, List[str]]:
    """Get the current watchlist - public endpoint."""
    return {"tickers": store.list_tickers()}


@app.post("/watchlist")
async def create_watchlist(
    payload: TickerPayload, _: str = Depends(validate_key)
) -> dict[str, str]:
    store.add_ticker(payload.ticker, payload.user)
    await refresh_upcoming_calls(store, calls_bucket, email_bucket)
    cleanup_calls_queue(calls_bucket, set(store.list_tickers()))
    cleanup_email_queue(email_bucket, set(store.list_tickers()))
    return {"message": "added"}


@app.delete("/watchlist/{ticker}")
async def delete_watchlist(ticker: str, _: str = Depends(validate_key)) -> dict[str, str]:
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
                status_code=404, 
                detail=f"Ticker {ticker_upper} not found in watchlist"
            )
        
        # Count items before cleanup for reporting
        logger.info("Counting existing calls and emails for %s before cleanup", ticker_upper)
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
                    
            logger.info("Found %d calls and %d emails for %s", 
                       len(calls_before), len(emails_before), ticker_upper)
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
                cleanup_details.append(f"removed {total_removed_calls} call(s) ({removed_calls} stale, {past_calls} past)")
            elif removed_calls > 0:
                cleanup_details.append(f"removed {removed_calls} stale call(s)")
            else:
                cleanup_details.append(f"removed {past_calls} past call(s)")
                
        if total_removed_emails > 0:
            if removed_emails > 0 and past_emails > 0:
                cleanup_details.append(f"removed {total_removed_emails} email(s) ({removed_emails} stale, {past_emails} expired)")
            elif removed_emails > 0:
                cleanup_details.append(f"removed {removed_emails} stale email(s)")
            else:
                cleanup_details.append(f"removed {past_emails} expired email(s)")
            
        if cleanup_details:
            cleanup_msg = f" and {', '.join(cleanup_details)}"
        else:
            cleanup_msg = " (no cleanup needed)"
            
        success_message = f"{ticker_upper} removed from watchlist{cleanup_msg}"
        logger.info("Successfully completed deletion for %s: %s", ticker_upper, success_message)
        
        return {"message": success_message}
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        logger.error("Error deleting ticker %s: %s", ticker_upper, str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove {ticker_upper} from watchlist: {str(e)}"
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
                    logger.info("Skipping past call: %s at %s", call_data["ticker"], call_time_str)
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
                logger.info("Added upcoming call: %s on %s", call.ticker, call.call_date)
                
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
        return UpcomingCallsResponse(
            calls=[], total_count=0, next_call=None
        )


@app.get("/public/earnings/upcoming")
async def get_upcoming_earnings_public() -> UpcomingCallsResponse:
    """Get upcoming earnings calls from GCS storage - public endpoint."""
    logger = logging.getLogger(__name__)
    logger.info("Fetching upcoming earnings from GCS storage (public endpoint)")
    
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
                    logger.info("Skipping past call: %s at %s", call_data["ticker"], call_time_str)
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
                logger.info("Added upcoming call: %s on %s", call.ticker, call.call_date)
                
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
        return UpcomingCallsResponse(
            calls=[], total_count=0, next_call=None
        )


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
            "url": f"https://api.api-ninjas.com/v1/earningscalendar?ticker={ticker}&show_upcoming=true",
            "name": "upcoming_only",
            "expected_field": "date"  # Official API docs show 'date' field
        },
        {
            "url": f"https://api.api-ninjas.com/v1/earningscalendar?ticker={ticker}",
            "name": "historical_data",
            "expected_field": "date"
        }
    ]
    
    headers = {"X-Api-Key": get_setting("API_NINJAS_KEY")}
    
    for attempt_num, attempt in enumerate(api_attempts, 1):
        logger.info("API attempt %d/%d for %s using %s", attempt_num, len(api_attempts), ticker, attempt["name"])
        logger.info("Request URL: %s", attempt["url"])
        logger.info("Request headers: %s", {k: v[:10] + "..." if k == "X-Api-Key" and len(v) > 10 else v for k, v in headers.items()})
        
        async with aiohttp.ClientSession() as sess:
            try:
                async with sess.get(attempt["url"], headers=headers) as resp:
                    logger.info("API response status for %s (attempt %d): %d", ticker, attempt_num, resp.status)
                    
                    if resp.status != 200:
                        logger.error("API Ninjas error for %s (attempt %d): status %d", ticker, attempt_num, resp.status)
                        response_text = await resp.text()
                        logger.error("Error response body for %s (attempt %d): %s", ticker, attempt_num, response_text)
                        
                        # If this isn't the last attempt, continue to next one
                        if attempt_num < len(api_attempts):
                            logger.info("Trying next API approach for %s", ticker)
                            continue
                        else:
                            raise RuntimeError(f"All API attempts failed for {ticker}")
                    
                    result = await resp.json()
                    logger.info("API response for %s (attempt %d): %s", ticker, attempt_num, json.dumps(result, indent=2) if result else "[]")
                    
                    # Check if this result has usable data
                    if result and isinstance(result, list) and len(result) > 0:
                        # Prioritize 'date' field as documented, with fallbacks
                        date_fields = ['date', 'earnings_date', 'announcement_date', 'report_date', 'call_date', 'earnings_call_date']
                        
                        usable_items = 0
                        for item in result:
                            if any(field in item and item[field] for field in date_fields):
                                usable_items += 1
                        
                        logger.info("Found %d usable items out of %d total for %s (attempt %d)", 
                                  usable_items, len(result), ticker, attempt_num)
                        
                        if usable_items > 0:
                            logger.info("Successfully retrieved usable data for %s using %s", ticker, attempt["name"])
                            return result
                        else:
                            logger.warning("No usable date fields found in response for %s (attempt %d)", ticker, attempt_num)
                            if attempt_num < len(api_attempts):
                                logger.info("Trying next API approach for %s", ticker)
                                continue
                    else:
                        logger.warning("Empty or invalid result for %s (attempt %d)", ticker, attempt_num)
                        if attempt_num < len(api_attempts):
                            logger.info("Trying next API approach for %s", ticker)
                            continue
                    
                    # If we get here and it's the last attempt, return whatever we got
                    if attempt_num == len(api_attempts):
                        logger.warning("Returning potentially empty result for %s after all attempts", ticker)
                        return result or []
                        
            except Exception as e:
                logger.error("Exception during API request for %s (attempt %d): %s", ticker, attempt_num, str(e))
                if attempt_num < len(api_attempts):
                    logger.info("Trying next API approach for %s due to exception", ticker)
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
        logger.info("Current watchlist contains %d tickers: %s", ticker_count, list(current_tickers))
        
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
                cleanup_details.append(f"removed {total_removed_calls} call(s) ({removed_calls} stale, {past_calls} past)")
            elif removed_calls > 0:
                cleanup_details.append(f"removed {removed_calls} stale call(s)")
            else:
                cleanup_details.append(f"removed {past_calls} past call(s)")
                
        if total_removed_emails > 0:
            if removed_emails > 0 and past_emails > 0:
                cleanup_details.append(f"removed {total_removed_emails} email(s) ({removed_emails} stale, {past_emails} expired)")
            elif removed_emails > 0:
                cleanup_details.append(f"removed {removed_emails} stale email(s)")
            else:
                cleanup_details.append(f"removed {past_emails} expired email(s)")
            
        if cleanup_details:
            cleanup_msg = f" and {', '.join(cleanup_details)}"
        else:
            cleanup_msg = " (no cleanup needed)"
            
        success_message = f"Sync completed for {ticker_count} ticker(s){cleanup_msg}"
        logger.info("Successfully completed upcoming earnings sync: %s", success_message)
        
        return {"status": "ok", "message": success_message}
        
    except Exception as e:
        logger.error("Error during upcoming earnings sync: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync upcoming earnings: {str(e)}"
        )


@app.post("/tasks/send-queued-emails")
def send_queued_emails(_: str = Depends(validate_key)) -> dict[str, str]:
    send_due_emails(email_bucket)
    return {"status": "sent"}


LOGIN_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Banshee - Earnings Monitor</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 448 512'><path fill='%23667eea' d='M384 32c35.3 0 64 28.7 64 64v320c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96C0 60.7 28.7 32 64 32h320zM160 144c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm16 80h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16s7.2-16 16-16zm-16 80c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm144-96c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32zm16 48c0-8.8-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32c8.8 0 16-7.2 16-16zm-16 80c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32z'/></svg>" type="image/svg+xml">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1rem;
    }
    .login-container {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(20px);
      padding: 2.5rem;
      border-radius: 20px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.1), 0 0 0 1px rgba(255,255,255,0.1);
      width: 100%;
      max-width: 420px;
      border: 1px solid rgba(255, 255, 255, 0.2);
    }
    .header {
      text-align: center;
      margin-bottom: 2rem;
    }
    .logo {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 80px;
      height: 80px;
      background: linear-gradient(135deg, #667eea, #764ba2);
      border-radius: 20px;
      margin-bottom: 1rem;
      box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
    }
    .logo i {
      font-size: 2.5rem;
      color: white;
    }
    h1 {
      color: #2c3e50;
      margin-bottom: 0.5rem;
      font-size: 1.75rem;
      font-weight: 600;
    }
    .subtitle {
      color: #64748b;
      font-size: 0.95rem;
      font-weight: 400;
    }
    .form-group {
      margin-bottom: 1.5rem;
      position: relative;
    }
    label {
      display: block;
      margin-bottom: 0.5rem;
      color: #374151;
      font-weight: 500;
      font-size: 0.9rem;
    }
    .input-wrapper {
      position: relative;
    }
    .input-icon {
      position: absolute;
      left: 1rem;
      top: 50%;
      transform: translateY(-50%);
      color: #9ca3af;
      z-index: 1;
    }
    input[type="password"] {
      width: 100%;
      padding: 1rem 1rem 1rem 3rem;
      border: 2px solid #e5e7eb;
      border-radius: 12px;
      font-size: 1rem;
      transition: all 0.2s ease;
      background: rgba(255, 255, 255, 0.8);
      backdrop-filter: blur(10px);
    }
    input[type="password"]:focus {
      outline: none;
      border-color: #667eea;
      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
      background: rgba(255, 255, 255, 0.95);
    }
    button {
      width: 100%;
      background: linear-gradient(135deg, #667eea, #764ba2);
      color: white;
      border: none;
      padding: 1rem;
      border-radius: 12px;
      cursor: pointer;
      font-size: 1rem;
      font-weight: 600;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    button:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    button:active {
      transform: translateY(0);
    }
    .error {
      background: linear-gradient(135deg, #fef2f2, #fee2e2);
      color: #dc2626;
      padding: 1rem;
      border-radius: 12px;
      margin-bottom: 1.5rem;
      border: 1px solid #fecaca;
      text-align: center;
      font-weight: 500;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
    }
    .features {
      margin-top: 2rem;
      padding-top: 1.5rem;
      border-top: 1px solid #e5e7eb;
    }
    .feature {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 0.75rem;
      color: #6b7280;
      font-size: 0.9rem;
    }
    .feature-icon {
      color: #667eea;
      width: 16px;
    }
    @media (max-width: 480px) {
      .login-container {
        padding: 2rem 1.5rem;
        border-radius: 16px;
      }
      h1 {
        font-size: 1.5rem;
      }
      .logo {
        width: 70px;
        height: 70px;
      }
      .logo i {
        font-size: 2rem;
      }
    }
    @media (max-width: 360px) {
      body {
        padding: 0.5rem;
      }
      .login-container {
        padding: 1.5rem 1rem;
      }
    }
  </style>
  <meta property="og:image" content="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 448 512'><path fill='%23667eea' d='M384 32c35.3 0 64 28.7 64 64v320c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96C0 60.7 28.7 32 64 32h320zM160 144c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm16 80h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16s7.2-16 16-16zm-16 80c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm144-96c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32zm16 48c0-8.8-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32c8.8 0 16-7.2 16-16zm-16 80c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32z'/></svg>">
  <meta name="twitter:image" content="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 448 512'><path fill='%23667eea' d='M384 32c35.3 0 64 28.7 64 64v320c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96C0 60.7 28.7 32 64 32h320zM160 144c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm16 80h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16s7.2-16 16-16zm-16 80c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm144-96c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32zm16 48c0-8.8-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32c8.8 0 16-7.2 16-16zm-16 80c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32z'/></svg>">
  <meta property="og:title" content="Banshee - Earnings Monitor">
  <meta property="og:description" content="Monitor earnings calls & market alerts">
  <meta name="twitter:card" content="summary_large_image">
</head>
<body>
  <div class="login-container">
    <div class="header">
      <div class="logo">
        <i class="fas fa-chart-line"></i>
      </div>
      <h1>Banshee Access</h1>
      <p class="subtitle">Monitor earnings calls & market alerts</p>
    </div>
    
    {error}
    
    <form method="post" action="/web-login">
      <div class="form-group">
        <label for="password">
          <i class="fas fa-shield-alt"></i> Access Code
        </label>
        <div class="input-wrapper">
          <i class="fas fa-lock input-icon"></i>
          <input type="password" id="password" name="password" required autofocus autocomplete="current-password">
        </div>
      </div>
      <button type="submit">
        <i class="fas fa-sign-in-alt"></i>
        Access Dashboard
      </button>
    </form>
    
    <div class="features">
      <div class="feature">
        <i class="fas fa-eye feature-icon"></i>
        <span>Real-time earnings monitoring</span>
      </div>
      <div class="feature">
        <i class="fas fa-bell feature-icon"></i>
        <span>Intelligent alert system</span>
      </div>
      <div class="feature">
        <i class="fas fa-mobile-alt feature-icon"></i>
        <span>Mobile-optimized interface</span>
      </div>
    </div>
  </div>
</body>
</html>
"""


WATCHLIST_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Banshee - Earnings Monitor</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 448 512'><path fill='%23667eea' d='M384 32c35.3 0 64 28.7 64 64v320c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96C0 60.7 28.7 32 64 32h320zM160 144c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm16 80h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16s7.2-16 16-16zm-16 80c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm144-96c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32zm16 48c0-8.8-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32c8.8 0 16-7.2 16-16zm-16 80c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32z'/></svg>" type="image/svg+xml">
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    html, body {
      height: 100%;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      line-height: 1.6;
      color: #1f2937;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      background-attachment: fixed;
    }
    .container {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(20px);
      border-radius: 24px;
      padding: 2rem;
      box-shadow: 0 25px 50px rgba(0,0,0,0.1), 0 0 0 1px rgba(255,255,255,0.1);
      max-width: 1200px;
      margin: 1rem auto;
      min-height: calc(100vh - 2rem);
      border: 1px solid rgba(255, 255, 255, 0.2);
    }
    .header {
      text-align: center;
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 2px solid rgba(102, 126, 234, 0.1);
      position: relative;
    }
    .logo {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 60px;
      height: 60px;
      background: linear-gradient(135deg, #667eea, #764ba2);
      border-radius: 16px;
      margin-bottom: 1rem;
      box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
    }
    .logo i {
      font-size: 1.5rem;
      color: white;
    }
    h1 {
      color: #1f2937;
      margin-bottom: 0.5rem;
      font-size: 2rem;
      font-weight: 700;
      background: linear-gradient(135deg, #667eea, #764ba2);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .subtitle {
      color: #6b7280;
      font-size: 1rem;
      font-weight: 400;
    }
    .header-controls {
      position: absolute;
      top: 0;
      right: 0;
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    .progress-container {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
      background: rgba(255, 255, 255, 0.1);
      backdrop-filter: blur(10px);
      z-index: 1001;
      opacity: 0;
      transition: opacity 0.3s ease;
    }
    .progress-container.active {
      opacity: 1;
    }
    .progress-bar {
      height: 100%;
      background: linear-gradient(90deg, #667eea, #764ba2, #10b981);
      background-size: 300% 100%;
      width: 0%;
      transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
      animation: shimmer 2s ease-in-out infinite;
      border-radius: 0 2px 2px 0;
      box-shadow: 0 0 20px rgba(102, 126, 234, 0.3);
    }
    @keyframes shimmer {
      0% { background-position: 300% 0; }
      100% { background-position: -300% 0; }
    }
    .refresh-btn {
      background: linear-gradient(135deg, #10b981, #059669);
      color: white;
      border: none;
      padding: 0.875rem 1.25rem;
      border-radius: 12px;
      cursor: pointer;
      font-size: 0.9rem;
      font-weight: 600;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      display: flex;
      align-items: center;
      gap: 0.5rem;
      box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
      position: relative;
      overflow: hidden;
    }
    .refresh-btn:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(16, 185, 129, 0.4);
    }
    .refresh-btn:active {
      transform: translateY(0);
    }
    .refresh-btn:disabled {
      opacity: 0.7;
      cursor: not-allowed;
      transform: none;
    }
    .refresh-btn.loading {
      background: linear-gradient(135deg, #6b7280, #4b5563);
      box-shadow: 0 4px 15px rgba(107, 114, 128, 0.3);
    }
    .refresh-btn.loading i {
      animation: spin 1s linear infinite;
    }
    .refresh-btn::before {
      content: '';
      position: absolute;
      top: 0;
      left: -100%;
      width: 100%;
      height: 100%;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
      transition: left 0.5s ease;
    }
    .refresh-btn:hover::before {
      left: 100%;
    }
    .step-indicator {
      position: fixed;
      top: 50px;
      right: 20px;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(20px);
      padding: 1rem;
      border-radius: 12px;
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.2);
      z-index: 1000;
      opacity: 0;
      transform: translateX(100%);
      transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
      min-width: 250px;
    }
    .step-indicator.active {
      opacity: 1;
      transform: translateX(0);
    }
    .step-list {
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .step-item {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.5rem 0;
      transition: all 0.3s ease;
    }
    .step-icon {
      width: 20px;
      height: 20px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.75rem;
      transition: all 0.3s ease;
    }
    .step-icon.pending {
      background: #e5e7eb;
      color: #9ca3af;
    }
    .step-icon.active {
      background: linear-gradient(135deg, #667eea, #764ba2);
      color: white;
      animation: pulse 1.5s ease-in-out infinite;
    }
    .step-icon.completed {
      background: linear-gradient(135deg, #10b981, #059669);
      color: white;
    }
    .step-text {
      flex: 1;
      font-size: 0.875rem;
      font-weight: 500;
      transition: color 0.3s ease;
    }
    .step-item.pending .step-text {
      color: #9ca3af;
    }
    .step-item.active .step-text {
      color: #667eea;
      font-weight: 600;
    }
    .step-item.completed .step-text {
      color: #10b981;
    }
    @keyframes pulse {
      0%, 100% { transform: scale(1); }
      50% { transform: scale(1.1); }
    }
    .nav-tabs {
      display: flex;
      background: rgba(243, 244, 246, 0.6);
      border-radius: 16px;
      padding: 0.25rem;
      margin-bottom: 2rem;
      backdrop-filter: blur(10px);
      border: 1px solid rgba(229, 231, 235, 0.8);
    }
    .nav-tab {
      flex: 1;
      text-align: center;
      padding: 0.875rem 1rem;
      background: none;
      border: none;
      font-size: 0.95rem;
      font-weight: 600;
      color: #6b7280;
      cursor: pointer;
      transition: all 0.2s ease;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
    }
    .nav-tab.active {
      background: linear-gradient(135deg, #667eea, #764ba2);
      color: white;
      box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
      transform: translateY(-1px);
    }
    .nav-tab:hover:not(.active) {
      background: rgba(102, 126, 234, 0.1);
      color: #667eea;
    }
    .tab-content {
      display: none;
    }
    .tab-content.active {
      display: block;
    }
    .stats-card {
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
      border: 1px solid rgba(102, 126, 234, 0.2);
      border-radius: 16px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
      backdrop-filter: blur(10px);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .stats {
      color: #667eea;
      font-weight: 600;
      font-size: 1.1rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .add-form {
      background: rgba(248, 250, 252, 0.8);
      border: 1px solid rgba(226, 232, 240, 0.8);
      padding: 1.5rem;
      border-radius: 20px;
      margin-bottom: 1.5rem;
      backdrop-filter: blur(10px);
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
    }
    .form-header {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1rem;
      color: #374151;
      font-weight: 600;
    }
    .form-header i {
      color: #667eea;
    }
    .form-row {
      display: flex;
      gap: 0.75rem;
      margin-bottom: 0.75rem;
    }
    .input-group {
      position: relative;
      flex: 1;
    }
    .input-icon {
      position: absolute;
      left: 1rem;
      top: 50%;
      transform: translateY(-50%);
      color: #9ca3af;
      z-index: 1;
    }
    input[type="text"] {
      width: 100%;
      padding: 1rem 1rem 1rem 3rem;
      border: 2px solid #e5e7eb;
      border-radius: 12px;
      font-size: 1rem;
      transition: all 0.2s ease;
      background: rgba(255, 255, 255, 0.8);
      backdrop-filter: blur(10px);
    }
    input[type="text"]:focus {
      outline: none;
      border-color: #667eea;
      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
      background: rgba(255, 255, 255, 0.95);
    }
    button {
      background: linear-gradient(135deg, #667eea, #764ba2);
      color: white;
      border: none;
      padding: 1rem 1.5rem;
      border-radius: 12px;
      cursor: pointer;
      font-size: 1rem;
      font-weight: 600;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
      white-space: nowrap;
    }
    button:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    button:active {
      transform: translateY(0);
    }
    .delete-btn {
      background: linear-gradient(135deg, #ef4444, #dc2626);
      padding: 0.5rem 1rem;
      font-size: 0.875rem;
      box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
      border-radius: 8px;
    }
    .delete-btn:hover {
      box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
    }
    .watchlist, .earnings-list {
      list-style: none;
      display: grid;
      gap: 1rem;
    }
    .card {
      background: rgba(255, 255, 255, 0.9);
      backdrop-filter: blur(15px);
      border: 1px solid rgba(229, 231, 235, 0.8);
      border-radius: 16px;
      padding: 1.25rem;
      transition: all 0.2s ease;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    }
    .card:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
      border-color: rgba(102, 126, 234, 0.3);
    }
    .ticker-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
    }
    .earnings-item {
      cursor: default;
    }
    .ticker-info {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .ticker-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      background: linear-gradient(135deg, #667eea, #764ba2);
      border-radius: 10px;
      color: white;
      font-weight: 600;
      font-size: 0.875rem;
    }
    .ticker-name {
      font-weight: 700;
      color: #1f2937;
      font-size: 1.125rem;
    }
    .earnings-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      cursor: pointer;
      padding-bottom: 1rem;
      border-bottom: 1px solid rgba(229, 231, 235, 0.6);
    }
    .earnings-details {
      display: none;
      padding-top: 1rem;
    }
    .earnings-details.show {
      display: block;
    }
    .earnings-ticker {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .earnings-time {
      color: #6b7280;
      font-size: 0.875rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .countdown {
      font-family: 'Monaco', 'Consolas', monospace;
      font-size: 1rem;
      font-weight: 700;
      padding: 0.5rem 0.75rem;
      border-radius: 8px;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .countdown.urgent {
      background: linear-gradient(135deg, #fef2f2, #fee2e2);
      color: #dc2626;
      border: 1px solid #fecaca;
      animation: pulse 1s infinite;
    }
    .countdown.soon {
      background: linear-gradient(135deg, #fffbeb, #fef3c7);
      color: #d97706;
      border: 1px solid #fed7aa;
    }
    .countdown.normal {
      background: linear-gradient(135deg, #f0fdf4, #dcfce7);
      color: #16a34a;
      border: 1px solid #bbf7d0;
    }
    @keyframes pulse {
      0% { opacity: 1; }
      50% { opacity: 0.7; }
      100% { opacity: 1; }
    }
    .empty-state {
      text-align: center;
      color: #6b7280;
      font-style: italic;
      padding: 3rem 2rem;
      background: linear-gradient(135deg, rgba(248, 250, 252, 0.8), rgba(241, 245, 249, 0.8));
      border-radius: 16px;
      border: 2px dashed #cbd5e1;
      backdrop-filter: blur(10px);
    }
    .empty-icon {
      font-size: 3rem;
      color: #cbd5e1;
      margin-bottom: 1rem;
    }
    .loading {
      text-align: center;
      color: #667eea;
      font-weight: 600;
      padding: 2rem;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
    }
    .loading i {
      animation: spin 1s linear infinite;
    }
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    .message {
      margin-bottom: 1.5rem;
    }
    .error {
      background: linear-gradient(135deg, #fef2f2, #fee2e2);
      color: #dc2626;
      padding: 1rem;
      border-radius: 12px;
      border: 1px solid #fecaca;
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-weight: 500;
    }
    .success {
      background: linear-gradient(135deg, #f0fdf4, #dcfce7);
      color: #16a34a;
      padding: 1rem;
      border-radius: 12px;
      border: 1px solid #bbf7d0;
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-weight: 500;
    }
    .modal {
      display: none;
      position: fixed;
      z-index: 1000;
      left: 0;
      top: 0;
      width: 100%;
      height: 100%;
      background-color: rgba(0,0,0,0.6);
      backdrop-filter: blur(4px);
    }
    .modal-content {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(20px);
      margin: 5% auto;
      padding: 2rem;
      border-radius: 20px;
      width: 90%;
      max-width: 600px;
      box-shadow: 0 25px 50px rgba(0,0,0,0.2);
      border: 1px solid rgba(255, 255, 255, 0.2);
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.5rem;
      padding-bottom: 1rem;
      border-bottom: 2px solid rgba(229, 231, 235, 0.6);
    }
    .modal-title {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      color: #1f2937;
      font-weight: 700;
      font-size: 1.25rem;
    }
    .close {
      color: #9ca3af;
      font-size: 1.5rem;
      font-weight: bold;
      cursor: pointer;
      line-height: 1;
      padding: 0.5rem;
      border-radius: 8px;
      transition: all 0.2s ease;
    }
    .close:hover {
      color: #667eea;
      background: rgba(102, 126, 234, 0.1);
    }
    .modal-countdown {
      text-align: center;
      font-family: 'Monaco', 'Consolas', monospace;
      font-size: 2.5rem;
      font-weight: 700;
      margin: 1.5rem 0;
      padding: 2rem;
      background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
      border-radius: 16px;
      border: 2px solid rgba(102, 126, 234, 0.2);
      color: #667eea;
    }
    .earnings-info {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-top: 1.5rem;
    }
    .info-item {
      padding: 1rem;
      background: rgba(248, 250, 252, 0.8);
      border-radius: 12px;
      border: 1px solid rgba(226, 232, 240, 0.8);
      backdrop-filter: blur(10px);
    }
    .info-label {
      font-weight: 600;
      color: #374151;
      font-size: 0.875rem;
      margin-bottom: 0.25rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .info-value {
      color: #667eea;
      font-size: 1.125rem;
      font-weight: 700;
    }
    
    /* Desktop delete button - hidden on mobile */
    .desktop-delete {
      display: flex;
    }
    
    /* Mobile delete button - hidden by default, shown on mobile */
    .mobile-delete {
      display: none;
    }
    
    /* Mobile-specific styles */
    @media (max-width: 768px) {
      .header-controls {
        position: relative;
        top: auto;
        right: auto;
        justify-content: center;
        margin-top: 1rem;
      }
      
      .refresh-btn {
        padding: 0.75rem 1rem;
        font-size: 0.875rem;
      }
      
      .step-indicator {
        top: 10px;
        right: 10px;
        left: 10px;
        transform: translateY(-100%);
        min-width: auto;
        max-width: none;
      }
      
      .step-indicator.active {
        transform: translateY(0);
      }
      
      .step-item {
        padding: 0.375rem 0;
      }
      
      .step-text {
        font-size: 0.8125rem;
      }
      
      .desktop-delete {
        display: none;
      }
      
      .card {
        padding: 1rem;
        border-radius: 12px;
      }
      
      .ticker-item {
        flex-direction: column;
        align-items: stretch;
        gap: 1rem;
      }
      
      .ticker-info {
        justify-content: center;
      }
      
      .mobile-delete {
        display: flex;
        justify-content: center;
        width: 100%;
      }
      
      .delete-btn {
        width: 100%;
        max-width: 200px;
        justify-content: center;
        padding: 0.75rem 1rem;
      }
      
      .container {
        margin: 0.5rem;
        padding: 1.5rem;
        min-height: calc(100vh - 1rem);
        border-radius: 20px;
      }
      h1 {
        font-size: 1.75rem;
      }
      .form-row {
        flex-direction: column;
      }
      .nav-tab {
        font-size: 0.875rem;
        padding: 0.75rem 0.5rem;
      }
      .modal-content {
        margin: 10% auto;
        width: 95%;
        padding: 1.5rem;
      }
      .modal-countdown {
        font-size: 2rem;
        padding: 1.5rem;
      }
      .earnings-info {
        grid-template-columns: 1fr;
      }
    }

    /* Hide deprecated refresh UI */
    #progress-container,
    #step-indicator,
    .refresh-btn,
    .header-controls {
      display: none !important;
    }
  </style>
  <meta property="og:image" content="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 448 512'><path fill='%23667eea' d='M384 32c35.3 0 64 28.7 64 64v320c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96C0 60.7 28.7 32 64 32h320zM160 144c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm16 80h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16s7.2-16 16-16zm-16 80c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm144-96c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32zm16 48c0-8.8-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32c8.8 0 16-7.2 16-16zm-16 80c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32z'/></svg>">
  <meta name="twitter:image" content="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 448 512'><path fill='%23667eea' d='M384 32c35.3 0 64 28.7 64 64v320c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V96C0 60.7 28.7 32 64 32h320zM160 144c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm16 80h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16s7.2-16 16-16zm-16 80c0-8.8 7.2-16 16-16h32c8.8 0 16 7.2 16 16s-7.2 16-16 16H176c-8.8 0-16-7.2-16-16zm144-96c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32zm16 48c0-8.8-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32c8.8 0 16-7.2 16-16zm-16 80c8.8 0 16-7.2 16-16s-7.2-16-16-16H272c-8.8 0-16 7.2-16 16s7.2 16 16 16h32z'/></svg>">
  <meta property="og:title" content="Banshee - Earnings Monitor">
  <meta property="og:description" content="Monitor earnings calls & market alerts">
  <meta name="twitter:card" content="summary_large_image">
</head>
<body>
  <!-- Progress bar at the top -->
  <div id="progress-container" class="progress-container">
    <div id="progress-bar" class="progress-bar"></div>
  </div>
  
  <!-- Step indicator -->
  <div id="step-indicator" class="step-indicator">
    <ul id="step-list" class="step-list">
      <li class="step-item pending" id="step-1">
        <div class="step-icon">1</div>
        <div class="step-text">Preparing sync...</div>
      </li>
      <li class="step-item pending" id="step-2">
        <div class="step-icon">2</div>
        <div class="step-text">Fetching data...</div>
      </li>
      <li class="step-item pending" id="step-3">
        <div class="step-icon">3</div>
        <div class="step-text">Cleaning stale data...</div>
      </li>
      <li class="step-item pending" id="step-4">
        <div class="step-icon">4</div>
        <div class="step-text">Updating storage...</div>
      </li>
      <li class="step-item pending" id="step-5">
        <div class="step-icon">5</div>
        <div class="step-text">Refreshing display...</div>
      </li>
    </ul>
  </div>

  <div class="container">
    <div class="header">
      <div class="header-controls">
        <button id="refresh-earnings-btn" class="refresh-btn" onclick="refreshUpcomingEarnings()">
          <i class="fas fa-sync-alt"></i>
          <span>Refresh Data</span>
        </button>
      </div>
      <div class="logo">
        <i class="fas fa-chart-line"></i>
      </div>
      <h1>Banshee Dashboard</h1>
      <p class="subtitle">Monitor earnings calls & market alerts in real-time</p>
    </div>
    
    <div class="nav-tabs">
      <button class="nav-tab active" onclick="switchTab('watchlist')">
        <i class="fas fa-list-ul"></i>
        <span class="tab-text">Watchlist</span>
      </button>
      <button class="nav-tab" onclick="switchTab('upcoming')">
        <i class="fas fa-calendar-alt"></i>
        <span class="tab-text">Upcoming Calls</span>
      </button>
    </div>
    
    <div id="message" class="message"></div>
    
    <!-- Watchlist Tab -->
    <div id="watchlist-tab" class="tab-content active">
      <div class="stats-card">
        <div class="stats">
          <i class="fas fa-chart-bar"></i>
          <span id="ticker-count">Loading...</span>
        </div>
      </div>
      
      <div class="add-form">
        <div class="form-header">
          <i class="fas fa-plus-circle"></i>
          <span>Add New Ticker</span>
        </div>
        <form id="add-form">
          <div class="form-row">
            <div class="input-group">
              <i class="fas fa-search input-icon"></i>
              <input type="text" id="ticker" placeholder="Enter ticker symbol (e.g., AAPL)" required>
            </div>
            <button type="submit">
              <i class="fas fa-plus"></i>
              <span>Add</span>
            </button>
          </div>
        </form>
      </div>
      
      <div id="loading" class="loading">
        <i class="fas fa-spinner"></i>
        <span>Loading watchlist...</span>
      </div>
      <ul id="watchlist" class="watchlist" style="display: none;"></ul>
    </div>
    
    <!-- Upcoming Calls Tab -->
    <div id="upcoming-tab" class="tab-content">
      <div class="stats-card">
        <div class="stats">
          <i class="fas fa-clock"></i>
          <span id="earnings-count">Loading upcoming earnings...</span>
        </div>
      </div>
      
      <div id="earnings-loading" class="loading">
        <i class="fas fa-spinner"></i>
        <span>Loading upcoming calls...</span>
      </div>
      <ul id="earnings-list" class="earnings-list" style="display: none;"></ul>
    </div>
  </div>

  <!-- Modal for countdown timer -->
  <div id="countdown-modal" class="modal">
    <div class="modal-content">
      <div class="modal-header">
        <div class="modal-title">
          <i class="fas fa-stopwatch"></i>
          <span id="modal-ticker"></span>
        </div>
        <span class="close" onclick="closeModal()">
          <i class="fas fa-times"></i>
        </span>
      </div>
      <div class="modal-countdown" id="modal-countdown"></div>
      <div class="earnings-info" id="modal-info"></div>
    </div>
  </div>

  <script>
    const apiKey = '{api_key}';
    let countdownInterval = null;
    let currentEarningsData = null;
    
    function switchTab(tabName) {
      // Update tab buttons
      document.querySelectorAll('.nav-tab').forEach(tab => tab.classList.remove('active'));
      event.target.closest('.nav-tab').classList.add('active');
      
      // Update tab content
      document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
      document.getElementById(tabName + '-tab').classList.add('active');
      
      if (tabName === 'upcoming') {
        // Try to use authenticated endpoint, fall back to public
        if (apiKey) {
          loadUpcomingEarnings();
        } else {
          loadUpcomingEarningsPublic();
        }
      }
    }
    
    function showMessage(text, type = 'success', icon = null) {
      const messageDiv = document.getElementById('message');
      const iconClass = icon || (type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-triangle');
      messageDiv.innerHTML = `<div class="${type}"><i class="${iconClass}"></i><span>${text}</span></div>`;
      setTimeout(() => messageDiv.innerHTML = '', 5000);
    }
    
    function updateStats(count) {
      const statsEl = document.getElementById('ticker-count');
      const plural = count !== 1 ? 's' : '';
      statsEl.textContent = `${count} ticker${plural} being monitored`;
    }
    
    function updateEarningsStats(count) {
      const statsEl = document.getElementById('earnings-count');
      const plural = count !== 1 ? 's' : '';
      statsEl.textContent = `${count} upcoming earnings call${plural}`;
    }
    
    async function loadWatchlist() {
      const loadingEl = document.getElementById('loading');
      const listEl = document.getElementById('watchlist');
      
      try {
        loadingEl.style.display = 'flex';
        listEl.style.display = 'none';
        
        const resp = await fetch('/watchlist', {
          headers: {'X-API-Key': apiKey}
        });
        
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        
        const data = await resp.json();
        const tickers = data.tickers || [];
        
        // Cache the fresh data
        localStorage.setItem('cached_watchlist', JSON.stringify(data));
        
        renderWatchlistData(tickers);
        
        loadingEl.style.display = 'none';
        listEl.style.display = 'block';
        
      } catch (error) {
        console.error('Error loading watchlist:', error);
        showMessage(`Error loading watchlist: ${error.message}`, 'error');
        loadingEl.style.display = 'none';
        listEl.style.display = 'block';
        updateStats(0);
      }
    }
    
    async function loadWatchlistPublic() {
      const loadingEl = document.getElementById('loading');
      const listEl = document.getElementById('watchlist');
      
      // Check for cached data first for instant loading
      const cachedData = localStorage.getItem('cached_watchlist');
      if (cachedData) {
        try {
          const data = JSON.parse(cachedData);
          console.log('Using cached watchlist data:', data.tickers.length, 'tickers');
          renderWatchlistData(data.tickers || []);
        } catch (error) {
          console.error('Error parsing cached watchlist data:', error);
        }
      }
      
      try {
        loadingEl.style.display = 'flex';
        listEl.style.display = 'none';
        
        // Use public endpoint that doesn't require authentication
        const resp = await fetch('/public/watchlist');
        
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        
        const data = await resp.json();
        const tickers = data.tickers || [];
        
        // Cache the fresh data
        localStorage.setItem('cached_watchlist', JSON.stringify(data));
        
        renderWatchlistData(tickers);
        
        loadingEl.style.display = 'none';
        listEl.style.display = 'block';
        
      } catch (error) {
        console.error('Error loading watchlist (public):', error);
        // If we have cached data, don't show error
        if (!cachedData) {
          loadingEl.style.display = 'none';
          listEl.style.display = 'block';
          updateStats(0);
        }
      }
    }
    
    function renderWatchlistData(tickers) {
      const listEl = document.getElementById('watchlist');
      
      listEl.innerHTML = '';
      updateStats(tickers.length);
      
      if (tickers.length === 0) {
        listEl.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">
              <i class="fas fa-chart-line-down"></i>
            </div>
            <p>No tickers in your watchlist yet</p>
            <small>Add some ticker symbols above to get started!</small>
          </div>
        `;
      } else {
        tickers.forEach(ticker => {
          const li = document.createElement('li');
          li.className = 'card';
          li.innerHTML = `
            <div class="ticker-item">
              <div class="ticker-info">
                <div class="ticker-icon">${ticker.substring(0, 2).toUpperCase()}</div>
                <div>
                  <div class="ticker-name">${ticker.toUpperCase()}</div>
                  <small style="color: #6b7280;">Stock Symbol</small>
                </div>
              </div>
              <button class="delete-btn desktop-delete" onclick="deleteTicker('${ticker}')">
                <i class="fas fa-trash"></i>
                <span>Remove</span>
              </button>
              <div class="mobile-delete">
                <button class="delete-btn" onclick="deleteTicker('${ticker}')">
                  <i class="fas fa-trash"></i>
                  <span>Remove from Watchlist</span>
                </button>
              </div>
            </div>
          `;
          listEl.appendChild(li);
        });
      }
    }
    
    async function loadUpcomingEarnings() {
      const loadingEl = document.getElementById('earnings-loading');
      const listEl = document.getElementById('earnings-list');
      
      try {
        loadingEl.style.display = 'flex';
        listEl.style.display = 'none';
        
        const resp = await fetch('/earnings/upcoming', {
          headers: {'X-API-Key': apiKey}
        });
        
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        
        const data = await resp.json();
        const calls = data.calls || [];
        currentEarningsData = calls;
        
        listEl.innerHTML = '';
        updateEarningsStats(calls.length);
        
        if (calls.length === 0) {
          listEl.innerHTML = `
            <div class="empty-state">
              <div class="empty-icon">
                <i class="fas fa-calendar-times"></i>
              </div>
              <p>No upcoming earnings calls found</p>
              <small>Check back later for new earnings announcements</small>
            </div>
          `;
        } else {
          calls.forEach((call, index) => {
            const callTime = new Date(call.call_time);
            // Convert to EST for display
            const estOffset = -5; // EST is UTC-5
            const callTimeEST = new Date(callTime.getTime() + (estOffset * 60 * 60 * 1000));
            const timeString = callTimeEST.toLocaleString('en-US', {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
              timeZone: 'America/New_York'
            }) + ' EST';
            
            const li = document.createElement('li');
            li.className = 'card earnings-item';
            li.innerHTML = `
              <div class="earnings-header" onclick="showCountdown(${index})">
                <div class="earnings-ticker">
                  <div class="ticker-icon">${call.ticker.substring(0, 2).toUpperCase()}</div>
                  <div>
                    <div class="ticker-name">${call.ticker.toUpperCase()}</div>
                    <div class="earnings-time">
                      <i class="fas fa-clock"></i>
                      <span>${timeString}</span>
                    </div>
                  </div>
                </div>
                <div class="countdown" id="countdown-${index}">
                  <i class="fas fa-hourglass-half"></i>
                  <span>Loading...</span>
                </div>
              </div>
              <div class="earnings-details" id="details-${index}">
                <div class="earnings-info">
                  ${call.estimated_eps ? `
                    <div class="info-item">
                      <div class="info-label">
                        <i class="fas fa-chart-bar"></i>
                        Est. EPS
                      </div>
                      <div class="info-value">$${call.estimated_eps}</div>
                    </div>
                  ` : ''}
                  ${call.estimated_revenue ? `
                    <div class="info-item">
                      <div class="info-label">
                        <i class="fas fa-dollar-sign"></i>
                        Est. Revenue
                      </div>
                      <div class="info-value">$${(call.estimated_revenue / 1000000).toFixed(0)}M</div>
                    </div>
                  ` : ''}
                  ${call.actual_eps ? `
                    <div class="info-item">
                      <div class="info-label">
                        <i class="fas fa-chart-line"></i>
                        Actual EPS
                      </div>
                      <div class="info-value">$${call.actual_eps}</div>
                    </div>
                  ` : ''}
                  ${call.actual_revenue ? `
                    <div class="info-item">
                      <div class="info-label">
                        <i class="fas fa-money-bill-wave"></i>
                        Actual Revenue
                      </div>
                      <div class="info-value">$${(call.actual_revenue / 1000000).toFixed(0)}M</div>
                    </div>
                  ` : ''}
                </div>
              </div>
            `;
            listEl.appendChild(li);
          });
          
          // Start countdown timers
          updateCountdowns();
          setInterval(updateCountdowns, 100); // Update every 100ms for millisecond precision
        }
        
        loadingEl.style.display = 'none';
        listEl.style.display = 'block';
        
      } catch (error) {
        console.error('Error loading earnings:', error);
        showMessage(`Error loading earnings: ${error.message}`, 'error');
        loadingEl.style.display = 'none';
        listEl.style.display = 'block';
        updateEarningsStats(0);
      }
    }
    
    async function loadUpcomingEarningsPublic() {
      const loadingEl = document.getElementById('earnings-loading');
      const listEl = document.getElementById('earnings-list');
      
      // Check for cached data first for instant loading
      const cachedData = localStorage.getItem('cached_earnings');
      if (cachedData) {
        try {
          const data = JSON.parse(cachedData);
          console.log('Using cached earnings data:', data.total_count, 'calls');
          renderEarningsData(data.calls || []);
        } catch (error) {
          console.error('Error parsing cached data:', error);
        }
      }
      
      try {
        loadingEl.style.display = 'flex';
        listEl.style.display = 'none';
        
        // Use public endpoint that doesn't require authentication
        const resp = await fetch('/public/earnings/upcoming');
        
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        
        const data = await resp.json();
        const calls = data.calls || [];
        
        // Cache the fresh data
        localStorage.setItem('cached_earnings', JSON.stringify(data));
        
        renderEarningsData(calls);
        
        loadingEl.style.display = 'none';
        listEl.style.display = 'block';
        
      } catch (error) {
        console.error('Error loading earnings (public):', error);
        // If we have cached data, don't show error
        if (!cachedData) {
          loadingEl.style.display = 'none';
          listEl.style.display = 'block';
          updateEarningsStats(0);
        }
      }
    }
    
    function renderEarningsData(calls) {
      const listEl = document.getElementById('earnings-list');
      currentEarningsData = calls;
      
      listEl.innerHTML = '';
      updateEarningsStats(calls.length);
      
      if (calls.length === 0) {
        listEl.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">
              <i class="fas fa-calendar-times"></i>
            </div>
            <p>No upcoming earnings calls found</p>
            <small>Check back later for new earnings announcements</small>
          </div>
        `;
      } else {
        calls.forEach((call, index) => {
          const callTime = new Date(call.call_time);
          // Convert to EST for display
          const estOffset = -5; // EST is UTC-5
          const callTimeEST = new Date(callTime.getTime() + (estOffset * 60 * 60 * 1000));
          const timeString = callTimeEST.toLocaleString('en-US', {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            timeZone: 'America/New_York'
          }) + ' EST';
          
          const li = document.createElement('li');
          li.className = 'card earnings-item';
          li.innerHTML = `
            <div class="earnings-header" onclick="showCountdown(${index})">
              <div class="earnings-ticker">
                <div class="ticker-icon">${call.ticker.substring(0, 2).toUpperCase()}</div>
                <div>
                  <div class="ticker-name">${call.ticker.toUpperCase()}</div>
                  <div class="earnings-time">
                    <i class="fas fa-clock"></i>
                    <span>${timeString}</span>
                  </div>
                </div>
              </div>
              <div class="countdown" id="countdown-${index}">
                <i class="fas fa-hourglass-half"></i>
                <span>Loading...</span>
              </div>
            </div>
            <div class="earnings-details" id="details-${index}">
              <div class="earnings-info">
                ${call.estimated_eps ? `
                  <div class="info-item">
                    <div class="info-label">
                      <i class="fas fa-chart-bar"></i>
                      Est. EPS
                    </div>
                    <div class="info-value">$${call.estimated_eps}</div>
                  </div>
                ` : ''}
                ${call.estimated_revenue ? `
                  <div class="info-item">
                    <div class="info-label">
                      <i class="fas fa-dollar-sign"></i>
                      Est. Revenue
                    </div>
                    <div class="info-value">$${(call.estimated_revenue / 1000000).toFixed(0)}M</div>
                  </div>
                ` : ''}
                ${call.actual_eps ? `
                  <div class="info-item">
                    <div class="info-label">
                      <i class="fas fa-chart-line"></i>
                      Actual EPS
                    </div>
                    <div class="info-value">$${call.actual_eps}</div>
                  </div>
                ` : ''}
                ${call.actual_revenue ? `
                  <div class="info-item">
                    <div class="info-label">
                      <i class="fas fa-money-bill-wave"></i>
                      Actual Revenue
                    </div>
                    <div class="info-value">$${(call.actual_revenue / 1000000).toFixed(0)}M</div>
                  </div>
                ` : ''}
              </div>
            </div>
          `;
          listEl.appendChild(li);
        });
        
        // Start countdown timers
        updateCountdowns();
        setInterval(updateCountdowns, 100); // Update every 100ms for millisecond precision
      }
    }
    
    function updateCountdowns() {
      if (!currentEarningsData) return;
      
      // Get current time in EST
      const now = new Date();
      const estOffset = -5; // EST is UTC-5 (ignoring DST for simplicity)
      const nowEST = new Date(now.getTime() + (estOffset * 60 * 60 * 1000));
      
      currentEarningsData.forEach((call, index) => {
        // Convert call time to EST
        const callTime = new Date(call.call_time);
        const callTimeEST = new Date(callTime.getTime() + (estOffset * 60 * 60 * 1000));
        
        const countdownEl = document.getElementById(`countdown-${index}`);
        if (!countdownEl) return;
        
        const iconEl = countdownEl.querySelector('i');
        const textEl = countdownEl.querySelector('span');
        
        // Check if the call is live or past
        if (callTimeEST <= nowEST) {
          iconEl.className = 'fas fa-broadcast-tower';
          textEl.textContent = 'LIVE NOW';
          countdownEl.className = 'countdown urgent';
          return;
        }
        
        // Calculate time difference
        const diffMs = callTimeEST - nowEST;
        
        // Calculate months, days, hours, minutes, seconds
        const msPerSecond = 1000;
        const msPerMinute = msPerSecond * 60;
        const msPerHour = msPerMinute * 60;
        const msPerDay = msPerHour * 24;
        const msPerMonth = msPerDay * 30.44; // Average days per month
        
        const months = Math.floor(diffMs / msPerMonth);
        const days = Math.floor((diffMs % msPerMonth) / msPerDay);
        const hours = Math.floor((diffMs % msPerDay) / msPerHour);
        const minutes = Math.floor((diffMs % msPerHour) / msPerMinute);
        const seconds = Math.floor((diffMs % msPerMinute) / msPerSecond);
        
        let countdownText = '';
        let className = 'countdown normal';
        let iconClass = 'fas fa-calendar-day';
        
        if (months > 0) {
          if (days > 0) {
            countdownText = `${months}mo ${days}d`;
          } else {
            countdownText = `${months} month${months > 1 ? 's' : ''}`;
          }
          className = 'countdown normal';
          iconClass = 'fas fa-calendar-alt';
        } else if (days > 7) {
          const weeks = Math.floor(days / 7);
          const remainingDays = days % 7;
          if (remainingDays > 0) {
            countdownText = `${weeks}w ${remainingDays}d`;
          } else {
            countdownText = `${weeks} week${weeks > 1 ? 's' : ''}`;
          }
          className = 'countdown normal';
          iconClass = 'fas fa-calendar-week';
        } else if (days > 0) {
          countdownText = `${days}d ${hours}h`;
          className = 'countdown soon';
          iconClass = 'fas fa-calendar-day';
        } else if (hours > 0) {
          countdownText = `${hours}h ${minutes}m`;
          className = 'countdown urgent';
          iconClass = 'fas fa-clock';
        } else {
          countdownText = `${minutes}m ${seconds}s`;
          className = 'countdown urgent';
          iconClass = 'fas fa-stopwatch';
        }
        
        countdownEl.className = className;
        iconEl.className = iconClass;
        textEl.textContent = countdownText;
      });
    }
    
    function showCountdown(index) {
      if (!currentEarningsData || !currentEarningsData[index]) return;
      
      const call = currentEarningsData[index];
      document.getElementById('modal-ticker').textContent = `${call.ticker.toUpperCase()} Earnings Call`;
      
      // Show modal
      document.getElementById('countdown-modal').style.display = 'block';
      
      // Start modal countdown
      if (countdownInterval) clearInterval(countdownInterval);
      countdownInterval = setInterval(() => {
        // Get current time in EST
        const now = new Date();
        const estOffset = -5; // EST is UTC-5 (ignoring DST for simplicity)
        const nowEST = new Date(now.getTime() + (estOffset * 60 * 60 * 1000));
        
        // Convert call time to EST
        const callTime = new Date(call.call_time);
        const callTimeEST = new Date(callTime.getTime() + (estOffset * 60 * 60 * 1000));
        
        const diffMs = callTimeEST - nowEST;
        
        const modalCountdownEl = document.getElementById('modal-countdown');
        
        if (diffMs <= 0) {
          modalCountdownEl.innerHTML = '🚨 EARNINGS CALL IS LIVE! 🚨';
          modalCountdownEl.style.color = '#dc2626';
          return;
        }
        
        // Calculate time components
        const msPerSecond = 1000;
        const msPerMinute = msPerSecond * 60;
        const msPerHour = msPerMinute * 60;
        const msPerDay = msPerHour * 24;
        const msPerMonth = msPerDay * 30.44; // Average days per month
        
        const months = Math.floor(diffMs / msPerMonth);
        const days = Math.floor((diffMs % msPerMonth) / msPerDay);
        const hours = Math.floor((diffMs % msPerDay) / msPerHour);
        const minutes = Math.floor((diffMs % msPerHour) / msPerMinute);
        const seconds = Math.floor((diffMs % msPerMinute) / msPerSecond);
        const milliseconds = diffMs % 1000;
        
        let countdownText = '';
        
        if (months > 0) {
          countdownText = `${months}mo ${days}d ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        } else if (days > 0) {
          countdownText = `${days}d ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
        } else {
          countdownText = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
        }
        
        modalCountdownEl.textContent = countdownText;
        
        // Color coding based on time remaining
        if (diffMs < 60000) { // Less than 1 minute
          modalCountdownEl.style.color = '#dc2626';
        } else if (diffMs < 3600000) { // Less than 1 hour
          modalCountdownEl.style.color = '#d97706';
        } else if (diffMs < 86400000) { // Less than 1 day
          modalCountdownEl.style.color = '#059669';
        } else {
          modalCountdownEl.style.color = '#667eea';
        }
      }, 10); // Update every 10ms for high precision
      
      // Populate modal info
      const modalInfo = document.getElementById('modal-info');
      
      // Convert call time to EST for display
      const callTime = new Date(call.call_time);
      const estOffset = -5; // EST is UTC-5
      const callTimeEST = new Date(callTime.getTime() + (estOffset * 60 * 60 * 1000));
      const callTimeESTString = callTimeEST.toLocaleString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'America/New_York'
      }) + ' EST';
      
      modalInfo.innerHTML = `
        <div class="info-item">
          <div class="info-label">
            <i class="fas fa-calendar-alt"></i>
            Date & Time (EST)
          </div>
          <div class="info-value">${callTimeESTString}</div>
        </div>
        <div class="info-item">
          <div class="info-label">
            <i class="fas fa-info-circle"></i>
            Status
          </div>
          <div class="info-value">${call.status}</div>
        </div>
        ${call.estimated_eps ? `
          <div class="info-item">
            <div class="info-label">
              <i class="fas fa-chart-bar"></i>
              Estimated EPS
            </div>
            <div class="info-value">$${call.estimated_eps}</div>
          </div>
        ` : ''}
        ${call.estimated_revenue ? `
          <div class="info-item">
            <div class="info-label">
              <i class="fas fa-dollar-sign"></i>
              Estimated Revenue
            </div>
            <div class="info-value">$${(call.estimated_revenue / 1000000).toFixed(0)}M</div>
          </div>
        ` : ''}
        ${call.actual_eps ? `
          <div class="info-item">
            <div class="info-label">
              <i class="fas fa-chart-line"></i>
              Actual EPS
            </div>
            <div class="info-value">$${call.actual_eps}</div>
          </div>
        ` : ''}
        ${call.actual_revenue ? `
          <div class="info-item">
            <div class="info-label">
              <i class="fas fa-money-bill-wave"></i>
              Actual Revenue
            </div>
            <div class="info-value">$${(call.actual_revenue / 1000000).toFixed(0)}M</div>
          </div>
        ` : ''}
      `;
    }
    
    function closeModal() {
      document.getElementById('countdown-modal').style.display = 'none';
      if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
      }
    }
    
    // Close modal when clicking outside of it
    window.onclick = function(event) {
      const modal = document.getElementById('countdown-modal');
      if (event.target === modal) {
        closeModal();
      }
    }
    
    async function deleteTicker(ticker) {
      if (!confirm(`Are you sure you want to remove ${ticker.toUpperCase()} from the watchlist?`)) {
        return;
      }
      
      try {
        const resp = await fetch(`/watchlist/${ticker}`, {
          method: 'DELETE',
          headers: {'X-API-Key': apiKey}
        });
        
        if (!resp.ok) {
          const errorData = await resp.json();
          throw new Error(errorData.detail || `HTTP ${resp.status}: ${resp.statusText}`);
        }
        
        const result = await resp.json();
        showMessage(result.message || `${ticker.toUpperCase()} removed from watchlist`, 'success', 'fas fa-check-circle');
        
        // Automatically trigger the full refresh process with UI feedback
        await refreshUpcomingEarnings();
        
      } catch (error) {
        console.error('Error deleting ticker:', error);
        showMessage(`Error removing ticker: ${error.message}`, 'error');
      }
    }
    
    document.getElementById('add-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const tickerInput = document.getElementById('ticker');
      const ticker = tickerInput.value.trim().toUpperCase();
      
      if (!ticker) {
        showMessage('Please enter a ticker symbol', 'error');
        return;
      }
      
      // Basic ticker validation (letters and numbers only, 1-5 characters)
      if (!/^[A-Z0-9]{1,5}$/.test(ticker)) {
        showMessage('Please enter a valid ticker symbol (1-5 letters/numbers)', 'error');
        return;
      }
      
      try {
        const resp = await fetch('/watchlist', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': apiKey
          },
          body: JSON.stringify({ticker, user: 'web'})
        });
        
        if (!resp.ok) {
          const errorData = await resp.json();
          throw new Error(errorData.detail || `HTTP ${resp.status}: ${resp.statusText}`);
        }
        
        showMessage(`${ticker} added to watchlist`, 'success', 'fas fa-plus-circle');
        tickerInput.value = '';
        loadWatchlist();
        
      } catch (error) {
        console.error('Error adding ticker:', error);
        showMessage(`Error adding ticker: ${error.message}`, 'error');
      }
    });
    
    // Load watchlist on page load
    loadWatchlistPublic();
    
    // Load upcoming earnings immediately (public endpoint)
    loadUpcomingEarningsPublic();
    
    // Progress and step management
    let currentStep = 0;
    const totalSteps = 5;
    
    function showProgress() {
      const progressContainer = document.getElementById('progress-container');
      const stepIndicator = document.getElementById('step-indicator');
      
      progressContainer.classList.add('active');
      stepIndicator.classList.add('active');
      
      // Reset all steps
      for (let i = 1; i <= totalSteps; i++) {
        const step = document.getElementById(`step-${i}`);
        step.className = 'step-item pending';
        const icon = step.querySelector('.step-icon');
        icon.textContent = i;
      }
      currentStep = 0;
      updateProgressBar(0);
    }
    
    function hideProgress() {
      const progressContainer = document.getElementById('progress-container');
      const stepIndicator = document.getElementById('step-indicator');
      
      setTimeout(() => {
        progressContainer.classList.remove('active');
        stepIndicator.classList.remove('active');
      }, 500);
    }
    
    function updateProgressBar(percentage) {
      const progressBar = document.getElementById('progress-bar');
      progressBar.style.width = `${percentage}%`;
    }
    
    function setStepActive(stepNumber, text = null) {
      if (currentStep > 0) {
        // Mark previous step as completed
        const prevStep = document.getElementById(`step-${currentStep}`);
        prevStep.className = 'step-item completed';
        const prevIcon = prevStep.querySelector('.step-icon');
        prevIcon.innerHTML = '<i class="fas fa-check"></i>';
      }
      
      currentStep = stepNumber;
      const step = document.getElementById(`step-${stepNumber}`);
      step.className = 'step-item active';
      
      if (text) {
        const stepText = step.querySelector('.step-text');
        stepText.textContent = text;
      }
      
      // Update progress bar smoothly
      const percentage = ((stepNumber - 1) / totalSteps) * 100 + (100 / totalSteps) * 0.5;
      updateProgressBar(percentage);
    }
    
    function completeStep(stepNumber, text = null) {
      const step = document.getElementById(`step-${stepNumber}`);
      step.className = 'step-item completed';
      const icon = step.querySelector('.step-icon');
      icon.innerHTML = '<i class="fas fa-check"></i>';
      
      if (text) {
        const stepText = step.querySelector('.step-text');
        stepText.textContent = text;
      }
      
      // Update progress bar to full for this step
      const percentage = (stepNumber / totalSteps) * 100;
      updateProgressBar(percentage);
    }
    
    async function delay(ms) {
      return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    async function refreshUpcomingEarnings() {
      const refreshBtn = document.getElementById('refresh-earnings-btn');
      const btnIcon = refreshBtn.querySelector('i');
      const btnText = refreshBtn.querySelector('span');
      
      try {
        // Show loading state
        refreshBtn.disabled = true;
        refreshBtn.classList.add('loading');
        btnText.textContent = 'Refreshing...';
        
        // Show progress tracking
        showProgress();
        
        // Step 1: Preparing sync
        setStepActive(1, 'Initializing refresh process...');
        await delay(300);
        
        showMessage('Starting comprehensive data refresh...', 'success', 'fas fa-sync-alt');
        
        // Get current watchlist to show which companies are being processed
        let watchlistTickers = [];
        try {
          const watchlistResp = await fetch(apiKey ? '/watchlist' : '/public/watchlist', {
            headers: apiKey ? {'X-API-Key': apiKey} : {}
          });
          if (watchlistResp.ok) {
            const watchlistData = await watchlistResp.json();
            watchlistTickers = watchlistData.tickers || [];
          }
        } catch (error) {
          console.log('Could not fetch watchlist for display:', error);
        }
        
        // Create company list for display
        const companyList = watchlistTickers.length > 0 
          ? watchlistTickers.slice(0, 3).map(t => t.toUpperCase()).join(', ') + 
            (watchlistTickers.length > 3 ? ` +${watchlistTickers.length - 3} more` : '')
          : 'tracked companies';
        
        // Step 2: Fetching data
        setStepActive(2, `Fetching latest earnings data for ${companyList}...`);
        await delay(200);
        
        // Call the refresh endpoint (requires authentication)
        const resp = await fetch('/tasks/upcoming-sync', {
          method: 'POST',
          headers: {'X-API-Key': apiKey}
        });
        
        await delay(400); // Simulate processing time for smooth UX
        
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        
        completeStep(2, 'Data fetched successfully');
        
        // Step 3: Cleaning stale data
        setStepActive(3, `Cleaning stale data for ${companyList}...`);
        await delay(300);
        
        const result = await resp.json();
        
        completeStep(3, 'Cleanup completed');
        
        // Step 4: Updating storage
        setStepActive(4, 'Updating data storage...');
        await delay(250);
        
        completeStep(4, 'Storage updated');
        
        // Step 5: Refreshing display
        setStepActive(5, 'Refreshing dashboard...');
        await delay(200);
        
        // Reload the earnings data (use authenticated endpoint after refresh)
        loadUpcomingEarnings();
        
        // Also refresh watchlist in case tickers were added/removed
        if (apiKey) {
          loadWatchlist();
        } else {
          loadWatchlistPublic();
        }
        
        await delay(300);
        
        completeStep(5, 'Dashboard refreshed');
        
        // Show the detailed message from the backend
        const message = result.message || 'Data refresh completed successfully!';
        showMessage(message, 'success', 'fas fa-check-circle');
        
        // Complete progress bar
        updateProgressBar(100);
        await delay(500);
        
      } catch (error) {
        console.error('Error refreshing earnings:', error);
        showMessage(`Error refreshing data: ${error.message}`, 'error');
        
        // Mark current step as failed
        if (currentStep > 0) {
          const step = document.getElementById(`step-${currentStep}`);
          step.className = 'step-item pending';
          const icon = step.querySelector('.step-icon');
          icon.innerHTML = '<i class="fas fa-times"></i>';
          icon.style.background = 'linear-gradient(135deg, #ef4444, #dc2626)';
          const stepText = step.querySelector('.step-text');
          stepText.textContent = 'Failed - ' + error.message;
          stepText.style.color = '#ef4444';
        }
      } finally {
        // Restore button state
        refreshBtn.disabled = false;
        refreshBtn.classList.remove('loading');
        btnText.textContent = 'Refresh Data';
        
        // Hide progress after a delay
        setTimeout(hideProgress, 1500);
      }
    }
  </script>
</body>
</html>
"""


@app.get("/web", response_class=HTMLResponse)
def watchlist_page(request: Request):
    """Show the watchlist page or login form."""
    session_id = request.cookies.get("banshee_session")
    if session_id not in authenticated_sessions:
        # Show login form with immediate earnings data loading
        login_with_data = LOGIN_HTML.replace("{error}", "") + """
<script>
// Load upcoming earnings and watchlist data immediately on the login page
async function loadLoginPageData() {
  try {
    // Load earnings data
    const earningsResp = await fetch('/public/earnings/upcoming');
    if (earningsResp.ok) {
      const earningsData = await earningsResp.json();
      console.log('Loaded earnings data on login page:', earningsData.total_count, 'calls');
      if (earningsData.calls && earningsData.calls.length > 0) {
        localStorage.setItem('cached_earnings', JSON.stringify(earningsData));
      }
    }
    
    // Load watchlist data
    const watchlistResp = await fetch('/public/watchlist');
    if (watchlistResp.ok) {
      const watchlistData = await watchlistResp.json();
      console.log('Loaded watchlist data on login page:', watchlistData.tickers.length, 'tickers');
      if (watchlistData.tickers && watchlistData.tickers.length > 0) {
        localStorage.setItem('cached_watchlist', JSON.stringify(watchlistData));
      }
    }
  } catch (error) {
    console.log('Could not preload data:', error);
  }
}

// Load data immediately
loadLoginPageData();
</script>
"""
        return HTMLResponse(content=login_with_data)

    api_key = get_setting("BANSHEE_API_KEY")
    return WATCHLIST_HTML.replace("{api_key}", api_key)
