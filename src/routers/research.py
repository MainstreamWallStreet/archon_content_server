from __future__ import annotations

"""Router exposing a generic research endpoint that proxies to a LangFlow server.

The external LangFlow flow accepts *input_value* and returns a text response.
The API key is read from the ``LANGFLOW_API_KEY`` environment variable (or
Secret Manager).  If the key is missing the endpoint returns **503 Service
Unavailable** so callers can retry once secrets are configured.
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.config import get_setting

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request / response schemas --------------------------------------------------
# ---------------------------------------------------------------------------
class ResearchRequest(BaseModel):
    """Body schema for `/research`."""

    query: str = Field(..., example="Explain quantum computing in simple terms.")
    flow_id: str = Field(..., example="af41bf0f-6ffb-4591-a276-8ae5f296da51", description="The LangFlow flow ID to execute")


class ResearchResponse(BaseModel):
    """Simple wrapper around the text returned by LangFlow."""

    result: Any  # LangFlow may return arbitrary JSON or plain text


# ---------------------------------------------------------------------------
# Router ---------------------------------------------------------------------
# ---------------------------------------------------------------------------
router = APIRouter(prefix="", tags=["research"])


@router.post(
    "/research",
    summary="Proxy request to a LangFlow research flow.",
    response_model=ResearchResponse,
)
async def research(body: ResearchRequest) -> ResearchResponse:  # noqa: D401
    """Call the external LangFlow flow and return its response verbatim."""

    # 1️⃣  Resolve configuration
    try:
        api_key = get_setting("LANGFLOW_API_KEY")
        base_url = get_setting("LANGFLOW_SERVER_URL")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Construct the full URL
    flow_url = f"{base_url.rstrip('/')}/{body.flow_id}"

    payload = {
        "input_value": body.query,
        "output_type": "text",
        "input_type": "text",
    }
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    # 2️⃣  Perform the request
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(flow_url, json=payload, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log.warning("LangFlow returned non-2xx status %s: %s", exc.response.status_code, exc.response.text)
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:  # noqa: BLE001
        log.exception("Error calling LangFlow: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))

    # 3️⃣  Attempt to parse JSON response, fallback to raw text
    try:
        data: Any = resp.json()
        
        # Extract the final answer from the LangFlow response structure
        if isinstance(data, dict):
            # Navigate through the nested structure to find the actual text response
            outputs = data.get("outputs", [])
            if outputs and len(outputs) > 0:
                first_output = outputs[0]
                output_results = first_output.get("outputs", [])
                if output_results and len(output_results) > 0:
                    first_result = output_results[0]
                    results = first_result.get("results", {})
                    text_result = results.get("text", {})
                    
                    # Try to get the text from the most likely locations
                    final_text = (
                        text_result.get("data", {}).get("text") or  # Primary: data.text (this is where the actual content is)
                        text_result.get("text") or  # Secondary: direct text field
                        text_result.get("message") or  # Alternative: message field
                        str(data)  # Fallback to string representation
                    )
                    
                    if final_text and final_text != str(data):
                        data = final_text
                    else:
                        log.warning("Could not extract text from LangFlow response structure")
                        data = str(data)
                else:
                    log.warning("No output results found in LangFlow response")
                    data = str(data)
            else:
                log.warning("No outputs found in LangFlow response")
                data = str(data)
        else:
            data = str(data)
            
    except ValueError:
        data = resp.text

    return ResearchResponse(result=data) 