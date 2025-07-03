from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.auth import APIKeyAuth
from src.langflow_runner import run_langflow_json
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(tags=["research"])


class ResearchRequest(BaseModel):
    query: str = Field(
        ..., example="Why is Citi's ROE depressed in the last two years?"
    )


class ResearchResponse(BaseModel):
    result: str
    metadata: dict = Field(default_factory=dict)


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
        raise HTTPException(
            status_code=500, detail="Research flow definition not found."
        )

    # Execute the flow in a thread pool to avoid event loop conflicts
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result, debug_info, _ = await loop.run_in_executor(
                executor, run_langflow_json, str(flow_path), body.query
            )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error executing research flow: {exc}"
        )

    return ResearchResponse(
        result=result, metadata={"flow": "research", "debug": debug_info}
    )


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
        raise HTTPException(
            status_code=500, detail="Research flow definition not found."
        )

    # Execute the flow in a thread pool to avoid event loop conflicts
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result, debug_info, _ = await loop.run_in_executor(
                executor, run_langflow_json, str(flow_path), body.query
            )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Error executing research flow: {exc}"
        )

    return ResearchResponse(
        result=result, metadata={"flow": "build-context", "debug": debug_info}
    )


# CLI for manual testing and debug file output
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test the research flow endpoint via CLI."
    )
    parser.add_argument(
        "--query", type=str, required=True, help="Query to send to the research flow."
    )
    parser.add_argument(
        "--debug-file",
        type=str,
        default="research_debug_output.json",
        help="File to save debug output.",
    )
    args = parser.parse_args()
    flow_path = Path(__file__).parent.parent / "flows" / "Research flow.json"
    result, debug_info, _ = run_langflow_json(
        str(flow_path), args.query, args.debug_file
    )
    print("\n[CLI] Result:\n", result)
    print("\n[CLI] Debug info saved to:", args.debug_file)
