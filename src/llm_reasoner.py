#!/usr/bin/env python3
"""
llm_reasoner.py – Raven v5.1
• Robust RateLimiter (no deque index crash)
• Logs oversize single requests for visibility
• Async helpers unchanged
"""

from __future__ import annotations
import json
import time
import re
import os
import asyncio
import collections
import logging
import random
from typing import List, Dict, Any, Deque, Tuple

from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

log = logging.getLogger("llm_reasoner")  # picked up by Cloud Run

# ───────────────────── pricing constants (unchanged) ─────────────────────
PRICE = {
    "nano": {"in": 0.00010, "out": 0.00040},
    "turbo": {"in": 0.00200, "out": 0.00800},
}

JSON_MODE = {"response_format": {"type": "json_object"}}


# ───────────────────── rate-limiter ─────────────────────
class RateLimiter:
    """
    Sliding-window limiter for both request-count and token-count.
    Now resilient when the deque is empty (no IndexError).
    """

    def __init__(self, rpm: int, tpm: int, window: float = 60.0):
        self.rpm, self.tpm, self.window = rpm, tpm, window
        self.req_times: Deque[float] = collections.deque()
        self.tok_hist: Deque[Tuple[float, int]] = collections.deque()
        self.lock = asyncio.Lock()

    async def throttle(self, tokens: int):
        async with self.lock:
            now = time.perf_counter()

            # drop old entries
            while self.req_times and now - self.req_times[0] > self.window:
                self.req_times.popleft()
            while self.tok_hist and now - self.tok_hist[0][0] > self.window:
                self.tok_hist.popleft()

            # compute wait time for RPM
            wait_req = 0
            if len(self.req_times) >= self.rpm:
                wait_req = self.window - (now - self.req_times[0])

            # compute wait for TPM
            used = sum(t for _, t in self.tok_hist)
            wait_tok = 0
            if used + tokens > self.tpm:
                if self.tok_hist:
                    wait_tok = self.window - (now - self.tok_hist[0][0])
                else:
                    # single request larger than TPM; allow but warn
                    log.warning(
                        "Single request (%d tokens) exceeds LLM_MAX_TPM (%d). "
                        "Processing anyway.",
                        tokens,
                        self.tpm,
                    )
                    wait_tok = 0

            wait_for = max(wait_req, wait_tok)
            if wait_for > 0:
                await asyncio.sleep(wait_for)

            # record this request
            self.req_times.append(now)
            self.tok_hist.append((now, tokens))


# ───────────────────── helper fns (unchanged) ─────────────────────
def _rough_tokens(txt: str) -> int:
    return max(1, len(txt) // 4)


def _strip_md_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    return raw


def _ctx_block(chunks: List[str]) -> str:
    return "\n\n".join(chunks) if chunks else "(none)"


def build_prompt(
    template: str, target: str, before: List[str], after: List[str]
) -> str:
    return template.format(
        context=(
            "----- BEFORE -----\n"
            f"{_ctx_block(before)}\n\n"
            "===== TARGET =====\n"
            f"{target}\n\n"
            "----- AFTER ------\n"
            f"{_ctx_block(after)}"
        )
    )


# ───────────────────── prompt strings (unchanged) ─────────────────────
PARA_TEMPLATE = (
    "You are a fundamental-analysis assistant.\n"
    "Below is a **paragraph** from an SEC filing, surrounded by up to five "
    "neighboring chunks before and after it.\n\n"
    "Decide if the TARGET paragraph is useful for fundamental analysis.\n"
    'Reply JSON → {{"relevant":"yes|no","why":"…"}}\n\n'
    "{context}"
)

TABLE_TEMPLATE = (
    "You are a fundamental-analysis assistant.\n"
    "Below is a **table excerpt** from an SEC filing (+context).\n\n"
    "Mark relevant only if it holds financial data.\n"
    'Reply JSON → {{"relevant":"yes|no","why":"…"}}\n\n'
    "{context}"
)

SYS_FORMAT = SystemMessage(
    content=(
        "Convert the following SEC table into structured data and detect units.\n"
        "Return ONLY JSON with keys: title, units, headers, rows.\n"
        'If no data → {"title":"","units":"","headers":[],"rows":[]}'
    )
)


# ───────────────────── Reasoner class (async helpers unchanged) ─────────────────────
class Reasoner:
    def __init__(self):
        self.nano = ChatOpenAI(
            model_name="gpt-4.1-nano",
            temperature=0.0,
            request_timeout=20,
            model_kwargs=JSON_MODE,
        )
        self.turbo = ChatOpenAI(
            model_name="gpt-4.1",
            temperature=0.0,
            request_timeout=40,
            model_kwargs=JSON_MODE,
        )

        self.cost: Dict[str, Dict[str, float]] = {
            k: {"in": 0, "out": 0, "secs": 0} for k in PRICE
        }

        rpm = int(os.getenv("LLM_MAX_RPM", "200"))
        tpm = int(os.getenv("LLM_MAX_TPM", "40000"))
        self.limiter = RateLimiter(rpm, tpm)

    # ------------- internal sync helper -------------
    def _llm_json(self, llm, tag: str, msgs):
        t0 = time.perf_counter()
        rsp = llm.invoke(msgs)
        dt = time.perf_counter() - t0

        usage = rsp.additional_kwargs.get("usage") or {}
        ptok = usage.get("prompt_tokens") or sum(_rough_tokens(m.content) for m in msgs)
        ctok = usage.get("completion_tokens") or _rough_tokens(rsp.content)

        self.cost[tag]["in"] += ptok
        self.cost[tag]["out"] += ctok
        self.cost[tag]["secs"] += dt

        try:
            data = json.loads(_strip_md_json(rsp.content))
        except Exception as e:  # ← robust fallback
            log.warning("Bad JSON from %s: %s", tag, e)
            return {
                "relevant": "error",
                "why": f"invalid JSON ({e})",
                "raw": rsp.content,
            }

        # ensure keys exist
        if "relevant" not in data:
            data["relevant"] = "error"
            data["why"] = data.get("why", "missing 'relevant' key")
        return data

    # ------------- async wrappers -------------
    async def _llm_json_async(
        self, llm, tag: str, msgs, *, max_retries: int = 3
    ) -> Any:
        tokens_est = sum(_rough_tokens(m.content) for m in msgs) + 150
        await self.limiter.throttle(tokens_est)

        last: Exception | None = None
        for attempt in range(max_retries):
            try:
                return await asyncio.to_thread(self._llm_json, llm, tag, msgs)
            except Exception as e:
                last = e
                if attempt < max_retries - 1:
                    delay = min(2**attempt, 60) + random.random()
                    log.warning(
                        "[LLMRetry/%s] Error on attempt %d/%d: %s. Retrying in %.2fs",
                        tag,
                        attempt + 1,
                        max_retries,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
        log.error(
            "[LLMRetry/%s] All %d attempts failed. Last error: %s",
            tag,
            max_retries,
            last,
        )
        raise last  # type: ignore

    # sync (old) interface kept for backward compat
    def para_relevant(self, *a, **kw):  # type: ignore[override]
        prompt = build_prompt(PARA_TEMPLATE, a[0], a[1], a[2])
        return self._llm_json(self.nano, "nano", [HumanMessage(content=prompt)])

    def table_relevant(self, *a, **kw):  # type: ignore[override]
        prompt = build_prompt(TABLE_TEMPLATE, a[0], a[1], a[2])
        return self._llm_json(self.nano, "nano", [HumanMessage(content=prompt)])

    def table_format(self, rows_txt: str):  # type: ignore[override]
        return self._llm_json(
            self.turbo, "turbo", [SYS_FORMAT, HumanMessage(content=rows_txt)]
        )

    # async interface
    async def para_relevant_async(self, target, before, after):
        prompt = build_prompt(PARA_TEMPLATE, target, before, after)
        return await self._llm_json_async(
            self.nano, "nano", [HumanMessage(content=prompt)]
        )

    async def table_relevant_async(self, excerpt, before, after):
        prompt = build_prompt(TABLE_TEMPLATE, excerpt, before, after)
        return await self._llm_json_async(
            self.nano, "nano", [HumanMessage(content=prompt)]
        )

    async def table_format_async(self, rows_txt: str):
        return await self._llm_json_async(
            self.turbo, "turbo", [SYS_FORMAT, HumanMessage(content=rows_txt)]
        )

    # ------------- summary -------------
    def cost_summary(self) -> str:
        out = []
        for tag, pretty in [("nano", "NANO"), ("turbo", "TURBO")]:
            p, c, s = (self.cost[tag][k] for k in ("in", "out", "secs"))
            usd = (p / 1_000) * PRICE[tag]["in"] + (c / 1_000) * PRICE[tag]["out"]
            out.append(f"{pretty}  P:{int(p)} C:{int(c)} T:{s:.1f}s  Cost:${usd:.4f}")
        return "\n".join(out)
