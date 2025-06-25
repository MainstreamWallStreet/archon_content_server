"""Endpoints that proxy to LangFlow programmatic flows."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
from functools import lru_cache
from pathlib import Path
import asyncio
from typing import Any
from uuid import uuid4

# LangFlow keeps moving the helper in different places across versions. Try the modern
# locations first and gracefully fall back for older releases.
try:
    # LangFlow ≥ 1.4.3 – re-exported at the package root.
    from langflow import load_flow_from_json  # type: ignore
except ImportError:  # pragma: no cover – continue probing
    try:
        # LangFlow ≥ 1.4.0 (sometimes) exposes it from the ``langflow.load`` sub-module.
        from langflow.load import load_flow_from_json  # type: ignore
    except ImportError:
        try:
            # Historic (<1.4) location.
            from langflow.processing.load import load_flow_from_json  # type: ignore
        except ImportError:
            # Very old (<1.1) releases.
            from langflow.base.processing.load import load_flow_from_json  # type: ignore

# Async loader (available in newer LangFlow)
try:
    from langflow.load import aload_flow_from_json  # type: ignore
except Exception:  # pragma: no cover
    aload_flow_from_json = None  # type: ignore

# Graph type for runtime isinstance checks (optional import)
try:
    from langflow.graph.graph.base import Graph  # type: ignore
except Exception:  # pragma: no cover
    Graph = None  # type: ignore

router = APIRouter()

# Path to exported flow JSON (adjust if stored elsewhere)
FLOW_DIR = Path(__file__).resolve().parent.parent / "flows"
HELLO_FLOW_FILE = FLOW_DIR / "hello_world.json"
BASIC_PROMPT_FLOW_FILE = FLOW_DIR / "Basic Prompting.json"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _echo_chain(inputs: dict):  # type: ignore[return-type]
    """Very simple replacement when no flow JSON is present."""

    value = inputs.get("input_value", "Hello world!")
    return {"result": value, "message": value}

# We defer loading to runtime so we can use the *async* loader when available
_hello_chain = None  # type: ignore
_hello_lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class HelloRequest(BaseModel):
    message: str = "Hello world!"

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/hello-world", tags=["generation"])
async def hello_world(body: HelloRequest):
    """Invoke the *hello_world* flow (async-safe).

    If the JSON file is missing we fall back to a tiny echo chain so the
    endpoint still works during local development.
    """

    global _hello_chain

    # Lazy-initialise the chain in a thread-safe manner.
    if _hello_chain is None:
        async with _hello_lock:
            if _hello_chain is None:  # double-check after acquiring lock
                if HELLO_FLOW_FILE.exists():
                    if aload_flow_from_json is not None:
                        _hello_chain = await aload_flow_from_json(str(HELLO_FLOW_FILE))
                    else:
                        # Older LangFlow – use synchronous loader (safe here
                        # because we are inside the first request and can
                        # afford a blocking call).
                        _hello_chain = load_flow_from_json(str(HELLO_FLOW_FILE))
                else:
                    _hello_chain = _echo_chain

    inputs = {"text": body.message, "input_value": body.message}

    result = None
    # Short-circuit if it's a LangFlow Graph (needs special signature)
    if Graph is not None and isinstance(_hello_chain, Graph):  # type: ignore[arg-type]
        _hello_chain.user_id = "system"  # simple identifier to satisfy LangFlow
        try:
            graph_out = await _hello_chain.arun([inputs], fallback_to_env_vars=True)  # type: ignore[arg-type]
            result = graph_out[0] if isinstance(graph_out, list) else graph_out
        except Exception:
            # Log and fall back to echo
            result = _echo_chain(inputs)
    # 1️⃣ plain callable (legacy loader)
    elif callable(_hello_chain):
        result = _hello_chain(inputs)
    else:
        # 2️⃣ async-first API (Chain objects)
        #    Some wrappers need `.build()` before .invoke/.ainvoke appear.
        if hasattr(_hello_chain, "build"):
            maybe_coroutine = _hello_chain.build()  # type: ignore[attr-defined]
            if asyncio.iscoroutine(maybe_coroutine):
                await maybe_coroutine

            if hasattr(_hello_chain, "root"):
                _hello_chain = _hello_chain.root  # type: ignore[attr-defined]

        if hasattr(_hello_chain, "ainvoke"):
            result = await _hello_chain.ainvoke(inputs)  # type: ignore[attr-defined]
        elif hasattr(_hello_chain, "invoke"):
            result = _hello_chain.invoke(inputs)  # type: ignore[attr-defined]
        elif hasattr(_hello_chain, "arun"):
            result = await _hello_chain.arun([inputs])  # type: ignore[attr-defined]
        elif hasattr(_hello_chain, "run"):
            result = _hello_chain.run(inputs)  # type: ignore[attr-defined]

    if result is None:
        raise TypeError("Unsupported flow object: cannot execute – missing invoke/ainvoke")

    return result

_basic_prompt_chain = None  # type: ignore
_basic_lock = asyncio.Lock()

async def _get_basic_prompt_chain():
    global _basic_prompt_chain

    if _basic_prompt_chain is not None:
        return _basic_prompt_chain

    async with _basic_lock:
        if _basic_prompt_chain is None:
            if not BASIC_PROMPT_FLOW_FILE.exists():
                raise FileNotFoundError(f"Expected flow file {BASIC_PROMPT_FLOW_FILE} not found.")

            if aload_flow_from_json is not None:
                _basic_prompt_chain = await aload_flow_from_json(str(BASIC_PROMPT_FLOW_FILE))
            else:
                _basic_prompt_chain = load_flow_from_json(str(BASIC_PROMPT_FLOW_FILE))

        return _basic_prompt_chain

class GenerateRequest(BaseModel):
    prompt: str
    video_url: str | None = None


@router.post("/generate-vid-informed-response", tags=["generation"])
async def generate_vid_informed_response(body: GenerateRequest):
    """Call the LangFlow endpoint named ``generate_vid_informed_response``.

    The entire request body is forwarded to LangFlow as ``input_value`` so you
    can access the dict inside your flow.
    """

    payload = {
        "input_value": body.model_dump(),
    }
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        resp = await client.post(
            "/langflow/api/v1/run/generate_vid_informed_response?stream=false",
            json=payload,
            timeout=120,
        )
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.text)
    return resp.json()

class BasicPromptRequest(BaseModel):
    text: str


@router.post("/basic-prompt", tags=["generation"])
async def basic_prompt(body: BasicPromptRequest):
    """Run the *Basic Prompting* flow exported from LangFlow.

    The flow file must be located at ``src/flows/Basic Prompting.json`` and must *not*
    contain the raw API key.  Ensure you set your OpenAI key using the environment
    variable ``OPENAI_API_KEY`` – the component in the flow uses that at runtime.
    """
    chain = await _get_basic_prompt_chain()
    inputs = {"text": body.text, "input_value": body.text}

    # Graph first
    if Graph is not None and isinstance(chain, Graph):  # type: ignore[arg-type]
        chain.user_id = "system"
        try:
            graph_out = await chain.arun([inputs], fallback_to_env_vars=True)  # type: ignore[arg-type]
            result = graph_out[0] if isinstance(graph_out, list) else graph_out
        except Exception:
            result = {
                "result": "Error: Unable to execute flow",
                "message": "An error occurred while executing the flow. Please check the logs for more details."
            }
    # 1️⃣ plain callable
    elif callable(chain):
        result = chain(inputs)
    else:
        # 2️⃣ Chain with invoke methods
        if hasattr(chain, "build"):
            maybe_coro = chain.build()  # type: ignore[attr-defined]
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro

            if hasattr(chain, "root"):
                chain = chain.root  # type: ignore[attr-defined]

        if hasattr(chain, "ainvoke"):
            result = await chain.ainvoke(inputs)  # type: ignore[attr-defined]
        elif hasattr(chain, "invoke"):
            result = chain.invoke(inputs)  # type: ignore[attr-defined]
        elif hasattr(chain, "arun"):
            result = await chain.arun([inputs])  # type: ignore[attr-defined]
        elif hasattr(chain, "run"):
            result = chain.run(inputs)  # type: ignore[attr-defined]

    return result 