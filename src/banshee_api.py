from __future__ import annotations

import aiohttp
from typing import List
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Security, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import secrets

from src.notifications import send_alert

from src.config import get_setting
from src.banshee_watchlist import BansheeStore

API_KEY_HEADER = APIKeyHeader(name="X-API-Key")


def validate_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    expected = get_setting("BANSHEE_API_KEY")
    if api_key != expected:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


store = BansheeStore(get_setting("BANSHEE_DATA_BUCKET"))
app = FastAPI(title="Banshee API", version="1.0")

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
        return HTMLResponse(content=LOGIN_HTML.replace("{error}", "<div class='error'>Invalid password. Please try again.</div>"), status_code=401)
    
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


@app.post("/watchlist")
def create_watchlist(
    payload: TickerPayload, _: str = Depends(validate_key)
) -> dict[str, str]:
    store.add_ticker(payload.ticker, payload.user)
    return {"message": "added"}


@app.delete("/watchlist/{ticker}")
def delete_watchlist(ticker: str, _: str = Depends(validate_key)) -> dict[str, str]:
    store.remove_ticker(ticker)
    return {"message": "removed"}


@app.get("/earnings/upcoming")
async def get_upcoming_earnings(_: str = Depends(validate_key)) -> UpcomingCallsResponse:
    """Get upcoming earnings calls for all watchlist tickers."""
    calls = []
    tickers = store.list_tickers()
    
    for ticker in tickers:
        try:
            # Fetch data with show_upcoming=true to get future earnings
            data = await _fetch_api_ninjas_upcoming(ticker)
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
                        estimated_revenue=item.get("estimated_revenue")
                    )
                    calls.append(call)
        except Exception as e:
            # Skip failed tickers but log the error
            print(f"Error fetching earnings for {ticker}: {e}")
            continue
    
    # Sort by call time
    calls.sort(key=lambda x: x.call_time)
    
    # Filter to only future calls
    now = datetime.now(timezone.utc)
    future_calls = [
        call for call in calls 
        if datetime.fromisoformat(call.call_time.replace('Z', '+00:00')) > now
    ]
    
    next_call = future_calls[0] if future_calls else None
    
    return UpcomingCallsResponse(
        calls=future_calls,
        total_count=len(future_calls),
        next_call=next_call
    )


@app.get("/earnings/{ticker}")
async def get_ticker_earnings(ticker: str, _: str = Depends(validate_key)) -> List[EarningsCall]:
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
                estimated_revenue=item.get("estimated_revenue")
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
    """Fetch upcoming earnings calls from API Ninjas."""
    url = f"https://api.api-ninjas.com/v1/earningscalendar?ticker={ticker}&show_upcoming=true"
    headers = {"X-Api-Key": get_setting("API_NINJAS_KEY")}
    async with aiohttp.ClientSession() as sess:
        async with sess.get(url, headers=headers) as resp:
            if resp.status != 200:
                raise RuntimeError(f"API Ninjas error {resp.status}")
            return await resp.json()


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


LOGIN_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Banshee Login</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .login-container {
      background: white;
      padding: 40px;
      border-radius: 10px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
      width: 100%;
      max-width: 400px;
    }
    h1 {
      text-align: center;
      color: #2c3e50;
      margin-bottom: 30px;
      font-size: 2em;
      font-weight: 300;
    }
    .form-group {
      margin-bottom: 20px;
    }
    label {
      display: block;
      margin-bottom: 8px;
      color: #555;
      font-weight: 500;
    }
    input[type="password"] {
      width: 100%;
      padding: 12px;
      border: 2px solid #e0e6ed;
      border-radius: 6px;
      font-size: 16px;
      transition: border-color 0.3s;
    }
    input[type="password"]:focus {
      outline: none;
      border-color: #667eea;
    }
    button {
      width: 100%;
      background: #667eea;
      color: white;
      border: none;
      padding: 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 16px;
      transition: background 0.3s;
      font-weight: 500;
    }
    button:hover {
      background: #5a67d8;
    }
    .error {
      background: #f8d7da;
      color: #721c24;
      padding: 12px;
      border-radius: 6px;
      margin-bottom: 20px;
      border: 1px solid #f5c6cb;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="login-container">
    <h1>📊 Banshee Access</h1>
    {error}
    <form method="post" action="/web-login">
      <div class="form-group">
        <label for="password">Password</label>
        <input type="password" id="password" name="password" required autofocus>
      </div>
      <button type="submit">Access Watchlist</button>
    </form>
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
  <title>Banshee Watchlist</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    html, body {
      height: 100%;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      line-height: 1.6;
      color: #333;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      background-attachment: fixed;
    }
    .container {
      background: rgba(255, 255, 255, 0.95);
      border-radius: 10px;
      padding: 30px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
      max-width: 1200px;
      margin: 20px auto;
      min-height: calc(100vh - 40px);
    }
    .nav-tabs {
      display: flex;
      border-bottom: 2px solid #e0e6ed;
      margin-bottom: 30px;
    }
    .nav-tab {
      flex: 1;
      text-align: center;
      padding: 15px;
      background: none;
      border: none;
      font-size: 16px;
      font-weight: 500;
      color: #7f8c8d;
      cursor: pointer;
      transition: all 0.3s;
      border-bottom: 3px solid transparent;
    }
    .nav-tab.active {
      color: #667eea;
      border-bottom-color: #667eea;
    }
    .nav-tab:hover {
      background: rgba(102, 126, 234, 0.1);
    }
    .tab-content {
      display: none;
    }
    .tab-content.active {
      display: block;
    }
    h1 {
      color: #2c3e50;
      margin-bottom: 30px;
      text-align: center;
      font-size: 2.5em;
      font-weight: 300;
    }
    .subtitle {
      text-align: center;
      color: #7f8c8d;
      margin-bottom: 40px;
      font-size: 1.1em;
    }
    .add-form {
      background: #f8f9fa;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 30px;
      border-left: 4px solid #667eea;
    }
    .form-row {
      display: flex;
      gap: 10px;
      margin-bottom: 15px;
    }
    input[type="text"] {
      flex: 1;
      padding: 12px;
      border: 2px solid #e0e6ed;
      border-radius: 6px;
      font-size: 16px;
      transition: border-color 0.3s;
    }
    input[type="text"]:focus {
      outline: none;
      border-color: #667eea;
    }
    button {
      background: #667eea;
      color: white;
      border: none;
      padding: 12px 24px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 16px;
      transition: background 0.3s;
      font-weight: 500;
    }
    button:hover {
      background: #5a67d8;
    }
    .delete-btn {
      background: #e74c3c;
      padding: 6px 12px;
      font-size: 14px;
      margin-left: 10px;
    }
    .delete-btn:hover {
      background: #c0392b;
    }
    .watchlist, .earnings-list {
      list-style: none;
    }
    .ticker-item, .earnings-item {
      background: white;
      margin-bottom: 10px;
      padding: 15px;
      border-radius: 6px;
      border: 1px solid #e0e6ed;
      display: flex;
      justify-content: space-between;
      align-items: center;
      transition: box-shadow 0.3s;
      cursor: pointer;
    }
    .ticker-item:hover, .earnings-item:hover {
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .earnings-item {
      cursor: default;
      flex-direction: column;
      align-items: stretch;
    }
    .earnings-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      cursor: pointer;
    }
    .earnings-details {
      display: none;
      padding-top: 10px;
      border-top: 1px solid #e0e6ed;
    }
    .earnings-details.show {
      display: block;
    }
    .ticker-name {
      font-weight: 600;
      color: #2c3e50;
      font-size: 1.1em;
    }
    .earnings-time {
      color: #7f8c8d;
      font-size: 0.9em;
    }
    .countdown {
      font-family: 'Monaco', 'Consolas', monospace;
      font-size: 1.1em;
      font-weight: bold;
      color: #e74c3c;
    }
    .countdown.urgent {
      color: #e74c3c;
      animation: pulse 1s infinite;
    }
    .countdown.soon {
      color: #f39c12;
    }
    .countdown.normal {
      color: #27ae60;
    }
    @keyframes pulse {
      0% { opacity: 1; }
      50% { opacity: 0.7; }
      100% { opacity: 1; }
    }
    .empty-state {
      text-align: center;
      color: #7f8c8d;
      font-style: italic;
      padding: 40px;
      background: #f8f9fa;
      border-radius: 8px;
      border: 2px dashed #e0e6ed;
    }
    .loading {
      text-align: center;
      color: #667eea;
      font-weight: 500;
    }
    .error {
      background: #f8d7da;
      color: #721c24;
      padding: 12px;
      border-radius: 6px;
      margin-bottom: 20px;
      border: 1px solid #f5c6cb;
    }
    .success {
      background: #d4edda;
      color: #155724;
      padding: 12px;
      border-radius: 6px;
      margin-bottom: 20px;
      border: 1px solid #c3e6cb;
    }
    .stats {
      text-align: center;
      margin-bottom: 30px;
      color: #667eea;
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
      background-color: rgba(0,0,0,0.5);
    }
    .modal-content {
      background-color: white;
      margin: 5% auto;
      padding: 30px;
      border-radius: 10px;
      width: 90%;
      max-width: 600px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 15px;
      border-bottom: 1px solid #e0e6ed;
    }
    .close {
      color: #aaa;
      font-size: 28px;
      font-weight: bold;
      cursor: pointer;
      line-height: 1;
    }
    .close:hover {
      color: #667eea;
    }
    .modal-countdown {
      text-align: center;
      font-family: 'Monaco', 'Consolas', monospace;
      font-size: 2em;
      margin: 20px 0;
      padding: 20px;
      background: #f8f9fa;
      border-radius: 8px;
      border: 2px solid #e0e6ed;
    }
    .earnings-info {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 15px;
      margin-top: 20px;
    }
    .info-item {
      padding: 10px;
      background: #f8f9fa;
      border-radius: 6px;
    }
    .info-label {
      font-weight: 600;
      color: #2c3e50;
      font-size: 0.9em;
    }
    .info-value {
      color: #7f8c8d;
      font-size: 1.1em;
    }
    @media (max-width: 600px) {
      .container {
        margin: 10px;
        padding: 20px;
        min-height: calc(100vh - 20px);
      }
      .form-row {
        flex-direction: column;
      }
      h1 {
        font-size: 2em;
      }
      .nav-tab {
        font-size: 14px;
        padding: 12px 8px;
      }
      .earnings-info {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>📊 Banshee Watchlist</h1>
    <p class="subtitle">Monitor your earnings calls and stock alerts</p>
    
    <div class="nav-tabs">
      <button class="nav-tab active" onclick="switchTab('watchlist')">📋 Watchlist</button>
      <button class="nav-tab" onclick="switchTab('upcoming')">📅 Upcoming Calls</button>
    </div>
    
    <div id="message"></div>
    
    <!-- Watchlist Tab -->
    <div id="watchlist-tab" class="tab-content active">
      <div class="stats">
        <span id="ticker-count">Loading...</span>
      </div>
      
      <div class="add-form">
        <h3>Add New Ticker</h3>
        <form id="add-form">
          <div class="form-row">
            <input type="text" id="ticker" placeholder="Enter ticker symbol (e.g., AAPL)" required>
            <button type="submit">Add Ticker</button>
          </div>
        </form>
      </div>
      
      <div id="loading" class="loading">Loading watchlist...</div>
      <ul id="watchlist" class="watchlist" style="display: none;"></ul>
    </div>
    
    <!-- Upcoming Calls Tab -->
    <div id="upcoming-tab" class="tab-content">
      <div class="stats">
        <span id="earnings-count">Loading upcoming earnings...</span>
      </div>
      
      <div id="earnings-loading" class="loading">Loading upcoming calls...</div>
      <ul id="earnings-list" class="earnings-list" style="display: none;"></ul>
    </div>
  </div>

  <!-- Modal for countdown timer -->
  <div id="countdown-modal" class="modal">
    <div class="modal-content">
      <div class="modal-header">
        <h2 id="modal-ticker"></h2>
        <span class="close" onclick="closeModal()">&times;</span>
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
      event.target.classList.add('active');
      
      // Update tab content
      document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
      document.getElementById(tabName + '-tab').classList.add('active');
      
      if (tabName === 'upcoming') {
        loadUpcomingEarnings();
      }
    }
    
    function showMessage(text, type = 'success') {
      const messageDiv = document.getElementById('message');
      messageDiv.innerHTML = `<div class="${type}">${text}</div>`;
      setTimeout(() => messageDiv.innerHTML = '', 5000);
    }
    
    function updateStats(count) {
      const statsEl = document.getElementById('ticker-count');
      statsEl.textContent = `${count} ticker${count !== 1 ? 's' : ''} on watchlist`;
    }
    
    function updateEarningsStats(count) {
      const statsEl = document.getElementById('earnings-count');
      statsEl.textContent = `${count} upcoming earnings call${count !== 1 ? 's' : ''}`;
    }
    
    async function loadWatchlist() {
      const loadingEl = document.getElementById('loading');
      const listEl = document.getElementById('watchlist');
      
      try {
        loadingEl.style.display = 'block';
        listEl.style.display = 'none';
        
        const resp = await fetch('/watchlist', {
          headers: {'X-API-Key': apiKey}
        });
        
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        
        const data = await resp.json();
        const tickers = data.tickers || [];
        
        listEl.innerHTML = '';
        updateStats(tickers.length);
        
        if (tickers.length === 0) {
          listEl.innerHTML = '<div class="empty-state">No tickers in watchlist yet. Add one above!</div>';
        } else {
          tickers.forEach(ticker => {
            const li = document.createElement('li');
            li.className = 'ticker-item';
            li.innerHTML = `
              <span class="ticker-name">${ticker.toUpperCase()}</span>
              <button class="delete-btn" onclick="deleteTicker('${ticker}')">Delete</button>
            `;
            listEl.appendChild(li);
          });
        }
        
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
    
    async function loadUpcomingEarnings() {
      const loadingEl = document.getElementById('earnings-loading');
      const listEl = document.getElementById('earnings-list');
      
      try {
        loadingEl.style.display = 'block';
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
          listEl.innerHTML = '<div class="empty-state">No upcoming earnings calls found.</div>';
        } else {
          calls.forEach((call, index) => {
            const callTime = new Date(call.call_time);
            const timeString = callTime.toLocaleString();
            
            const li = document.createElement('li');
            li.className = 'earnings-item';
            li.innerHTML = `
              <div class="earnings-header" onclick="showCountdown(${index})">
                <div>
                  <span class="ticker-name">${call.ticker.toUpperCase()}</span>
                  <div class="earnings-time">${timeString}</div>
                </div>
                <div class="countdown" id="countdown-${index}"></div>
              </div>
              <div class="earnings-details" id="details-${index}">
                <div class="earnings-info">
                  ${call.estimated_eps ? `<div class="info-item"><div class="info-label">Est. EPS</div><div class="info-value">$${call.estimated_eps}</div></div>` : ''}
                  ${call.estimated_revenue ? `<div class="info-item"><div class="info-label">Est. Revenue</div><div class="info-value">$${(call.estimated_revenue / 1000000).toFixed(0)}M</div></div>` : ''}
                  ${call.actual_eps ? `<div class="info-item"><div class="info-label">Actual EPS</div><div class="info-value">$${call.actual_eps}</div></div>` : ''}
                  ${call.actual_revenue ? `<div class="info-item"><div class="info-label">Actual Revenue</div><div class="info-value">$${(call.actual_revenue / 1000000).toFixed(0)}M</div></div>` : ''}
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
    
    function updateCountdowns() {
      if (!currentEarningsData) return;
      
      const now = new Date();
      
      currentEarningsData.forEach((call, index) => {
        const callTime = new Date(call.call_time);
        const diff = callTime - now;
        
        const countdownEl = document.getElementById(`countdown-${index}`);
        if (!countdownEl) return;
        
        if (diff <= 0) {
          countdownEl.textContent = 'LIVE NOW';
          countdownEl.className = 'countdown urgent';
          return;
        }
        
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);
        const milliseconds = Math.floor((diff % 1000) / 10); // Show centiseconds
        
        let countdownText = '';
        if (days > 0) {
          countdownText = `${days}d ${hours}h ${minutes}m`;
          countdownEl.className = 'countdown normal';
        } else if (hours > 0) {
          countdownText = `${hours}h ${minutes}m ${seconds}s`;
          countdownEl.className = 'countdown soon';
        } else {
          countdownText = `${minutes}m ${seconds}.${milliseconds.toString().padStart(2, '0')}s`;
          countdownEl.className = 'countdown urgent';
        }
        
        countdownEl.textContent = countdownText;
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
        const now = new Date();
        const callTime = new Date(call.call_time);
        const diff = callTime - now;
        
        const modalCountdownEl = document.getElementById('modal-countdown');
        
        if (diff <= 0) {
          modalCountdownEl.textContent = '🚨 EARNINGS CALL IS LIVE! 🚨';
          modalCountdownEl.style.color = '#e74c3c';
          return;
        }
        
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);
        const milliseconds = diff % 1000;
        
        let countdownText = '';
        if (days > 0) {
          countdownText = `${days}d ${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
        } else {
          countdownText = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
        }
        
        modalCountdownEl.textContent = countdownText;
        
        // Color coding
        if (diff < 60000) { // Less than 1 minute
          modalCountdownEl.style.color = '#e74c3c';
        } else if (diff < 3600000) { // Less than 1 hour
          modalCountdownEl.style.color = '#f39c12';
        } else {
          modalCountdownEl.style.color = '#27ae60';
        }
      }, 10); // Update every 10ms for high precision
      
      // Populate modal info
      const modalInfo = document.getElementById('modal-info');
      modalInfo.innerHTML = `
        <div class="info-item">
          <div class="info-label">Date & Time</div>
          <div class="info-value">${new Date(call.call_time).toLocaleString()}</div>
        </div>
        <div class="info-item">
          <div class="info-label">Status</div>
          <div class="info-value">${call.status}</div>
        </div>
        ${call.estimated_eps ? `<div class="info-item"><div class="info-label">Estimated EPS</div><div class="info-value">$${call.estimated_eps}</div></div>` : ''}
        ${call.estimated_revenue ? `<div class="info-item"><div class="info-label">Estimated Revenue</div><div class="info-value">$${(call.estimated_revenue / 1000000).toFixed(0)}M</div></div>` : ''}
        ${call.actual_eps ? `<div class="info-item"><div class="info-label">Actual EPS</div><div class="info-value">$${call.actual_eps}</div></div>` : ''}
        ${call.actual_revenue ? `<div class="info-item"><div class="info-label">Actual Revenue</div><div class="info-value">$${(call.actual_revenue / 1000000).toFixed(0)}M</div></div>` : ''}
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
          throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        }
        
        showMessage(`${ticker.toUpperCase()} removed from watchlist`);
        loadWatchlist();
        
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
        
        showMessage(`${ticker} added to watchlist`);
        tickerInput.value = '';
        loadWatchlist();
        
      } catch (error) {
        console.error('Error adding ticker:', error);
        showMessage(`Error adding ticker: ${error.message}`, 'error');
      }
    });
    
    // Load watchlist on page load
    loadWatchlist();
  </script>
</body>
</html>
"""


@app.get("/web", response_class=HTMLResponse)
def watchlist_page(request: Request):
    """Show the watchlist page or login form."""
    session_id = request.cookies.get("banshee_session")
    if session_id not in authenticated_sessions:
        return HTMLResponse(content=LOGIN_HTML.replace("{error}", ""))
    
    api_key = get_setting("BANSHEE_API_KEY")
    return WATCHLIST_HTML.replace("{api_key}", api_key)
