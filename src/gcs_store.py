"""
GCS-based data store implementation.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional
import io

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from src.database import DataStore
from src.models import Item, ItemCreate, ItemUpdate


class GcsStore(DataStore):
    """GCS-based implementation of DataStore."""
    
    def __init__(self, bucket_name: str):
        """Initialize GCS store with bucket name."""
        if not bucket_name:
            raise ValueError("Bucket name is required")
        
        try:
            self.client = storage.Client()
            self.bucket = self.client.bucket(bucket_name)
            self.bucket_name = bucket_name
            
            if not self.bucket.exists():
                raise ValueError(f"GCS bucket {bucket_name} does not exist")
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to initialize GCS client: {exc}") from exc
    
    def list_items(self) -> List[Item]:
        """List all items from GCS."""
        try:
            blob = self.bucket.blob("items.json")
            if not blob.exists():
                return []
            
            data = json.loads(blob.download_as_text())
            return [Item(**item) for item in data.get("items", [])]
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to list items: {exc}") from exc
    
    def get_item(self, item_id: str) -> Optional[Item]:
        """Get a specific item by ID from GCS."""
        try:
            blob = self.bucket.blob(f"items/{item_id}.json")
            if not blob.exists():
                return None
            
            data = json.loads(blob.download_as_text())
            return Item(**data)
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to get item {item_id}: {exc}") from exc
    
    def create_item(self, item: ItemCreate) -> Item:
        """Create a new item in GCS."""
        try:
            item_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            
            new_item = Item(
                id=item_id,
                name=item.name,
                description=item.description,
                created_at=now,
                updated_at=now
            )
            
            # Check if item with this ID already exists (unlikely but possible)
            blob = self.bucket.blob(f"items/{item_id}.json")
            if blob.exists():
                raise ValueError(f"Item with id {item_id} already exists")
            
            # Save the item
            blob.upload_from_string(
                json.dumps(new_item.model_dump()),
                content_type="application/json"
            )
            
            return new_item
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to create item: {exc}") from exc
    
    def update_item(self, item_id: str, item_update: ItemUpdate) -> Item:
        """Update an existing item in GCS."""
        try:
            blob = self.bucket.blob(f"items/{item_id}.json")
            if not blob.exists():
                raise ValueError(f"Item with id {item_id} not found")
            
            # Get existing item
            existing_data = json.loads(blob.download_as_text())
            existing_item = Item(**existing_data)
            
            # Update fields
            update_data = item_update.model_dump(exclude_none=True)
            for field, value in update_data.items():
                setattr(existing_item, field, value)
            
            # Update timestamp
            existing_item.updated_at = datetime.now(timezone.utc).isoformat()
            
            # Save updated item
            blob.upload_from_string(
                json.dumps(existing_item.model_dump()),
                content_type="application/json"
            )
            
            return existing_item
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to update item {item_id}: {exc}") from exc
    
    def delete_item(self, item_id: str) -> None:
        """Delete an item from GCS."""
        try:
            blob = self.bucket.blob(f"items/{item_id}.json")
            if not blob.exists():
                raise ValueError(f"Item with id {item_id} not found")
            
            blob.delete()
        except GoogleCloudError as exc:
            raise RuntimeError(f"Failed to delete item {item_id}: {exc}") from exc

    def list_objects(self) -> List[str]:
        """
        List all object names in the bucket.
        """
        return [blob.name for blob in self.bucket.list_blobs()]

    def get_object(self, object_name: str) -> bytes:
        """
        Download an object from the bucket.
        """
        blob = self.bucket.blob(object_name)
        if not blob.exists():
            raise FileNotFoundError(f"Object {object_name} not found.")
        return blob.download_as_bytes()

    def put_object(self, object_name: str, data: bytes) -> None:
        """
        Upload a new object to the bucket.
        """
        blob = self.bucket.blob(object_name)
        if blob.exists():
            raise FileExistsError(f"Object {object_name} already exists.")
        blob.upload_from_string(data)

    def update_object(self, object_name: str, data: bytes) -> None:
        """
        Update (overwrite) an existing object in the bucket.
        """
        blob = self.bucket.blob(object_name)
        if not blob.exists():
            raise FileNotFoundError(f"Object {object_name} not found.")
        blob.upload_from_string(data)

    def delete_object(self, object_name: str) -> None:
        """
        Delete an object from the bucket.
        """
        blob = self.bucket.blob(object_name)
        if not blob.exists():
            raise FileNotFoundError(f"Object {object_name} not found.")
        blob.delete() 