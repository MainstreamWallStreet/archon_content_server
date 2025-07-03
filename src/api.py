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
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.config import get_setting
from src.spreadsheet_builder import PlanGenerator, build_from_plan

app = FastAPI(
    title="Archon Content Server",
    version="1.0.0",
    description="API for LangFlow research integration and spreadsheet generation"
)

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
    flow_id: str = Field(..., example="af41bf0f-6ffb-4591-a276-8ae5f296da51", description="The LangFlow flow ID to execute")


class ResearchResponse(BaseModel):
    """Response model for research endpoint."""
    result: Any = Field(..., description="The extracted text response from LangFlow")


class SpreadsheetRequest(BaseModel):
    """Request model for spreadsheet generation."""
    objective: str = Field(..., example="Model FY-2024 revenue break-even")
    data: str | None = Field(
        None,
        example="Revenue: 763.9M, Participants: 7020",
        description="Plaintext data or '@/abs/path.txt' to read from file."
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
    description="Check if the service is running and healthy."
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
        version="1.0.0"
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
    """
)
async def research(body: ResearchRequest) -> ResearchResponse:
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
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
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
                        text_result.get("data", {}).get("text") or  # Primary: data.text
                        text_result.get("text") or  # Secondary: direct text field
                        text_result.get("message") or  # Alternative: message field
                        str(data)  # Fallback to string representation
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
    response_class=FileResponse
)
async def generate_spreadsheet(body: SpreadsheetRequest):
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
    response_model=dict
)
async def generate_plan(body: SpreadsheetRequest):
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
