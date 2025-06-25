# new file
import asyncio
from pathlib import Path
import types

import pytest
from httpx import AsyncClient

from src.api import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class DummyFlow(types.SimpleNamespace):
    """A minimal stand-in for a LangFlow Graph/Chain/callable."""

    async def arun(self, *args, **kwargs):  # noqa: D401 – simple stub
        return [{
            "outputs": [{"results": {"message": {"text": "stub"}}}]
        }]

    def __call__(self, *_: object, **__: object):  # fallback for legacy callable path
        return {"result": "stub", "message": "stub"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_hello_world_loads_json(monkeypatch):
    """/hello-world should load *src/flows/hello_world.json* at startup."""

    from src import routers as _routers  # ensure modules are imported
    generate = _routers.generate

    loaded_path: dict[str, str] = {}

    async def fake_aload(path: str):  # type: ignore[arg-type]
        loaded_path["path"] = path
        return DummyFlow()

    # Patch the async loader used when available
    monkeypatch.setattr(generate, "aload_flow_from_json", fake_aload)
    # Force lazy loader to rebuild
    monkeypatch.setattr(generate, "_hello_chain", None)

    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/hello-world", json={"message": "ping"})
    assert resp.status_code == 200, resp.text
    assert loaded_path["path"].endswith(str(Path("src/flows/hello_world.json"))), "Flow JSON not loaded"


@pytest.mark.anyio
async def test_basic_prompt_flow(monkeypatch):
    """/basic-prompt must load *Basic Prompting.json* and execute it."""

    from src.routers import generate as generate

    loaded_path: dict[str, str] = {}

    def fake_sync_load(path: str):  # type: ignore[arg-type]
        loaded_path["path"] = path
        return DummyFlow()

    monkeypatch.setattr(generate, "load_flow_from_json", fake_sync_load)
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/basic-prompt", json={"text": "hello"})
    assert resp.status_code == 200, resp.text
    assert loaded_path["path"].endswith(str(Path("src/flows/Basic Prompting.json"))), "Basic Prompt JSON not loaded" 