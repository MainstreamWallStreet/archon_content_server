"""
Pydantic models for FastAPI template.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator


class ItemBase(BaseModel):
    """Base model for items."""
    name: str = Field(..., min_length=1, max_length=255, description="Item name")
    description: Optional[str] = Field(None, max_length=1000, description="Item description")


class ItemCreate(ItemBase):
    """Model for creating a new item."""
    pass


class ItemUpdate(BaseModel):
    """Model for updating an existing item."""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Item name")
    description: Optional[str] = Field(None, max_length=1000, description="Item description")


class Item(ItemBase):
    """Model for item responses."""
    id: str = Field(..., description="Unique item identifier")
    created_at: str = Field(..., description="ISO 8601 timestamp when item was created")
    updated_at: str = Field(..., description="ISO 8601 timestamp when item was last updated")

    model_config = {"from_attributes": True}


class ItemsResponse(BaseModel):
    """Response model for list of items."""
    items: list[Item] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Health status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="Application version")


class SchedulerResponse(BaseModel):
    """Response model for scheduler operations."""
    message: str = Field(..., description="Operation message")
    tasks_run: int = Field(..., description="Number of tasks executed")


class ErrorResponse(BaseModel):
    """Response model for errors."""
    detail: str = Field(..., description="Error details")


class ObjectListResponse(BaseModel):
    """
    Response model for listing objects in the example_bucket.
    """
    objects: List[str] = Field(..., description="List of object names in the bucket.")


class ObjectUploadRequest(BaseModel):
    """
    Request model for uploading or updating an object.
    """
    object_name: str = Field(..., description="Name of the object to upload or update.")
    data: str = Field(..., description="Base64-encoded data to store in the object.")


class ObjectDownloadResponse(BaseModel):
    """
    Response model for downloading an object.
    """
    object_name: str = Field(..., description="Name of the object.")
    data: str = Field(..., description="Base64-encoded data of the object.") 