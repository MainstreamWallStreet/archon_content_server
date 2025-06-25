"""
Main FastAPI application for the template.
"""

import logging
import secrets
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse

from src.config import get_setting
from src.database import DataStore
from src.in_memory_store import InMemoryStore
from src.models import (
    HealthResponse,
    Item,
    ItemCreate,
    ItemsResponse,
    ItemUpdate,
    SchedulerResponse,
)
from src.scheduler import BackgroundScheduler, get_scheduler
from src.routers.generate import router as generate_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API key authentication
API_KEY_HEADER = APIKeyHeader(name="X-API-Key")


# Initialize FastAPI app
async def lifespan(app: FastAPI):
    logger.info("Starting FastAPI application")
    scheduler_instance = get_scheduler_instance()
    await scheduler_instance.start()
    logger.info("Application startup complete")
    yield
    logger.info("Shutting down FastAPI application")
    await scheduler_instance.stop()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Archon Content Server",
    description="Archon Content Server – lightweight FastAPI application",
    version="1.0.0",
    lifespan=lifespan,
)

# Initialize data store
data_store: DataStore = None

# Initialize scheduler
scheduler: BackgroundScheduler = None


def get_data_store() -> DataStore:
    """Get the data store instance (singleton)."""
    global data_store
    if data_store is None:
        data_store = InMemoryStore()
    return data_store


def get_scheduler_instance() -> BackgroundScheduler:
    """Get the scheduler instance."""
    global scheduler
    if scheduler is None:
        scheduler = get_scheduler()
    return scheduler


def validate_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Validate the API key."""
    expected_key = get_setting("ARCHON_API_KEY")
    if not secrets.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "APIKey"},
        )
    return api_key


@app.get("/", response_model=dict)
def root(_: str = Depends(validate_api_key)):
    """Root endpoint with basic health status."""
    return {
        "status": "ok",
        "message": "Zergling FastAPI Server is running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Detailed health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
    )


@app.get("/items", response_model=ItemsResponse)
async def list_items(_: str = Depends(validate_api_key)):
    """List all items."""
    try:
        store = get_data_store()
        items = store.list_items()

        return ItemsResponse(items=items, total=len(items))
    except Exception as e:
        logger.error(f"Error listing items: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: str, _: str = Depends(validate_api_key)):
    """Get a specific item by ID."""
    try:
        store = get_data_store()
        item = store.get_item(item_id)

        if item is None:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

        return item
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting item {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/items", response_model=Item, status_code=201)
async def create_item(item: ItemCreate, _: str = Depends(validate_api_key)):
    """Create a new item."""
    try:
        store = get_data_store()
        created_item = store.create_item(item)

        logger.info(f"Created item: {created_item.id}")
        return created_item
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/items/{item_id}", response_model=Item)
async def update_item(
    item_id: str, item_update: ItemUpdate, _: str = Depends(validate_api_key)
):
    """Update an existing item."""
    try:
        store = get_data_store()
        updated_item = store.update_item(item_id, item_update)

        logger.info(f"Updated item: {item_id}")
        return updated_item
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating item {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/items/{item_id}", status_code=204)
async def delete_item(item_id: str, _: str = Depends(validate_api_key)):
    """Delete an item."""
    try:
        store = get_data_store()
        store.delete_item(item_id)

        logger.info(f"Deleted item: {item_id}")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting item {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/tasks/run-scheduler", response_model=SchedulerResponse)
async def run_scheduler(_: str = Depends(validate_api_key)):
    """Manually trigger background tasks."""
    try:
        scheduler_instance = get_scheduler_instance()
        result = await scheduler_instance.run_tasks()

        return SchedulerResponse(
            message="Background tasks completed", tasks_run=result["tasks_run"]
        )
    except Exception as e:
        logger.error(f"Error running scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    return JSONResponse(status_code=404, content={"detail": "Resource not found"})


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(422)
async def validation_error_handler(request, exc):
    """Handle validation errors."""
    return JSONResponse(
        status_code=422, content={"detail": "Validation error", "errors": exc.errors()}
    )


# ---- LangFlow integration (optional) ---------------------------------------
from src.langflow_mount import attach_langflow

attach_langflow(app)

app.include_router(generate_router)
