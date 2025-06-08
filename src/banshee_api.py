from __future__ import annotations

import aiohttp
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

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


class TickerPayload(BaseModel):
    ticker: str
    user: str


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
