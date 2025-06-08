import asyncio
import random
import pytest

from src.llm_reasoner import Reasoner


@pytest.mark.asyncio
async def test_llm_json_async_retries(monkeypatch):
    R = Reasoner()

    async def no_wait(_):
        pass

    monkeypatch.setattr(R.limiter, "throttle", no_wait)
    monkeypatch.setattr(random, "random", lambda: 0)

    sleeps = []

    async def fake_sleep(d):
        sleeps.append(d)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    attempts = {"n": 0}

    def flaky(_llm, _tag, _msgs):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("fail")
        return {"relevant": "no", "why": "ok"}

    monkeypatch.setattr(R, "_llm_json", flaky)

    out = await R.para_relevant_async("x", [], [])

    assert out["relevant"] == "no"
    assert attempts["n"] == 3
    assert sleeps[:2] == [1, 2]
