# __tests__/test_llm_bad_json.py
"""
Regression: a malformed LLM response must *not* crash _llm_json
or the edgar_cli async pipeline.
"""

import asyncio
import types
import bs4
import os

os.environ.setdefault("OPENAI_API_KEY", "dummy")

from src.llm_reasoner import Reasoner
from src.edgar_cli import _analyse_chunks


def test_llm_json_fallback():
    """_llm_json returns {'relevant': 'error', …} when JSON is bogus."""
    R = Reasoner()

    class DummyResp:  # fake OpenAI response
        def __init__(self):
            self.content = "oops"  # not JSON
            self.additional_kwargs = {"usage": {}}

    llm_stub = types.SimpleNamespace(invoke=lambda *_: DummyResp())
    out = R._llm_json(llm_stub, "nano", [types.SimpleNamespace(content="hi")])

    assert out["relevant"] == "error"


def test_analyse_chunks_handles_missing_key(monkeypatch):
    """_analyse_chunks must complete even when 'relevant' key is absent."""
    R = Reasoner()

    async def bad_para(*_a, **_k):
        return {"why": "missing key"}  # no 'relevant'

    async def bad_table(*_a, **_k):
        return {"why": "missing key"}  # same

    monkeypatch.setattr(R, "para_relevant_async", bad_para)
    monkeypatch.setattr(R, "table_relevant_async", bad_table)

    # two dummy <p> chunks
    chunks = [bs4.BeautifulSoup("<p>x</p>", "html.parser").p for _ in range(2)]

    async def run():
        await _analyse_chunks(
            chunks,
            R,
            workers=2,
            docs_service=None,
            drive_service=None,
            doc_id="dummy",
            title="dummy",
            fa_tables=[],
        )

    # should finish without raising
    asyncio.run(run())
