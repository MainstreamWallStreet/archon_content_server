"""
Archon Content Server - FastAPI Application

Core Functionality:
1. LangFlow Integration - Execute research flows via external LangFlow server
2. Spreadsheet Building - Generate Excel workbooks from natural language descriptions

Environment Variables Required:
- ARCHON_API_KEY: Authentication key for the API
- LANGFLOW_SERVER_URL: Base URL for LangFlow server (e.g., http://0.0.0.0:7860/api/v1/run/)
- LANGFLOW_API_KEY: API key for LangFlow server authentication
- OPENAI_API_KEY: OpenAI API key for LLM plan generation (optional)
"""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

import httpx
import logging
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.config import get_setting
from src.spreadsheet_builder import PlanGenerator, build_from_plan

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Archon Content Server",
    version="1.0.0",
    description="API for LangFlow research integration and spreadsheet generation. All endpoints require authentication via X-API-Key header.",
)

# ============================================================================
# AUTHENTICATION
# ============================================================================


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """
    Verify the API key from the request header.

    Args:
        x_api_key: The API key from the X-API-Key header

    Returns:
        str: The verified API key

    Raises:
        HTTPException: 401 if API key is missing or invalid
    """
    try:
        expected_api_key = get_setting("ARCHON_API_KEY")
    except RuntimeError:
        raise HTTPException(status_code=503, detail="ARCHON_API_KEY not configured")

    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header is required")

    if x_api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return x_api_key


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="Application version")


class ResearchRequest(BaseModel):
    """Request model for research endpoint."""

    query: str = Field(..., example="Explain quantum computing in simple terms.")
    flow_id: str = Field(
        ...,
        example="af41bf0f-6ffb-4591-a276-8ae5f296da51",
        description="The LangFlow flow ID to execute",
    )


class ResearchResponse(BaseModel):
    """Response model for research endpoint."""

    result: Any = Field(..., description="The extracted text response from LangFlow")


class SpreadsheetRequest(BaseModel):
    """Request model for spreadsheet generation."""

    objective: str = Field(..., example="Model FY-2024 revenue break-even")
    data: str | None = Field(
        None,
        example="Revenue: 763.9M, Participants: 7020",
        description="Plaintext data or '@/abs/path.txt' to read from file.",
    )


class VidReasonerRequest(BaseModel):
    """Request model for video reasoning endpoint."""

    input_value: str = Field(
        ...,
        example="hello world!",
        description="The input value to be processed by the video reasoning flow",
    )
    output_type: str = Field(
        default="text",
        example="text",
        description="Specifies the expected output format",
    )
    input_type: str = Field(
        default="text", example="text", description="Specifies the input format"
    )

    chat_history: list[dict[str, str]] | None = Field(
        default=None,
        description='Optional chat history to provide conversational context. Each list item should contain a role ("user" or "assistant") and the corresponding content.',
        example=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help you today?"},
        ],
    )

    # Add optional stream flag
    stream: bool = Field(
        default=False,
        description="If true, the response will be streamed back to the client in real-time chunks.",
        example=True,
    )


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error details")


# ============================================================================
# CORE ENDPOINTS
# ============================================================================


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the service is running and healthy.",
)
def health_check():
    """
    Health check endpoint.

    Returns:
        HealthResponse: Service status and timestamp
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
    )


@app.post(
    "/research",
    response_model=ResearchResponse,
    summary="Execute LangFlow Research Flow",
    description="""
    Execute a research flow on the external LangFlow server.
    
    This endpoint:
    1. Takes a query and flow ID
    2. Sends the request to the configured LangFlow server
    3. Extracts the final answer text from the complex response structure
    4. Returns just the clean text response
    
    Environment Variables Required:
    - LANGFLOW_SERVER_URL: Base URL for LangFlow server
    - LANGFLOW_API_KEY: API key for LangFlow authentication
    
    Example:
    ```json
    {
        "query": "How should we think about risk?",
        "flow_id": "af41bf0f-6ffb-4591-a276-8ae5f296da51"
    }
    ```
    """,
)
async def research(
    body: ResearchRequest, api_key: str = Depends(verify_api_key)
) -> ResearchResponse:
    """
    Execute a LangFlow research flow and return the extracted answer.

    Args:
        body: ResearchRequest containing query and flow_id

    Returns:
        ResearchResponse: The extracted text response from LangFlow

    Raises:
        HTTPException: 503 if configuration is missing, 500 for server errors
    """
    # 1️⃣ Resolve configuration
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

    # 2️⃣ Perform the request
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(flow_url, json=payload, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(f"❌ HTTP error: {exc.response.status_code} - {exc.response.text}")
        raise HTTPException(
            status_code=exc.response.status_code, detail=exc.response.text
        )
    except Exception as exc:
        logger.error(f"❌ Request error: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))

    # 3️⃣ Extract the final answer from the LangFlow response structure
    try:
        data: Any = resp.json()

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
                        text_result.get("data", {}).get("text")  # Primary: data.text
                        or text_result.get("text")  # Secondary: direct text field
                        or text_result.get("message")  # Alternative: message field
                        or str(data)  # Fallback to string representation
                    )

                    if final_text and final_text != str(data):
                        data = final_text
                    else:
                        data = str(data)
                else:
                    data = str(data)
            else:
                data = str(data)
        else:
            data = str(data)

    except ValueError:
        data = resp.text

    return ResearchResponse(result=data)


@app.post(
    "/vid-reasoner",
    response_model=ResearchResponse,
    summary="Execute Video Reasoning Flow",
    description="""
    Execute a video reasoning flow on the external LangFlow server.
    
    This endpoint:
    1. Takes an input value and optional output/input type specifications
    2. Sends the request to the configured LangFlow server using a specific flow ID
    3. Extracts the final answer text from the complex response structure
    4. Returns just the clean text response
    
    Environment Variables Required:
    - LANGFLOW_SERVER_URL: Base URL for LangFlow server
    - LANGFLOW_API_KEY: API key for LangFlow authentication
    
    Example:
    ```json
    {
        "input_value": "hello world!",
        "output_type": "text",
        "input_type": "text"
    }
    ```
    """,
    responses={
        200: {
            "model": ResearchResponse,
            "description": "Successful JSON response when stream=false",
        },
        206: {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "string",
                        "description": "Streamed JSON chunks when stream=true",
                    }
                }
            },
            "description": "Streaming response (partial content) when stream=true",
        },
    },
)
async def vid_reasoner(
    body: VidReasonerRequest, api_key: str = Depends(verify_api_key)
) -> ResearchResponse | StreamingResponse:
    """
    Execute a LangFlow video reasoning flow and return the extracted answer.

    Args:
        body: VidReasonerRequest containing input_value and optional type specifications

    Returns:
        ResearchResponse | StreamingResponse: The extracted text response from LangFlow or a streaming response

    Raises:
        HTTPException: 503 if configuration is missing, 500 for server errors
    """
    # 1️⃣ Resolve configuration
    try:
        langflow_api_key = get_setting("LANGFLOW_API_KEY")
        base_url = get_setting("LANGFLOW_SERVER_URL")
    except RuntimeError as exc:
        logger.error(f"❌ Configuration error: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))

    # Use the specific flow ID for video reasoning
    flow_id = "59ef78ef-195b-4534-9b38-21527c2c90d4"
    flow_url = f"{base_url.rstrip('/')}/{flow_id}"

    payload = {
        "input_value": body.input_value,
        "output_type": body.output_type,
        "input_type": body.input_type,
    }
    if body.chat_history:
        payload["chat_history"] = body.chat_history
    headers = {
        "x-api-key": langflow_api_key,
        "Content-Type": "application/json",
    }

    # If streaming requested, return StreamingResponse directly
    if body.stream:
        logger.info("🚀 Streaming response from LangFlow...")

        async def stream_langflow():
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream(
                        "POST", flow_url, json=payload, headers=headers
                    ) as resp:
                        resp.raise_for_status()
                        async for chunk in resp.aiter_bytes():
                            yield chunk
            except httpx.HTTPStatusError as exc:
                logger.error(
                    f"❌ HTTP error while streaming: {exc.response.status_code} - {exc.response.text}"
                )
                # Propagate the error details to the client in the stream
                yield exc.response.text.encode()
            except Exception as exc:
                logger.error(f"❌ Streaming request error: {exc}")
                yield str(exc).encode()

        # Import here to avoid circular import at top
        from fastapi.responses import StreamingResponse

        return StreamingResponse(stream_langflow(), media_type="application/json")

    # ==============================
    # Non-streaming logic (existing)
    # ==============================

    # 2️⃣ Perform the request
    logger.info("🚀 Making request to LangFlow...")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(flow_url, json=payload, headers=headers)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(f"❌ HTTP error: {exc.response.status_code} - {exc.response.text}")
        raise HTTPException(
            status_code=exc.response.status_code, detail=exc.response.text
        )
    except Exception as exc:
        logger.error(f"❌ Request error: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))

    # 3️⃣ Extract the final answer from the LangFlow response structure
    try:
        data: Any = resp.json()

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
                        text_result.get("data", {}).get("text")  # Primary: data.text
                        or text_result.get("text")  # Secondary: direct text field
                        or text_result.get("message")  # Alternative: message field
                        or str(data)  # Fallback to string representation
                    )

                    if final_text and final_text != str(data):
                        data = final_text
                    else:
                        data = str(data)
                else:
                    data = str(data)
            else:
                data = str(data)
        else:
            data = str(data)

    except ValueError:
        data = resp.text

    return ResearchResponse(result=data)


@app.post(
    "/spreadsheet/build",
    summary="Generate Excel Workbook from Natural Language",
    description="""
    Generate an Excel workbook from a natural language description.
    
    This endpoint:
    1. Takes an objective (what to model) and optional data
    2. Uses OpenAI to generate a structured build plan
    3. Creates an Excel workbook with formulas and formatting
    4. Returns the .xlsx file as a download
    
    Environment Variables Required:
    - OPENAI_API_KEY: OpenAI API key for LLM plan generation
    
    Example:
    ```json
    {
        "objective": "Model FY-2024 revenue break-even analysis",
        "data": "Revenue: 763.9M, Fixed Costs: 45M, Variable Cost %: 12%"
    }
    ```
    """,
    response_class=FileResponse,
)
async def generate_spreadsheet(
    body: SpreadsheetRequest, api_key: str = Depends(verify_api_key)
):
    """
    Generate an Excel workbook from natural language description.

    Args:
        body: SpreadsheetRequest containing objective and optional data

    Returns:
        FileResponse: The generated .xlsx file

    Raises:
        HTTPException: 503 if OpenAI API key is missing, 500 for generation errors
    """
    # 1️⃣ Obtain plan from LLM
    generator = PlanGenerator()
    try:
        plan = generator.generate(body.objective, body.data or "")
    except RuntimeError as exc:  # Missing API key etc.
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generating plan: {exc}")

    # 2️⃣ Build workbook in temp dir
    tmp_dir = Path(mkdtemp(prefix="sbuilder_"))
    try:
        output_path = build_from_plan(plan, output_dir=tmp_dir)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error building spreadsheet: {exc}"
        )

    # 3️⃣ Stream file back
    return FileResponse(
        path=output_path,
        filename=output_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post(
    "/spreadsheet/plan",
    summary="Generate Build Plan Only",
    description="""
    Generate just the build plan JSON without creating the Excel file.
    
    This is useful for:
    - Previewing what the LLM will generate
    - Debugging plan generation issues
    - Understanding the spreadsheet structure before building
    
    Environment Variables Required:
    - OPENAI_API_KEY: OpenAI API key for LLM plan generation
    """,
    response_model=dict,
)
async def generate_plan(
    body: SpreadsheetRequest, api_key: str = Depends(verify_api_key)
):
    """
    Generate a build plan from natural language without creating the Excel file.

    Args:
        body: SpreadsheetRequest containing objective and optional data

    Returns:
        dict: The generated build plan JSON

    Raises:
        HTTPException: 503 if OpenAI API key is missing, 500 for generation errors
    """
    generator = PlanGenerator()
    try:
        plan = generator.generate(body.objective, body.data or "")
        return plan
    except RuntimeError as exc:  # Missing API key etc.
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error generating plan: {exc}")
