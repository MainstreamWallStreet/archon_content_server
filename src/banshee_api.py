from __future__ import annotations

import aiohttp
from typing import List

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


@app.get("/")
def root():
    """Redirect root to the web interface."""
    return RedirectResponse(url="/web")


@app.post("/web-login")
def web_login(password: str = Form(...)):
    """Simple password-based login for web interface."""
    expected_password = get_setting("BANSHEE_WEB_PASSWORD")
    if not secrets.compare_digest(password, expected_password):
        return HTMLResponse(content=LOGIN_HTML.replace("{error}", "Invalid password. Please try again."), status_code=401)
    
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
      max-width: 800px;
      margin: 20px auto;
      min-height: calc(100vh - 40px);
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
    .watchlist {
      list-style: none;
    }
    .ticker-item {
      background: white;
      margin-bottom: 10px;
      padding: 15px;
      border-radius: 6px;
      border: 1px solid #e0e6ed;
      display: flex;
      justify-content: space-between;
      align-items: center;
      transition: box-shadow 0.3s;
    }
    .ticker-item:hover {
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .ticker-name {
      font-weight: 600;
      color: #2c3e50;
      font-size: 1.1em;
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
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>📊 Banshee Watchlist</h1>
    <p class="subtitle">Monitor your earnings calls and stock alerts</p>
    
    <div id="message"></div>
    
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

  <script>
    const apiKey = '{api_key}';
    
    function showMessage(text, type = 'success') {
      const messageDiv = document.getElementById('message');
      messageDiv.innerHTML = `<div class="${type}">${text}</div>`;
      setTimeout(() => messageDiv.innerHTML = '', 5000);
    }
    
    function updateStats(count) {
      const statsEl = document.getElementById('ticker-count');
      statsEl.textContent = `${count} ticker${count !== 1 ? 's' : ''} on watchlist`;
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
