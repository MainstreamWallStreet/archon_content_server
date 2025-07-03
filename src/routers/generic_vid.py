from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import asyncio

from src.auth import APIKeyAuth
from src.langflow_runner import run_langflow_json


router = APIRouter(tags=["generic-vid"])


class GenericVIDRequest(BaseModel):
    """Request model for the Generic VID Response endpoint."""

    query: str = Field(
        ..., example="Explain how net interest margin differs between regional banks"
    )


class GenericVIDResponse(BaseModel):
    """Response model returned by the Generic VID Response endpoint."""

    result: str
    metadata: dict = Field(default_factory=dict)


@router.post(
    "/execute-generic-vid",
    summary="Run the Generic VID Response flow and return the result",
    response_model=GenericVIDResponse,
)
async def execute_generic_vid(
    body: GenericVIDRequest,
    api_key: APIKeyAuth,
):
    """Endpoint that executes the *Generic VID Response* LangFlow pipeline.

    The implementation mirrors the logic used by the research flow endpoint so we
    maintain consistent behaviour and error handling across the API surface.
    """
    if not body.query or not body.query.strip():
        raise HTTPException(status_code=422, detail="Query is required.")

    # Locate the flow definition that ships with the repository
    flow_path = Path(__file__).parent.parent / "flows" / "Generic VID Response.json"
    if not flow_path.exists():
        raise HTTPException(
            status_code=500, detail="Generic VID Response flow definition not found."
        )

    # Execute the LangFlow graph in a thread pool to keep the event-loop free
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result, debug_info, _ = await loop.run_in_executor(
                executor, run_langflow_json, str(flow_path), body.query
            )
    except Exception as exc:  # pragma: no cover – surfaced via HTTPException
        raise HTTPException(
            status_code=500, detail=f"Error executing Generic VID Response flow: {exc}"
        ) from exc

    return GenericVIDResponse(
        result=result, metadata={"flow": "generic_vid_response", "debug": debug_info}
    )
