from unittest.mock import MagicMock, patch

import pytest

from src.banshee_api import sync_watchlist


@pytest.mark.asyncio
async def test_sync_watchlist_calls_api_and_schedules():
    mock_store = MagicMock()
    mock_store.list_tickers.return_value = ["AAPL"]
    with patch(
        "src.banshee_api._fetch_api_ninjas",
        return_value=[{"earnings_date": "2025-07-30T14:00:00Z"}],
    ) as fetch:
        await sync_watchlist(mock_store)
        fetch.assert_called_with("AAPL")
        mock_store.schedule_call.assert_called()
        mock_store.record_api_call.assert_called()
