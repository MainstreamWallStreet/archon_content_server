"""
Main FastAPI application for the template.
"""

from datetime import datetime, timezone

from fastapi import FastAPI

from src.routers.spreadsheet import router as spreadsheet_router

app = FastAPI(title="Archon Content Server", version="1.0.0")


@app.get("/health")
def health_check():
    """Simple health-check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# Mount Spreadsheet-Builder endpoint
app.include_router(spreadsheet_router)
