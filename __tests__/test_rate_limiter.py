# __tests__/test_rate_limiter.py
import pytest
import time
from src.llm_reasoner import RateLimiter


@pytest.mark.asyncio
async def test_single_oversize_request_does_not_crash():
    lim = RateLimiter(rpm=1, tpm=100, window=60)
    # tokens > tpm  → should succeed (and log a warning), not raise
    await lim.throttle(150)


@pytest.mark.asyncio
async def test_window_wait_time():
    lim = RateLimiter(rpm=2, tpm=50, window=60)
    t0 = time.perf_counter()
    await lim.throttle(30)  # allowed immediately
    await lim.throttle(30)  # exceeds tpm, should wait ~60s
    elapsed = time.perf_counter() - t0
    assert elapsed >= 59, f"Expected ~60s back-off, got {elapsed:.2f}s"
