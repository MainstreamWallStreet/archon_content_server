from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.auth import APIKeyAuth
import json
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import sys
import os

# Try to import LangFlow's loader
try:
    from langflow.load import load_flow_from_json
except ImportError:
    load_flow_from_json = None

router = APIRouter(tags=["research"])


class ResearchRequest(BaseModel):
    query: str = Field(..., example="Why is Citi's ROE depressed in the last two years?")

class ResearchResponse(BaseModel):
    result: str
    metadata: dict = Field(default_factory=dict)


def execute_flow_sync(flow_path: str, query: str, debug_file: str = None):
    """Execute the LangFlow flow synchronously in a thread, with debug output."""
    if load_flow_from_json is None:
        raise RuntimeError("LangFlow is not installed.")
    
    # LangFlow components (e.g., OpenAIEmbeddingsComponent) expect a user id.
    # Provide a default one if the runtime has not set it.
    os.environ.setdefault("LANGFLOW_USER_ID", "api-client")
    
    # Load the flow (returns a Graph or callable depending on LangFlow version)
    flow = load_flow_from_json(flow_path)

    # ------------------------------------------------------------------
    # 🛠  Compatibility shim                                              
    # ------------------------------------------------------------------
    # LangFlow's API has evolved over time.  Older releases expose
    # `Graph.build()` while newer versions may provide `Graph.compile()`
    # or return a callable pipeline directly.  The following logic keeps
    # us working across versions without hard-pinning a dependency.
    if hasattr(flow, "build"):
        compiled_flow = flow.build()
    elif hasattr(flow, "compile"):
        compiled_flow = flow.compile()  # type: ignore[attr-defined]
    elif hasattr(flow, "prepare") and hasattr(flow, "start"):
        # Newer API (v0.5+): Graph.prepare() ➜ Graph.start(...)

        def _run_graph(input_dict: dict[str, str]):
            """Execute a newer-style LangFlow Graph and return its last yielded outputs."""
            # Prepare the graph once (idempotent)
            flow.prepare()

            # Start execution – this returns an async generator wrapped to sync
            gen = flow.start(inputs=[input_dict])  # type: ignore[attr-defined]
            last_payload: dict[str, str] | None = None
            for payload in gen:  # Iterate to completion to capture final outputs
                last_payload = payload

            return last_payload or {}

        compiled_flow = _run_graph
    elif callable(flow):
        compiled_flow = flow  # Already a runnable pipeline
    else:
        raise RuntimeError(
            "Unsupported LangFlow object: expected .build()/.compile()/.prepare()+start() or callable"
        )
    
    # ------------------------------------------------------------------
    # 🗝️  Provide the query using the correct **input field**
    # ------------------------------------------------------------------
    # LangFlow v1.4 switched the default input handle name from "text" to
    # "input_value" (see langflow.schema.schema.INPUT_FIELD_NAME).  Runtime
    # errors like "Vertex text not found" surface when we send the outdated
    # key.  We therefore attempt the modern key first and gracefully fall
    # back to the legacy one for older LangFlow releases to maintain
    # compatibility across versions.

    try:
        from langflow.schema.schema import INPUT_FIELD_NAME  # type: ignore
    except Exception:  # pragma: no cover – very old LangFlow
        INPUT_FIELD_NAME = "input_value"

    # Try the preferred key, then fall back to the legacy "text" key if the
    # graph rejects it.  We re-raise the original exception if both fail so
    # callers receive a clear error message.
    try:
        outputs = compiled_flow({INPUT_FIELD_NAME: query})
    except Exception as first_exc:  # noqa: BLE001 – propagate if fallback fails
        try:
            outputs = compiled_flow({"text": query})
        except Exception:
            raise first_exc
    
    # ------------------------------------------------------------------
    # 🐛  Debug helpers
    # ------------------------------------------------------------------
    # Debug: print and optionally save all outputs
    debug_info = {
        "output_keys": list(outputs.keys()),
        "outputs": {k: str(v)[:500] for k, v in outputs.items()},
    }
    print("[DEBUG] Output keys:", debug_info["output_keys"])
    for k, v in outputs.items():
        print(f"[DEBUG] Output[{k}]:", repr(v)[:500])
    if debug_file:
        with open(debug_file, "w") as f:
            json.dump({"outputs": outputs, "debug_info": debug_info}, f, indent=2, default=str)
    
    # Try to extract the result from a preferred node, fallback to first string/dict
    preferred_keys = ["text_output", "output", "result"]
    result = None
    for key in preferred_keys:
        if key in outputs:
            value = outputs[key]
            if isinstance(value, dict) and "data" in value:
                result = value["data"]
                break
            elif isinstance(value, str):
                result = value
                break
    if not result:
        # fallback: first string or dict with 'data'
        for value in outputs.values():
            if isinstance(value, dict) and "data" in value:
                result = value["data"]
                break
            elif isinstance(value, str):
                result = value
                break
    if not result:
        result = str(outputs)
    return result, debug_info, outputs


@router.post(
    "/execute-research",
    summary="Run the research flow and return the result",
    response_model=ResearchResponse,
)
async def execute_research(
    body: ResearchRequest,
    api_key: APIKeyAuth,
):
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=422, detail="Query is required.")

    # Load the research flow
    flow_path = Path(__file__).parent.parent / "flows" / "Research flow.json"
    if not flow_path.exists():
        raise HTTPException(status_code=500, detail="Research flow definition not found.")

    # Execute the flow in a thread pool to avoid event loop conflicts
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result, debug_info, outputs = await loop.run_in_executor(
                executor, 
                execute_flow_sync, 
                str(flow_path), 
                body.query
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error executing research flow: {exc}")

    return ResearchResponse(result=result, metadata={"flow": "research", "debug": debug_info})


@router.post(
    "/build-context",
    summary="Build context using the research flow",
    response_model=ResearchResponse,
)
async def build_context(
    body: ResearchRequest,
    api_key: APIKeyAuth,
):
    """Build context endpoint that uses the research flow to generate contextual information."""
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=422, detail="Query is required.")

    # Load the research flow
    flow_path = Path(__file__).parent.parent / "flows" / "Research flow.json"
    if not flow_path.exists():
        raise HTTPException(status_code=500, detail="Research flow definition not found.")

    # Execute the flow in a thread pool to avoid event loop conflicts
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result, debug_info, outputs = await loop.run_in_executor(
                executor, 
                execute_flow_sync, 
                str(flow_path), 
                body.query
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error executing research flow: {exc}")

    return ResearchResponse(result=result, metadata={"flow": "build-context", "debug": debug_info})


# CLI for manual testing and debug file output
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test the research flow endpoint via CLI.")
    parser.add_argument("--query", type=str, required=True, help="Query to send to the research flow.")
    parser.add_argument("--debug-file", type=str, default="research_debug_output.json", help="File to save debug output.")
    args = parser.parse_args()
    flow_path = Path(__file__).parent.parent / "flows" / "Research flow.json"
    result, debug_info, outputs = execute_flow_sync(str(flow_path), args.query, args.debug_file)
    print("\n[CLI] Result:\n", result)
    print("\n[CLI] Debug info saved to:", args.debug_file) 