# __tests__/test_llm_parallel.py
import pytest
import asyncio
from src.llm_reasoner import Reasoner


@pytest.mark.asyncio
async def test_parallel_workers(monkeypatch):
    R = Reasoner()
    workers = 4

    started = 0

    async def fake_para(*a, **kw):
        nonlocal started
        started += 1
        await asyncio.sleep(0.1)  # simulate network
        return {"relevant": "no", "why": "test"}

    # patch async helpers
    monkeypatch.setattr(R, "para_relevant_async", fake_para)
    monkeypatch.setattr(R, "table_relevant_async", fake_para)

    # build dummy chunk list (8 <p> tags)
    import bs4

    chunks = [bs4.BeautifulSoup("<p>foo</p>", "html.parser").p for _ in range(8)]

    async def run():
        from src.edgar_cli import _analyse_chunks

        await _analyse_chunks(
            chunks,
            R,
            workers,
            docs_service=None,  # Mock services for test
            drive_service=None,
            doc_id="test_doc",
            title="Test Document",
            fa_tables=[],
        )

    t0 = asyncio.get_event_loop().time()
    await run()
    elapsed = asyncio.get_event_loop().time() - t0

    # with 4 workers and sleep(0.1), 8 tasks should take ~0.2s not 0.8s
    assert elapsed < 0.4, f"workers not parallel, took {elapsed:.2f}s"
    assert started == 8
